import { useState, useEffect } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import type { FormSchema } from "@/types/form";
import type { Project, ProjectStatus } from "@/types/project";
import { projectApi } from "@/services/projectApi";
import { subscriptionApi } from "@/services/subscriptionApi";
import { useAuth } from "@/hooks/useAuth";
import { addToast } from "@/stores/toastStore";
import SubscriptionForm from "@/components/subscriptions/SubscriptionForm";

// Project returned by getProjectEnhanced may include form_schema
type EnhancedProject = Project & { form_schema?: FormSchema };

const STATUS_LABELS: Record<ProjectStatus, string> = {
  pending: "Pendiente",
  active: "Activo",
  completed: "Completado",
  cancelled: "Cancelado",
};

const STATUS_STYLES: Record<ProjectStatus, string> = {
  pending: "bg-gray-100 text-gray-700",
  active: "bg-green-100 text-green-700",
  completed: "bg-blue-100 text-blue-700",
  cancelled: "bg-red-100 text-red-700",
};

export default function SubscribePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const { isAuthenticated, isLoading: authLoading } = useAuth();

  const [project, setProject] = useState<EnhancedProject | null>(null);
  const [fetchError, setFetchError] = useState<string | null>(null);
  const [isFetching, setIsFetching] = useState(true);
  const [succeeded, setSucceeded] = useState(false);
  const [emailExistsFor, setEmailExistsFor] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setIsFetching(true);
    projectApi
      .getProjectEnhanced(projectId)
      .then((p) => setProject(p as EnhancedProject))
      .catch(() => setFetchError("No se pudo cargar el proyecto. Intenta de nuevo."))
      .finally(() => setIsFetching(false));
  }, [projectId]);

  function handleSuccess(result: { subscription_id?: string }) {
    void result;
    if (isAuthenticated) {
      addToast("success", "¡Suscripción enviada! Está pendiente de aprobación.");
    }
    setSucceeded(true);
  }

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
          onClick={() => navigate("/")}
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
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M5 13l4 4L19 7"
            />
          </svg>
          <h1 className="text-xl font-semibold text-gray-900">
            ¡Te has suscrito exitosamente!
          </h1>
          <p className="text-sm text-gray-600">
            Tu solicitud está pendiente de aprobación.
          </p>
          <Link
            to="/"
            className="mt-2 text-indigo-600 hover:underline text-sm font-medium"
          >
            ← Volver a proyectos
          </Link>
        </div>
      </main>
    );
  }

  // Email-exists guard (public flow)
  if (!isAuthenticated && emailExistsFor) {
    return (
      <main className="max-w-2xl mx-auto px-4 py-12">
        <Link
          to="/"
          className="text-sm text-indigo-600 hover:underline mb-6 inline-block"
        >
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
      <Link
        to="/"
        className="text-sm text-indigo-600 hover:underline mb-6 inline-block"
      >
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

        <p className="text-sm text-gray-700 leading-relaxed">
          {project.description}
        </p>
      </section>

      {/* Subscription form */}
      <section aria-label="Formulario de suscripción">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {isAuthenticated
            ? "Confirmar suscripción"
            : "Suscribirse al proyecto"}
        </h2>

        {!isAuthenticated ? (
          <PublicSubscribeForm
            projectId={project.id}
            onEmailExists={(email) => setEmailExistsFor(email)}
            onSuccess={handleSuccess}
          />
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

// ── Public subscribe form with email-check ────────────────────────────────────

interface PublicSubscribeFormProps {
  projectId: string;
  onEmailExists: (email: string) => void;
  onSuccess: (result: { subscription_id?: string }) => void;
}

function PublicSubscribeForm({
  projectId,
  onEmailExists,
  onSuccess,
}: PublicSubscribeFormProps) {
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [notes, setNotes] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errors: Record<string, string> = {};
    if (!email.trim()) errors["email"] = "El correo es obligatorio";
    if (!firstName.trim()) errors["first_name"] = "El nombre es obligatorio";
    if (!lastName.trim()) errors["last_name"] = "El apellido es obligatorio";

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setIsSubmitting(true);
    setApiError(null);

    try {
      const { exists } = await subscriptionApi.publicCheckEmail(email.trim());
      if (exists) {
        onEmailExists(email.trim());
        return;
      }

      const result = await subscriptionApi.publicSubscribe({
        email: email.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        project_id: projectId,
        notes: notes.trim() || undefined,
      });
      onSuccess(result);
    } catch (err: unknown) {
      const msg =
        err instanceof Error
          ? err.message
          : "Error al procesar la suscripción";
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  const inputClass =
    "rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed";

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label
          htmlFor="pf-email"
          className="text-sm font-medium text-gray-700"
        >
          Correo electrónico{" "}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-email"
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors["email"] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors["email"]}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="pf-first-name"
          className="text-sm font-medium text-gray-700"
        >
          Nombre{" "}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-first-name"
          type="text"
          value={firstName}
          onChange={(e) => setFirstName(e.target.value)}
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors["first_name"] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors["first_name"]}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="pf-last-name"
          className="text-sm font-medium text-gray-700"
        >
          Apellido{" "}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-last-name"
          type="text"
          value={lastName}
          onChange={(e) => setLastName(e.target.value)}
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors["last_name"] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors["last_name"]}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label
          htmlFor="pf-notes"
          className="text-sm font-medium text-gray-700"
        >
          Notas (opcional)
        </label>
        <textarea
          id="pf-notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSubmitting}
          className={`${inputClass} resize-y`}
        />
      </div>

      {apiError && (
        <p
          className="text-sm text-red-600 rounded-md bg-red-50 px-3 py-2"
          role="alert"
        >
          {apiError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? "Enviando…" : "Suscribirse"}
      </button>
    </form>
  );
}
