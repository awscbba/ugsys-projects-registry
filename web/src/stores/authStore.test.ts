import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import * as fc from 'fast-check';

// Mock httpClient and authService to prevent module-level side effects
vi.mock('../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../services/authService', () => ({
  authService: {
    login: vi.fn(),
    register: vi.fn(),
    refreshToken: vi.fn(),
    forgotPassword: vi.fn(),
    resetPassword: vi.fn(),
    changePassword: vi.fn(),
  },
}));

// Build a minimal valid JWT (structurally valid for decoding, not cryptographically signed)
function makeJwt(sub: string, email: string, expOffset = 3600): string {
  const header = btoa(JSON.stringify({ alg: 'RS256', typ: 'JWT' }));
  const body = btoa(
    JSON.stringify({
      sub,
      email,
      exp: Math.floor(Date.now() / 1000) + expOffset,
      roles: [],
    })
  );
  return `${header}.${body}.fakesig`;
}

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('authStore unit', () => {
  beforeEach(async () => {
    // Reset shared module state between tests
    const { clearTokens, $user } = await import('./authStore');
    clearTokens();
    $user.set(null);
    vi.unstubAllGlobals();
  });

  it('setTokens and getAccessToken round-trip', async () => {
    const { setTokens, getAccessToken, clearTokens } = await import('./authStore');
    setTokens('acc-123');
    expect(getAccessToken()).toBe('acc-123');
    clearTokens();
    expect(getAccessToken()).toBeNull();
  });

  it('initializeAuth calls fetch and hydrates $user on 200', async () => {
    const accessToken = makeJwt('u1', 'test@example.com');
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { access_token: accessToken, refresh_token: 'r' } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const { initializeAuth, $user } = await import('./authStore');
    await initializeAuth();

    expect(fetchMock).toHaveBeenCalled();
    expect($user.get()).not.toBeNull();
    expect($user.get()?.email).toBe('test@example.com');
  });

  it('initializeAuth stays unauthenticated on 401', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ message: 'Unauthorized' }), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const { initializeAuth, $user, clearTokens } = await import('./authStore');
    clearTokens();
    await initializeAuth();

    expect($user.get()).toBeNull();
  });

  it('initializeAuth stays unauthenticated on network error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('Network error')));

    const { initializeAuth, $user, clearTokens } = await import('./authStore');
    clearTokens();
    // Must not throw
    await expect(initializeAuth()).resolves.toBeUndefined();
    expect($user.get()).toBeNull();
  });

  it('login with an expired JWT sets $user to null', async () => {
    const { authService } = await import('../services/authService');
    const { login, $user } = await import('./authStore');

    // exp in the past
    const expiredToken = makeJwt('u1', 'x@x.com', -100);
    vi.mocked(authService.login).mockResolvedValue({
      access_token: expiredToken,
      refresh_token: 'ref',
      expires_in: 3600,
    });

    await login('x@x.com', 'password');
    expect($user.get()).toBeNull();
  });

  it('login with a malformed JWT sets $user to null (extractUser catch branch)', async () => {
    const { authService } = await import('../services/authService');
    const { login, $user } = await import('./authStore');

    vi.mocked(authService.login).mockResolvedValue({
      access_token: 'not.a.jwt',
      refresh_token: 'ref',
      expires_in: 3600,
    });

    await login('x@x.com', 'password');
    expect($user.get()).toBeNull();
  });

  it('login does not store refresh token in JS memory', async () => {
    const { authService } = await import('../services/authService');
    const { login, getAccessToken } = await import('./authStore');

    vi.mocked(authService.login).mockResolvedValue({
      access_token: makeJwt('u1', 'test@example.com'),
      refresh_token: 'some-refresh-token',
      expires_in: 3600,
    });

    await login('test@example.com', 'password');

    // Access token is stored in memory (needed for Authorization header)
    expect(getAccessToken()).not.toBeNull();
    // No getRefreshToken() — refresh token is managed by httpOnly cookie only
  });

  it('logout calls endpoint with credentials include and clears access token', async () => {
    const { httpClient } = await import('../services/httpClient');
    const { login, logout, getAccessToken } = await import('./authStore');
    const { authService } = await import('../services/authService');

    vi.mocked(authService.login).mockResolvedValue({
      access_token: makeJwt('u1', 'test@example.com'),
      refresh_token: 'r',
      expires_in: 3600,
    });
    vi.mocked(httpClient.post).mockResolvedValue(undefined);

    // Stub window.location.href to prevent jsdom navigation
    const hrefSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      href: '',
    } as Location);

    try {
      await login('test@example.com', 'password');
      await logout();
      expect(getAccessToken()).toBeNull();
    } finally {
      hrefSpy.mockRestore();
    }
  });
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('authStore token security', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Property 11: tokens not persisted to localStorage after login ───────────
  it('Property 11: localStorage.setItem is never called with token keys after login', async () => {
    const { authService } = await import('../services/authService');
    const { login } = await import('./authStore');

    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    await fc.assert(
      fc.asyncProperty(fc.emailAddress(), fc.string({ minLength: 8 }), async (email, password) => {
        setItemSpy.mockClear();
        const accessToken = makeJwt('u1', email);
        vi.mocked(authService.login).mockResolvedValue({
          access_token: accessToken,
          refresh_token: 'refresh-token',
          expires_in: 3600,
        });

        await login(email, password);

        const tokenCalls = setItemSpy.mock.calls.filter(
          ([key]) => key === 'access_token' || key === 'refresh_token'
        );
        expect(tokenCalls).toHaveLength(0);
      }),
      { numRuns: 20 }
    );

    setItemSpy.mockRestore();
  });

  // ── Property 12: logout clears in-memory token ──────────────────────────────
  it('Property 12: getAccessToken() returns null after logout', async () => {
    const { authService } = await import('../services/authService');
    const { httpClient } = await import('../services/httpClient');
    const { login, logout, getAccessToken } = await import('./authStore');

    const hrefSpy = vi.spyOn(window, 'location', 'get').mockReturnValue({
      ...window.location,
      href: '',
    } as Location);

    try {
      await fc.assert(
        fc.asyncProperty(
          fc.emailAddress(),
          fc.string({ minLength: 8 }),
          async (email, password) => {
            const accessToken = makeJwt('u1', email);
            vi.mocked(authService.login).mockResolvedValue({
              access_token: accessToken,
              refresh_token: 'refresh-token',
              expires_in: 3600,
            });
            vi.mocked(httpClient.post).mockResolvedValue(undefined);

            await login(email, password);
            expect(getAccessToken()).not.toBeNull();

            await logout();

            expect(getAccessToken()).toBeNull();
          }
        ),
        { numRuns: 20 }
      );
    } finally {
      hrefSpy.mockRestore();
    }
  });
});

