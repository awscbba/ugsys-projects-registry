import { describe, it, expect, vi, beforeEach } from 'vitest';
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
  it('setTokens and getAccessToken / getRefreshToken round-trip', async () => {
    const { setTokens, getAccessToken, getRefreshToken, clearTokens } = await import(
      './authStore'
    );
    setTokens('acc-123', 'ref-456');
    expect(getAccessToken()).toBe('acc-123');
    expect(getRefreshToken()).toBe('ref-456');
    clearTokens();
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it('initializeAuth is a no-op and does not throw', async () => {
    const { initializeAuth } = await import('./authStore');
    expect(() => initializeAuth()).not.toThrow();
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
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('authStore token security', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Property 11: tokens not persisted to localStorage after login ───────────
  // Feature: web-frontend-quality, Property 11: tokens not persisted to localStorage after login
  it('Property 11: localStorage.setItem is never called with token keys after login', async () => {
    const { authService } = await import('../services/authService');
    const { login } = await import('./authStore');

    // Spy on Storage.prototype.setItem — works reliably in jsdom without touching window
    const setItemSpy = vi.spyOn(Storage.prototype, 'setItem');

    await fc.assert(
      fc.asyncProperty(
        fc.emailAddress(),
        fc.string({ minLength: 8 }),
        async (email, password) => {
          setItemSpy.mockClear();
          const accessToken = makeJwt('u1', email);
          vi.mocked(authService.login).mockResolvedValue({
            access_token: accessToken,
            refresh_token: 'refresh-token',
            expires_in: 3600,
          });

          await login(email, password);

          // authStore must NOT write tokens to localStorage
          const tokenCalls = setItemSpy.mock.calls.filter(
            ([key]) => key === 'access_token' || key === 'refresh_token'
          );
          expect(tokenCalls).toHaveLength(0);
        }
      ),
      { numRuns: 20 }
    );

    setItemSpy.mockRestore();
  });

  // ── Property 12: logout clears in-memory token ──────────────────────────────
  // Feature: web-frontend-quality, Property 12: logout clears in-memory token
  it('Property 12: getAccessToken() returns null after logout', async () => {
    const { authService } = await import('../services/authService');
    const { httpClient } = await import('../services/httpClient');
    const { login, logout, getAccessToken } = await import('./authStore');

    // Stub window.location.href assignment to prevent jsdom navigation errors
    // Use a property descriptor approach that doesn't corrupt the window object
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
