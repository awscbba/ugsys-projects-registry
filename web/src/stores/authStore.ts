import { atom, computed } from 'nanostores';
import type { AuthUser, TokenPair } from '../types/auth';
import { authService } from '../services/authService';

// ── In-memory token storage — never written to localStorage ──────────────────

let _accessToken: string | null = null;
let _refreshToken: string | null = null;

/** Called by httpClient — reads from memory, not localStorage */
export function getAccessToken(): string | null {
  return _accessToken;
}

/** Called by httpClient — reads from memory, not localStorage */
export function getRefreshToken(): string | null {
  return _refreshToken;
}

/** Called by httpClient after a successful token refresh */
export function setTokens(accessToken: string, refreshToken: string): void {
  _accessToken = accessToken;
  _refreshToken = refreshToken;
}

/** Called by httpClient on refresh failure or explicit logout */
export function clearTokens(): void {
  _accessToken = null;
  _refreshToken = null;
}

// ── Helpers ───────────────────────────────────────────────────────────────────

function decodeJwtPayload(token: string): Record<string, unknown> {
  const base64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
  return JSON.parse(atob(base64));
}

function extractUser(token: string): AuthUser | null {
  try {
    const payload = decodeJwtPayload(token);
    const exp = payload['exp'];
    if (typeof exp === 'number' && exp * 1000 < Date.now()) {
      return null; // expired
    }
    const sub = payload['sub'];
    const email = payload['email'];
    const roles = payload['roles'] ?? payload['cognito:groups'] ?? [];
    if (typeof sub !== 'string' || typeof email !== 'string') {
      return null;
    }
    return {
      sub,
      email,
      roles: Array.isArray(roles) ? (roles as string[]) : [],
    };
  } catch {
    return null;
  }
}

// ── Atoms ─────────────────────────────────────────────────────────────────────

export const $user = atom<AuthUser | null>(null);
export const $isLoading = atom<boolean>(false);
export const $isAuthenticated = computed($user, (user) => user !== null);

// ── Actions ───────────────────────────────────────────────────────────────────

/**
 * Call once on app startup. Tokens are in-memory only — no localStorage hydration.
 * If the user refreshes the page, they will need to log in again.
 */
export function initializeAuth(): void {
  // No-op: tokens are not persisted. Session is lost on page reload by design.
}

/**
 * Authenticate with email + password. Stores tokens in memory only (not localStorage).
 * Sets $user from the returned access_token claims.
 */
export async function login(email: string, password: string): Promise<void> {
  $isLoading.set(true);
  try {
    const tokens: TokenPair = await authService.login(email, password);
    _accessToken = tokens.access_token;
    _refreshToken = tokens.refresh_token;
    const user = extractUser(tokens.access_token);
    $user.set(user);
  } finally {
    $isLoading.set(false);
  }
}

/**
 * Clear in-memory session and redirect to home.
 */
export async function logout(): Promise<void> {
  _accessToken = null;
  _refreshToken = null;
  $user.set(null);
  try {
    // Import lazily to avoid circular dependency (httpClient imports authStore)
    const { httpClient } = await import('../services/httpClient');
    await httpClient.post('/api/v1/auth/logout');
  } catch {
    // best-effort — session already cleared client-side
  }
  window.location.href = '/';
}
