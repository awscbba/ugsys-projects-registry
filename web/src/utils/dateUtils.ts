/**
 * Format an ISO date string to a human-readable display format.
 */
export function formatDate(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('es-BO', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}

/**
 * Format an ISO datetime string to a short display format.
 */
export function formatDateTime(iso: string | undefined): string {
  if (!iso) return '—';
  try {
    return new Intl.DateTimeFormat('es-BO', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    }).format(new Date(iso));
  } catch {
    return iso;
  }
}
