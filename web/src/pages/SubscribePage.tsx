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
  pending: 'bg-gray-100 text-gray-700',
  active: 'bg-green-100 text-green-700',
  completed: 'bg-blue-100 text-blue-700',
  cancelled: 'bg-red-100 text-red-700',
};

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
          className="w-10 h-10 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"
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
        <p className="text-red-600 mb-4">{fetchError}</p>
        <button
          type="button"
          onClick={() => navigate('/')}
          className="text-indigo-600 hover:underline text-sm"
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
        <div className="rounded-lg bg-green-50 border border-green-200 p-8 flex flex-col items-center gap-4">
          <svg
            className="w-12 h-12 text-green-500"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            aria-hidden="true"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
          <h1 className="text-xl font-semibold text-gray-900">¡Te has suscrito exitosamente!</h1>
          <p className="text-sm text-gray-600">Tu solicitud está pendiente de aprobación.</p>
          <Link to="/" className="mt-2 text-indigo-600 hover:underline text-sm font-medium">
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
        <Link to="/" className="text-sm text-indigo-600 hover:underline mb-6 inline-block">
          ← Volver a proyectos
        </Link>
        <div className="rounded-lg bg-yellow-50 border border-yellow-200 p-6 flex flex-col gap-3">
          <p className="text-sm text-gray-800">
            Ya tienes una cuenta. Inicia sesión para suscribirte.
          </p>
          <Link
            to={`/login?redirect=/subscribe/${projectId}`}
            className="self-start rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
          >
            Iniciar sesión
          </Link>
        </div>
      </main>
    );
  }

  // Main page
  return (
    <main className="max-w-2xl mx-auto px-4 py-8">
      <Link to="/" className="text-sm text-indigo-600 hover:underline mb-6 inline-block">
        ← Volver a proyectos
      </Link>

      {/* Project info */}
      <section className="mb-8" aria-label="Información del proyecto">
        <div className="flex items-start justify-between gap-4 mb-2">
          <h1 className="text-2xl font-bold text-gray-900">{project.name}</h1>
          <span
            className={`shrink-0 text-xs font-medium px-2 py-1 rounded-full ${STATUS_STYLES[project.status]}`}
          >
            {STATUS_LABELS[project.status]}
          </span>
        </div>

        {project.category && (
          <span className="inline-block text-xs font-medium px-2 py-0.5 rounded-full bg-indigo-100 text-indigo-700 mb-3">
            {project.category}
          </span>
        )}

        <p className="text-sm text-gray-700 leading-relaxed">{project.description}</p>
      </section>

      {/* Subscription form */}
      <section aria-label="Formulario de suscripción">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
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
