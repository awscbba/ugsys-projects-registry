import type { RegisterRequest, TokenPair } from '../types/auth';
import { httpClient, setRefreshTokenFn } from './httpClient';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

/**
 * Refresh token uses raw fetch (not httpClient) to avoid the circular
 * 401-refresh loop that would occur if httpClient called this.
 */
async function refreshToken(token: string): Promise<TokenPair> {
  const response = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token: token }),
  });

  if (!response.ok) {
    throw new Error('Token refresh failed');
  }

  const json = await response.json();
  // Unwrap envelope if present
  return (json.data ?? json) as TokenPair;
}

// Register the refresh function with httpClient
setRefreshTokenFn(refreshToken);

export const authService = {
  async login(email: string, password: string): Promise<TokenPair> {
    return httpClient.post<TokenPair>('/api/v1/auth/login', { email, password });
  },

  async register(data: RegisterRequest): Promise<void> {
    return httpClient.post<void>('/api/v1/auth/register', data);
  },

  refreshToken,

  async forgotPassword(email: string): Promise<void> {
    return httpClient.post<void>('/api/v1/auth/forgot-password', { email });
  },

  async resetPassword(token: string, newPassword: string): Promise<void> {
    return httpClient.post<void>('/api/v1/auth/reset-password', {
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
