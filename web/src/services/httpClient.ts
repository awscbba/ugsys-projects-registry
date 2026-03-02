/**
 * Singleton HTTP client wrapping fetch.
 * - Injects Authorization: Bearer <token> from in-memory authStore (not localStorage)
 * - Adds X-Request-ID (UUID v4) on every request
 * - 401 interceptor: refresh once → retry → force logout on failure
 * - Unwraps { data, meta } envelope on success
 * - Throws Error with user-facing message on failure
 * - 15-second timeout via AbortController
 */

import { getAccessToken, getRefreshToken, setTokens, clearTokens } from '../stores/authStore';

const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';
const TIMEOUT_MS = 15_000;

type RefreshFn = (token: string) => Promise<{ access_token: string; refresh_token: string }>;

let _refreshTokenFn: RefreshFn | null = null;

/** Injected by authService to avoid circular dependency. */
export function setRefreshTokenFn(fn: RefreshFn): void {
  _refreshTokenFn = fn;
}

function forceLogout(): void {
  clearTokens();
  window.location.href = '/login';
}

function buildHeaders(token: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    'X-Request-ID': crypto.randomUUID(),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

async function parseResponse<T>(response: Response): Promise<T> {
  const json = await response.json().catch(() => null);

  if (!response.ok) {
    const message =
      (json as { message?: string } | null)?.message ??
      `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  // Unwrap envelope: { data: T, meta: { ... } }
  if (json && typeof json === 'object' && 'data' in json) {
    return (json as { data: T }).data;
  }

  return json as T;
}

async function fetchWithTimeout(url: string, options: RequestInit): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { ...options, signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

async function request<T>(
  method: string,
  path: string,
  body?: unknown,
  isRetry = false
): Promise<T> {
  const token = getAccessToken();
  const url = `${BASE_URL}${path}`;

  const options: RequestInit = {
    method,
    headers: buildHeaders(token),
  };

  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }

  const response = await fetchWithTimeout(url, options);

  if (response.status === 401 && !isRetry) {
    // Attempt one token refresh
    const refreshToken = getRefreshToken();
    if (refreshToken && _refreshTokenFn) {
      try {
        const tokens = await _refreshTokenFn(refreshToken);
        setTokens(tokens.access_token, tokens.refresh_token);
        // Retry original request once
        return request<T>(method, path, body, true);
      } catch {
        forceLogout();
        throw new Error('Session expired. Please log in again.');
      }
    } else {
      forceLogout();
      throw new Error('Session expired. Please log in again.');
    }
  }

  return parseResponse<T>(response);
}

export const httpClient = {
  get<T>(path: string): Promise<T> {
    return request<T>('GET', path);
  },

  post<T>(path: string, body?: unknown): Promise<T> {
    return request<T>('POST', path, body);
  },

  put<T>(path: string, body?: unknown): Promise<T> {
    return request<T>('PUT', path, body);
  },

  patch<T>(path: string, body?: unknown): Promise<T> {
    return request<T>('PATCH', path, body);
  },

  delete<T>(path: string): Promise<T> {
    return request<T>('DELETE', path);
  },
};
