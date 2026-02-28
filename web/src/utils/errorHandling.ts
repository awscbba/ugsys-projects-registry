import type { ApiError } from "@/types/api";

/**
 * Extract a user-friendly message from an API error response.
 */
export function getErrorMessage(error: unknown): string {
  if (error instanceof Error) return error.message;
  if (typeof error === "object" && error !== null) {
    const apiError = error as Partial<ApiError>;
    if (apiError.message) return apiError.message;
  }
  return "Ha ocurrido un error inesperado";
}

/**
 * Check if an error is an API error with a specific error code.
 */
export function isApiError(error: unknown, code?: string): boolean {
  if (typeof error !== "object" || error === null) return false;
  const apiError = error as Partial<ApiError>;
  if (!apiError.error) return false;
  if (code) return apiError.error === code;
  return true;
}
