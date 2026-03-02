/**
 * httpClient tests — Bug condition exploration (Task 1) + Preservation (Task 2)
 *
 * Exploration tests (describe 'Bug condition (b)'):
 *   MUST FAIL on unfixed code — confirms forceLogout() fires unconditionally on 401
 *   MUST PASS after fix (Task 3.4 verification)
 *
 * Preservation tests (describe 'Preservation'):
 *   MUST PASS on unfixed code — confirms baseline behavior to preserve
 *   MUST STILL PASS after fix (Task 3.5 verification)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';

// ── Module-level mocks ────────────────────────────────────────────────────────

vi.mock('../stores/authStore', () => ({
  getAccessToken: vi.fn(),
  getRefreshToken: vi.fn(),
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
}));

import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '../stores/authStore';
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
// On UNFIXED code: forceLogout() fires → window.location.href = '/login' → FAILS assertion
// On FIXED code:   error is thrown to caller, no redirect → PASSES

describe('Bug condition (b): public 401 with no session tokens', () => {
  let hrefSetter: ReturnType<typeof vi.fn>;
  let originalDescriptor: PropertyDescriptor | undefined;

  beforeEach(() => {
    // Spy on window.location.href setter
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
    vi.mocked(getRefreshToken).mockReturnValue(null);

    // No refresh function registered
    setRefreshTokenFn(null as never);
  });

  afterEach(() => {
    if (originalDescriptor) {
      Object.defineProperty(window, 'location', originalDescriptor);
    }
    vi.clearAllMocks();
  });

  it('does NOT call forceLogout (set window.location.href) on 401 when both tokens are null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    try {
      await httpClient.get('/api/v1/projects/public');
    } catch {
      // expected to throw — we only care that forceLogout was NOT called
    }

    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
  });

  it('throws an Error to the caller on 401 when both tokens are null', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    await expect(httpClient.get('/api/v1/projects/public')).rejects.toThrow();
  });

  // Property-based: for ANY request path, 401 with no tokens never triggers forceLogout
  it('Property: for any path, 401 with no tokens never sets window.location.href to /login', async () => {
    await fc.assert(
      fc.asyncProperty(fc.webPath(), async (path) => {
        vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));
        vi.mocked(getAccessToken).mockReturnValue(null);
        vi.mocked(getRefreshToken).mockReturnValue(null);

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

// ── Preservation: Authenticated 401 → refresh → retry ────────────────────────
// MUST PASS on unfixed code AND after fix

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

  it('retries original request with new token after successful refresh (req 3.1)', async () => {
    // Arrange — refresh token present, refresh succeeds
    vi.mocked(getAccessToken).mockReturnValue(null);
    vi.mocked(getRefreshToken).mockReturnValue('valid-refresh-token');

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

    expect(refreshFn).toHaveBeenCalledWith('valid-refresh-token');
    expect(setTokens).toHaveBeenCalledWith('new-access-token', 'new-refresh-token');
    expect(fetchMock).toHaveBeenCalledTimes(2);
    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
    expect(result).toEqual({ id: 'p1' });
  });

  it('calls forceLogout when refresh token present but refresh fails (req 3.2)', async () => {
    // Arrange — refresh token present, but refresh throws
    vi.mocked(getAccessToken).mockReturnValue(null);
    vi.mocked(getRefreshToken).mockReturnValue('expired-refresh-token');

    const refreshFn = vi.fn().mockRejectedValue(new Error('Refresh failed'));
    setRefreshTokenFn(refreshFn);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock401Response()));

    await expect(httpClient.get('/api/v1/protected')).rejects.toThrow();

    expect(clearTokens).toHaveBeenCalled();
    expect(hrefSetter).toHaveBeenCalledWith('/login');
  });

  // Property-based: for any refresh token value, if refresh succeeds → no forceLogout
  it('Property: for any valid refresh token, successful refresh never triggers forceLogout', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.string({ minLength: 10, maxLength: 100 }),
        fc.string({ minLength: 10, maxLength: 100 }),
        fc.string({ minLength: 10, maxLength: 100 }),
        async (refreshToken, newAccessToken, newRefreshToken) => {
          vi.mocked(getAccessToken).mockReturnValue(null);
          vi.mocked(getRefreshToken).mockReturnValue(refreshToken);

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

  // Property-based: for any refresh token, if refresh fails → forceLogout always called
  it('Property: for any refresh token, failed refresh always triggers forceLogout', async () => {
    await fc.assert(
      fc.asyncProperty(fc.string({ minLength: 10, maxLength: 100 }), async (refreshToken) => {
        vi.mocked(getAccessToken).mockReturnValue(null);
        vi.mocked(getRefreshToken).mockReturnValue(refreshToken);

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
    vi.mocked(getRefreshToken).mockReturnValue(null);

    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(mock500Response()));

    try {
      await httpClient.get('/api/v1/projects/public');
    } catch {
      // expected — 500 throws
    }

    expect(hrefSetter).not.toHaveBeenCalledWith('/login');
  });
});