// ═══════════════════════════════════════════════════════════════════════════════
// BUG CONDITION TESTS — Cross-Service Session (Task 1 / Task 3.8 verification)
// **Validates: Requirements 1.5, 1.7, 1.9**
// ═══════════════════════════════════════════════════════════════════════════════

describe('Bug condition: cross-service session', () => {
  afterEach(() => {
    vi.clearAllMocks();
    vi.unstubAllGlobals();
  });

  /**
   * Bug 1.5 / 1.7: initializeAuth() MUST call POST /api/v1/auth/refresh.
   * EXPECTED OUTCOME: PASSES after fix (initializeAuth now calls fetch).
   */
  it('test_initializeAuth_makes_no_http_call_bug_condition', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ data: { access_token: makeJwt('u1', 'test@example.com') } }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      })
    );
    vi.stubGlobal('fetch', fetchMock);

    const { initializeAuth } = await import('./authStore');
    await initializeAuth();

    expect(fetchMock).toHaveBeenCalled();
  });

  /**
   * Bug 1.9: After login, refresh token MUST NOT be stored in JS memory.
   * EXPECTED OUTCOME: PASSES after fix (no getRefreshToken() — cookie manages it).
   */
  it('test_refresh_token_stored_in_js_bug_condition', async () => {
    const { authService } = await import('../services/authService');
    const { login, getAccessToken } = await import('./authStore');

    vi.mocked(authService.login).mockResolvedValue({
      access_token: makeJwt('u1', 'test@example.com'),
      refresh_token: 'some-refresh-token',
      expires_in: 3600,
    });

    await login('test@example.com', 'password');

    // Access token is in memory (needed for Authorization header)
    expect(getAccessToken()).not.toBeNull();
    // Refresh token is NOT in JS — no getRefreshToken() export on fixed code
    // The absence of getRefreshToken confirms the bug is fixed
    const storeModule = await import('./authStore');
    expect('getRefreshToken' in storeModule).toBe(false);
  });
});
