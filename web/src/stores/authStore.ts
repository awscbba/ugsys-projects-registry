import { atom, computed } from "nanostores";
import type { AuthUser, TokenPair } from "../types/auth";
import { authService } from "../services/authService";

// ── Helpers ───────────────────────────────────────────────────────────────────

function decodeJwtPayload(token: string): Record<string, unknown> {
  const base64 = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(base64));
}

function extractUser(token: string): AuthUser | null {
  try {
    const payload = decodeJwtPayload(token);
    const exp = payload["exp"];
    if (typeof exp === "number" && exp * 1000 < Date.now()) {
      return null; // expired
    }
    const sub = payload["sub"];
    const email = payload["email"];
    const roles = payload["roles"] ?? payload["cognito:groups"] ?? [];
    if (typeof sub !== "string" || typeof email !== "string") {
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
 * Call once on app startup. Reads access_token from localStorage,
 * validates expiry, and hydrates $user from JWT claims.
 */
export function initializeAuth(): void {
  const token = localStorage.getItem("access_token");
  if (!token) return;
  const user = extractUser(token);
  $user.set(user);
}

/**
 * Authenticate with email + password. Stores tokens in localStorage
 * and sets $user from the returned access_token claims.
 */
export async function login(email: string, password: string): Promise<void> {
  $isLoading.set(true);
  try {
    const tokens: TokenPair = await authService.login(email, password);
    localStorage.setItem("access_token", tokens.access_token);
    localStorage.setItem("refresh_token", tokens.refresh_token);
    const user = extractUser(tokens.access_token);
    $user.set(user);
  } finally {
    $isLoading.set(false);
  }
}

/**
 * Clear session and redirect to home.
 */
export function logout(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  $user.set(null);
  window.location.href = "/";
}
