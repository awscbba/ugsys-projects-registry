import type { RegisterRequest, TokenPair } from '../types/auth';
import { httpClient, makeAuthRequest, setRefreshTokenFn } from './httpClient';

// Auth endpoints (login, register, refresh, password) live on the identity-manager,
// which may be on a different origin than the projects-registry API.
// VITE_AUTH_API_URL defaults to VITE_API_BASE_URL for local dev (same origin proxy).
const AUTH_BASE_URL = import.meta.env.VITE_AUTH_API_URL ?? import.meta.env.VITE_API_BASE_URL ?? '';

/**
 * Refresh token uses raw fetch (not httpClient) to avoid the circular
 * 401-refresh loop that would occur if httpClient called this.
 * No token argument — the httpOnly cookie is sent automatically via credentials:'include'.
 */
async function refreshToken(): Promise<TokenPair> {
  const response = await fetch(`${AUTH_BASE_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include', // sends the httpOnly refresh cookie cross-subdomain
  });

  if (!response.ok) {
    throw new Error('Token refresh failed');
  }

  const json = await response.json();
  // Unwrap envelope if present
  return (json.data ?? json) as TokenPair;
}

// Register the cookie-based refresh function with httpClient
setRefreshTokenFn(refreshToken);

export const authService = {
  async login(email: string, password: string): Promise<TokenPair> {
    return makeAuthRequest<TokenPair>(AUTH_BASE_URL, 'POST', '/api/v1/auth/login', {
      email,
      password,
    });
  },

  async register(data: RegisterRequest): Promise<void> {
    return makeAuthRequest<void>(AUTH_BASE_URL, 'POST', '/api/v1/auth/register', data);
  },

  refreshToken,

  async forgotPassword(email: string): Promise<void> {
    return makeAuthRequest<void>(AUTH_BASE_URL, 'POST', '/api/v1/auth/forgot-password', { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    return makeAuthRequest<void>(AUTH_BASE_URL, 'POST', '/api/v1/auth/reset-password', {
      token,
      new_password: newPassword,
    });
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<void> {
    return httpClient.post<void>('/api/v1/auth/change-password', {
      current_password: currentPassword,
      new_password: newPassword,
    });
  },
};
