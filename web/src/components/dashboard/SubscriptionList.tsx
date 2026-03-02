import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Subscription, SubscriptionStatus } from '@/types/project';
import { subscriptionApi } from '@/services/subscriptionApi';
import { formatDate } from '@/utils/dateUtils';

interface Props {
  personId: string;
}

const STATUS_STYLES: Record<SubscriptionStatus, string> = {
  pending: 'bg-yellow-100 text-yellow-700',
  active: 'bg-green-100 text-green-700',
  rejected: 'bg-red-100 text-red-700',
  cancelled: 'bg-gray-100 text-gray-700',
};

const STATUS_LABELS: Record<SubscriptionStatus, string> = {
  pending: 'Pendiente',
  active: 'Activo',
  rejected: 'Rechazado',
  cancelled: 'Cancelado',
};

export default function SubscriptionList({ personId }: Props) {
  const navigate = useNavigate();
  const [subscriptions, setSubscriptions] = useState<Subscription[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    subscriptionApi
      .getMySubscriptions(personId)
      .then((data) => {
        if (!cancelled) setSubscriptions(data);
      })
      .catch(() => {
        if (!cancelled) setError('No se pudieron cargar tus suscripciones.');
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [personId]);

  if (isLoading) {
    return (
      <div className="flex justify-center py-8" aria-label="Cargando suscripciones">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-blue-500 border-t-transparent" />
      </div>
    );
  }

  if (error) {
    return (
      <p className="rounded-md bg-red-50 p-4 text-sm text-red-700" role="alert">
        {error}
      </p>
    );
  }

  if (subscriptions.length === 0) {
    return <p className="py-6 text-center text-sm text-gray-500">No tienes suscripciones aún.</p>;
  }

  return (
    <ul className="space-y-3">
      {subscriptions.map((sub) => (
        <li key={sub.id}>
          <button
            type="button"
            onClick={() => navigate(`/subscribe/${sub.project_id}`)}
            className="w-full rounded-lg border border-gray-200 bg-white p-4 text-left shadow-sm transition hover:border-blue-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-blue-500"
          >
            <div className="flex items-start justify-between gap-2">
              <span className="truncate text-sm font-medium text-gray-800">
                Proyecto: <span className="font-mono text-xs text-gray-500">{sub.project_id}</span>
              </span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[sub.status]}`}
              >
                {STATUS_LABELS[sub.status]}
              </span>
            </div>
            <p className="mt-1 text-xs text-gray-400">Suscrito el {formatDate(sub.created_at)}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}
