/**
 * httpClient tests — Bug condition exploration (Task 1) + Preservation (Task 2)
 *
 * Exploration tests (describe 'Bug condition (b)'):
 *   MUST FAIL on unfixed code — confirms forceLogout() fires unconditionally on 401
 *   MUST PASS after fix (Task 3.7 verification)
 *
 * Preservation tests (describe 'Preservation'):
 *   MUST PASS on unfixed code — confirms baseline behavior to preserve
 *   MUST STILL PASS after fix (Task 3.9 verification)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';

// ── Module-level mocks ────────────────────────────────────────────────────────

vi.mock('../stores/authStore', () => ({
  getAccessToken: vi.fn(),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}));

import { getAccessToken, setTokens, clearTokens } from '../stores/authStore';
import { httpClient, setRefreshTokenFn } from './httpClient';

// ── Helpers ───────────────────────────────────────────────────────────────────

function mock401Response(): Response {
  return new Response(JSON.stringify({ message: 'Unauthorized' }), {
    status: 401,
    headers: { 'Content-Type': 'application/json' },
  });
}

function mock200Response(body: unknown = {}): Response {
  return new Response(JSON.stringify({ data: body }), {
    status: 200,
    headers: { 'Content-Type': 'application/json' },
  });
}

function mock500Response(): Response {
  return new Response(JSON.stringify({ message: 'Internal Server Error' }), {
    status: 500,
    headers: { 'Content-Type': 'application/json' },
  });
}

// ── Bug condition (b): Public 401 with no session ─────────────────────────────

describe('Bug condition (b): public 401 with no session tokens', () => {
  let hrefSetter: ReturnType<typeof vi.fn>;
  let originalDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    hrefSetter = vi.fn();
    originalDescriptor = Object.getOwnPropertyDescriptor(window, 'location');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...window.location,
        set href(v: string) {
          hrefSetter(v);
        },
      },
    });

    // No tokens in memory — fresh page load
    vi.mocked(getAccessToken).mockReturnValue(null);

    // No refresh function registered
    setRefreshTokenFn(null as never);
  });

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(window, 'location', originalDescriptor);
    }
    vi.clearAllMocks();
  });

  it('does NOT call forceLogout (set window.location.href) on 401 when access token is null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    try {
      await httpClient.get('/api/v1/projects/public');
    } catch {
      // expected to throw — we only care that forceLogout was NOT called
    }

    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
  });

  it('throws an Error to the caller on 401 when access token is null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    await expect(httpClient.get('/api/v1/projects/public')).rejects.toThrow();
  });

  // Property-based: for ANY request path, 401 with no tokens never triggers forceLogout
  it('Property: for any path, 401 with no tokens never sets window.location.href to /login', async () => {
    await fc.assert(
      fc.asyncProperty(fc.webPath(), async (path) => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));
        vi.mocked(getAccessToken).mockReturnValue(null);

        try {
          await httpClient.get(path);
        } catch {
          // expected
        }

        expect(hrefSetter).not.toHaveBeenCalledWith('/login');
        hrefSetter.mockClear();
      }),
      { numRuns: 20 }
    );
  });
});

// ── Preservation: Authenticated 401 → cookie-based refresh → retry ────────────

describe('Preservation: authenticated 401 → refresh → retry flow', () => {
  let hrefSetter: ReturnType<typeof vi.fn>;
  let originalDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    hrefSetter = vi.fn();
    originalDescriptor = Object.getOwnPropertyDescriptor(window, 'location');
    Object.defineProperty(window, 'location', {
      configurable: true,
      value: {
        ...window.location,
        set href(v: string) {
          hrefSetter(v);
        },
      },
    });
    vi.clearAllMocks();
  });

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(window, 'location', originalDescriptor);
    }
    vi.clearAllMocks();
  });

  it('retries original request with new token after successful cookie-based refresh (req 3.1)', async () => {
    // Arrange — access token expired, refresh function registered (cookie-based, no arg)
    vi.mocked(getAccessToken).mockReturnValue(null);

    // Cookie-based refresh — no token argument
    const refreshFn = vi.fn().mockResolvedValue({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    });
    setRefreshTokenFn(refreshFn);

    // First call → 401, second call (retry) → 200
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(mock401Response())
      .mockResolvedValueOnce(mock200Response({ id: 'p1' }));
    vi.stubGlobal('fetch', fetchMock);

    const result = await httpClient.get('/api/v1/projects/p1');

    // Cookie-based refresh — called with NO arguments
    expect(refreshFn).toHaveBeenCalledWith();
    expect(setTokens).toHaveBeenCalledWith('new-access-token');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
    expect(result).toEqual({ id: 'p1' });
  });

  it('calls forceLogout when refresh function present but refresh fails (req 3.2)', async () => {
    vi.mocked(getAccessToken).mockReturnValue(null);

    const refreshFn = vi.fn().mockRejectedValue(new Error('Refresh failed'));
    setRefreshTokenFn(refreshFn);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    await expect(httpClient.get('/api/v1/protected')).rejects.toThrow();

    expect(clearTokens).toHaveBeenCalled();
    expect(hrefSetter).toHaveBeenCalledWith('/login');
  });

  // Property-based: if cookie-based refresh succeeds → no forceLogout
  it('Property: successful cookie-based refresh never triggers forceLogout', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 10, maxLength: 100 }),
        fc.string({ minLength: 10, maxLength: 100 }),
        async (newAccessToken, newRefreshToken) => {
          vi.mocked(getAccessToken).mockReturnValue(null);

          // Cookie-based refresh — no token argument
          const refreshFn = vi.fn().mockResolvedValue({
            access_token: newAccessToken,
            refresh_token: newRefreshToken,
          });
          setRefreshTokenFn(refreshFn);

          const fetchMock = vi
            .fn()
            .mockResolvedValueOnce(mock401Response())
            .mockResolvedValueOnce(mock200Response({}));
          vi.stubGlobal('fetch', fetchMock);

          await httpClient.get('/api/v1/test');

          expect(hrefSetter).not.toHaveBeenCalledWith('/login');
          hrefSetter.mockClear();
          vi.clearAllMocks();
        }
      ),
      { numRuns: 20 }
    );
  });

  // Property-based: if refresh fails → forceLogout always called
  it('Property: failed cookie-based refresh always triggers forceLogout', async () => {
    await fc.assert(
      fc.asyncProperty(fc.constant(null), async () => {
        vi.mocked(getAccessToken).mockReturnValue(null);

        const refreshFn = vi.fn().mockRejectedValue(new Error('Refresh failed'));
        setRefreshTokenFn(refreshFn);

        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

        try {
          await httpClient.get('/api/v1/test');
        } catch {
          // expected
        }

        expect(hrefSetter).toHaveBeenCalledWith('/login');
        hrefSetter.mockClear();
        vi.clearAllMocks();
      }),
      { numRuns: 20 }
    );
  });

  it('does not redirect on non-401 responses (req 3.3, 3.4)', async () => {
    vi.mocked(getAccessToken).mockReturnValue(null);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock500Response()));

    try {
      await httpClient.get('/api/v1/projects/public');
    } catch {
      // expected — 500 throws
    }

    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
  });

  // ── Preservation: Authorization header on protected requests (req 3.10) ────

  it('test_makeAuthRequest_sends_authorization_header: httpClient.get includes Authorization: Bearer header (req 3.10)', async () => {
    vi.mocked(getAccessToken).mockReturnValue('test-access-token');

    const fetchMock = vi.fn().mockResolvedValue(mock200Response({ id: 'p1' }));
    vi.stubGlobal('fetch', fetchMock);

    await httpClient.get('/api/v1/projects');

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    const headers = options.headers as Record<string, string>;
    expect(headers['Authorization']).toBe('Bearer test-access-token');
  });

  // ── Preservation: 401 interceptor triggers refresh function (req 3.8) ──────

  it('test_401_interceptor_calls_refresh_fn: 401 on protected call triggers the cookie-based refresh function (req 3.8)', async () => {
    vi.mocked(getAccessToken).mockReturnValue('expired-access-token');

    // Cookie-based refresh — no token argument
    const refreshFn = vi.fn().mockResolvedValue({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    });
    setRefreshTokenFn(refreshFn);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(mock401Response()).mockResolvedValueOnce(mock200Response({}))
    );

    await httpClient.get('/api/v1/projects');

    // Cookie-based refresh — called with NO arguments
    expect(refreshFn).toHaveBeenCalledWith();
  });

  // ── Task 3.7 new tests ────────────────────────────────────────────────────

  it('test_401_interceptor_calls_refresh_without_token_arg: refresh fn called with no arguments', async () => {
    vi.mocked(getAccessToken).mockReturnValue(null);

    const refreshFn = vi.fn().mockResolvedValue({
      access_token: 'new-access-token',
      refresh_token: 'new-refresh-token',
    });
    setRefreshTokenFn(refreshFn);

    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValueOnce(mock401Response()).mockResolvedValueOnce(mock200Response({}))
    );

    await httpClient.get('/api/v1/test');

    // Must be called with zero arguments — cookie is sent automatically by browser
    expect(refreshFn).toHaveBeenCalledWith();
    expect(refreshFn.mock.calls[0]).toHaveLength(0);
  });

  it('test_makeAuthRequest_includes_credentials_include: fetch is called with credentials include', async () => {
    vi.mocked(getAccessToken).mockReturnValue('test-token');

    const fetchMock = vi.fn().mockResolvedValue(mock200Response({}));
    vi.stubGlobal('fetch', fetchMock);

    await httpClient.get('/api/v1/projects');

    const [, options] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(options.credentials).toBe('include');
  });
});
