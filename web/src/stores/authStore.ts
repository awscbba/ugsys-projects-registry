import { atom, computed } from 'nanostores';
import type { AuthUser } from '../types/auth';

// ── In-memory token storage — never written to localStorage ──────────────────

let _accessToken: string | null = null;

/** Called by httpClient — reads from memory, not localStorage */
export function getAccessToken(): string | null {
  return _accessToken;
}

/** Called by httpClient after a successful token refresh */
export function setTokens(accessToken: string): void {
  _accessToken = accessToken;
}

/** Called by httpClient on refresh failure or explicit logout */
export function clearTokens(): void {
  _accessToken = null;
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

// ── Auth base URL (identity-manager may be on a different origin) ─────────────

const AUTH_BASE_URL =
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_AUTH_API_URL) ??
  (typeof import.meta !== 'undefined' && import.meta.env?.VITE_API_BASE_URL) ??
  '';

// ── Actions ───────────────────────────────────────────────────────────────────

/**
 * Call once on app startup. Attempts a silent token refresh using the httpOnly
 * cookie set by the identity-manager. On success, hydrates $user from the new
 * access token. On 401 or network error, stays unauthenticated silently.
 */
export async function initializeAuth(): Promise<void> {
  try {
    const response = await fetch(`${AUTH_BASE_URL}/api/v1/auth/refresh`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include', // sends the httpOnly cookie cross-subdomain
    });
    if (!response.ok) {
      // 401 = no valid session — stay unauthenticated, no throw
      return;
    }
    const json = await response.json();
    const data = json.data ?? json;
    const accessToken: string = data.access_token;
    _accessToken = accessToken;
    $user.set(extractUser(accessToken));
  } catch {
    // Network error — stay unauthenticated, no throw
  }
}

/**
 * Authenticate with email + password. Stores access token in memory only.
 * The refresh token is managed as an httpOnly cookie by the identity-manager.
 * Sets $user from the returned access_token claims.
 */
export async function login(email: string, password: string): Promise<void> {
  $isLoading.set(true);
  try {
    // Import lazily to avoid circular dependency (authService → httpClient → authStore)
    const { authService } = await import('../services/authService');
    const tokens = await authService.login(email, password);
    _accessToken = tokens.access_token;
    // refresh_token is NOT stored in JS — it lives in the httpOnly cookie
    const user = extractUser(tokens.access_token);
    $user.set(user);
  } finally {
    $isLoading.set(false);
  }
}

/**
 * Clear in-memory session and redirect to home.
 * The server-side logout call clears the httpOnly cookie.
 */
export async function logout(): Promise<void> {
  _accessToken = null;
  $user.set(null);
  try {
    // Import lazily to avoid circular dependency (httpClient imports authStore)
    const { httpClient } = await import('../services/httpClient');
    await httpClient.post('/api/v1/auth/logout', undefined, { credentials: 'include' });
  } catch {
    // best-effort — session already cleared client-side
  }
  window.location.href = '/';
}
