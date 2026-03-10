import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type { Subscription, SubscriptionStatus } from '@/types/project';
import { subscriptionApi } from '@/services/subscriptionApi';
import { formatDate } from '@/utils/dateUtils';

interface Props {
  personId: string;
}

const STATUS_STYLES: Record<SubscriptionStatus, string> = {
  pending: 'bg-yellow-500/15 text-yellow-300 ring-1 ring-yellow-500/30',
  active: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30',
  rejected: 'bg-red-500/15 text-red-300 ring-1 ring-red-500/30',
  cancelled: 'bg-white/[0.06] text-white/40 ring-1 ring-white/10',
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
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-[#FF9900]/30 border-t-[#FF9900]" />
      </div>
    );
  }

  if (error) {
    return (
      <p
        className="rounded-xl bg-red-500/10 border border-red-500/20 p-4 text-sm text-red-400"
        role="alert"
      >
        {error}
      </p>
    );
  }

  if (subscriptions.length === 0) {
    return <p className="py-6 text-center text-sm text-white/35">No tienes suscripciones aún.</p>;
  }

  return (
    <ul className="space-y-2">
      {subscriptions.map((sub) => (
        <li key={sub.id}>
          <button
            type="button"
            onClick={() => navigate(`/subscribe/${sub.project_id}`)}
            className="
              w-full rounded-xl border border-white/[0.07] bg-[#252f42] p-4 text-left
              transition-all duration-150
              hover:border-[#FF9900]/25 hover:bg-[#2d3a52]
              focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
            "
          >
            <div className="flex items-start justify-between gap-2">
              <span className="truncate text-sm font-medium text-white/75">
                Proyecto: <span className="font-mono text-xs text-white/40">{sub.project_id}</span>
              </span>
              <span
                className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-semibold ${STATUS_STYLES[sub.status]}`}
              >
                {STATUS_LABELS[sub.status]}
              </span>
            </div>
            <p className="mt-1 text-xs text-white/30">Suscrito el {formatDate(sub.created_at)}</p>
          </button>
        </li>
      ))}
    </ul>
  );
}
