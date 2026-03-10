import { useParams, useNavigate, Link } from 'react-router-dom';
import type { ProjectStatus } from '../types/project';
import { useAuth } from '../hooks/useAuth';
import { addToast } from '../stores/toastStore';
import SubscriptionForm from '../components/subscriptions/SubscriptionForm';
import PublicSubscribeForm from '../components/subscriptions/PublicSubscribeForm';
import { useProjectDetail } from '../hooks/useProjectDetail';
import { usePublicSubscribe } from '../hooks/usePublicSubscribe';
import { useState } from 'react';

const STATUS_LABELS: Record<ProjectStatus, string> = {
  pending: 'Pendiente',
  active: 'Activo',
  completed: 'Completado',
  cancelled: 'Cancelado',
};

const STATUS_STYLES: Record<ProjectStatus, string> = {
  pending: 'bg-yellow-500/15 text-yellow-300 ring-1 ring-yellow-500/30',
  active: 'bg-emerald-500/15 text-emerald-300 ring-1 ring-emerald-500/30',
  completed: 'bg-sky-500/15 text-sky-300 ring-1 ring-sky-500/30',
  cancelled: 'bg-red-500/15 text-red-300 ring-1 ring-red-500/30',
};

const backLink =
  'text-sm text-[#FF9900] hover:text-[#ffb84d] transition-colors duration-150 mb-6 inline-flex items-center gap-1';

export default function SubscribePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [succeeded, setSucceeded] = useState(false);

  const { project, isLoading: isFetching, error: fetchError } = useProjectDetail(projectId);

  function handleSuccess(result: { subscription_id?: string }) {
    void result;
    if (isAuthenticated) {
      addToast('success', '¡Suscripción enviada! Está pendiente de aprobación.');
    }
    setSucceeded(true);
  }

  const publicSubscribe = usePublicSubscribe(handleSuccess);

  // Loading
  if (authLoading || isFetching) {
    return (
      <main className="flex justify-center items-center min-h-screen">
        <div
          className="w-10 h-10 rounded-full border-2 border-[#FF9900]/30 border-t-[#FF9900] animate-spin"
          role="status"
          aria-label="Cargando"
        />
      </main>
    );
  }

  // Fetch error
  if (fetchError) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-12 text-center">
        <p className="text-red-400 mb-4 text-sm">{fetchError}</p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-[#FF9900] hover:text-[#ffb84d] text-sm transition-colors"
        >
          ← Volver a proyectos
        </button>
      </main>
    );
  }

  if (!project) return null;

  // Success state
  if (succeeded) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-12 text-center">
        <div
          className="
            rounded-2xl p-10 flex flex-col items-center gap-4
            bg-[#1e2738] border border-emerald-500/20
            shadow-[0_8px_40px_rgba(0,0,0,0.4),0_0_24px_rgba(16,185,129,0.06)]
          "
        >
          <div className="w-14 h-14 rounded-full bg-emerald-500/15 ring-1 ring-emerald-500/30 flex items-center justify-center">
            <svg
              className="w-7 h-7 text-emerald-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
              aria-hidden="true"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M5 13l4 4L19 7"
              />
            </svg>
          </div>
          <h1 className="text-xl font-semibold text-white/90">¡Te has suscrito exitosamente!</h1>
          <p className="text-sm text-white/50">Tu solicitud está pendiente de aprobación.</p>
          <Link
            to="/"
            className="mt-2 text-sm font-medium text-[#FF9900] hover:text-[#ffb84d] transition-colors"
          >
            ← Volver a proyectos
          </Link>
        </div>
      </main>
    );
  }

  // Email-exists guard (public flow)
  if (!isAuthenticated && publicSubscribe.emailExistsFor) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-12">
        <Link to="/" className={backLink}>
          ← Volver a proyectos
        </Link>
        <div
          className="
            rounded-2xl p-6 flex flex-col gap-4
            bg-[#1e2738] border border-yellow-500/20
            shadow-[0_4px_24px_rgba(0,0,0,0.35)]
          "
        >
          <p className="text-sm text-white/70">
            Ya tienes una cuenta. Inicia sesión para suscribirte.
          </p>
          <Link
            to={`/login?redirect=/subscribe/${projectId}`}
            className="
              self-start rounded-lg bg-[#FF9900] px-4 py-2 text-sm font-semibold text-[#161d2b]
              hover:bg-[#ffb84d] transition-colors duration-150
              focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
            "
          >
            Iniciar sesión
          </Link>
        </div>
      </main>
    );
  }

  // Main page
  return (
    <main className="max-w-2xl mx-auto px-4 py-10">
      <Link to="/" className={backLink}>
        ← Volver a proyectos
      </Link>

      {/* Project info */}
      <section
        className="
          mb-8 p-6 rounded-2xl
          bg-[#1e2738] border border-white/[0.07]
          shadow-[0_4px_24px_rgba(0,0,0,0.3)]
        "
        aria-label="Información del proyecto"
      >
        <div className="flex items-start justify-between gap-4 mb-3">
          <h1 className="text-2xl font-bold text-white/90 leading-tight">{project.name}</h1>
          <span
            className={`shrink-0 text-xs font-medium px-2.5 py-1 rounded-full ${STATUS_STYLES[project.status]}`}
          >
            {STATUS_LABELS[project.status]}
          </span>
        </div>

        {project.category && (
          <span className="inline-block text-xs font-medium px-2.5 py-0.5 rounded-full bg-[#FF9900]/15 text-[#FF9900] ring-1 ring-[#FF9900]/25 mb-4">
            {project.category}
          </span>
        )}

        <p className="text-sm text-white/55 leading-relaxed">{project.description}</p>
      </section>

      {/* Subscription form */}
      <section
        className="
          p-6 rounded-2xl
          bg-[#1e2738] border border-white/[0.07]
          shadow-[0_4px_24px_rgba(0,0,0,0.3)]
        "
        aria-label="Formulario de suscripción"
      >
        <h2 className="text-lg font-semibold text-white/90 mb-5">
          {isAuthenticated ? 'Confirmar suscripción' : 'Suscribirse al proyecto'}
        </h2>

        {!isAuthenticated ? (
          <PublicSubscribeForm {...publicSubscribe} projectId={project.id} />
        ) : (
          <SubscriptionForm
            projectId={project.id}
            formSchema={project.form_schema}
            isAuthenticated={true}
            onSuccess={handleSuccess}
          />
        )}
      </section>
    </main>
  );
}
