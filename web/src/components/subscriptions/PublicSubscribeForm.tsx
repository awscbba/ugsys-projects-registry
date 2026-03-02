import type { UsePublicSubscribeResult } from '../../hooks/usePublicSubscribe';

interface PublicSubscribeFormProps extends UsePublicSubscribeResult {
  projectId: string;
}

const inputClass =
  'rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed';

export default function PublicSubscribeForm({
  projectId,
  submit,
  isSubmitting,
  apiError,
  fieldErrors,
}: PublicSubscribeFormProps) {
  async function handleSubmit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const data = new FormData(form);
    await submit(projectId, {
      email: (data.get('email') as string) ?? '',
      firstName: (data.get('firstName') as string) ?? '',
      lastName: (data.get('lastName') as string) ?? '',
      notes: (data.get('notes') as string) ?? '',
    });
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-4">
      <div className="flex flex-col gap-1">
        <label htmlFor="pf-email" className="text-sm font-medium text-gray-700">
          Correo electrónico{' '}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-email"
          name="email"
          type="email"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['email'] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors['email']}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="pf-first-name" className="text-sm font-medium text-gray-700">
          Nombre{' '}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-first-name"
          name="firstName"
          type="text"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['first_name'] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors['first_name']}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="pf-last-name" className="text-sm font-medium text-gray-700">
          Apellido{' '}
          <span className="text-red-500" aria-hidden="true">
            *
          </span>
        </label>
        <input
          id="pf-last-name"
          name="lastName"
          type="text"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['last_name'] && (
          <p className="text-xs text-red-600" role="alert">
            {fieldErrors['last_name']}
          </p>
        )}
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor="pf-notes" className="text-sm font-medium text-gray-700">
          Notas (opcional)
        </label>
        <textarea
          id="pf-notes"
          name="notes"
          rows={3}
          disabled={isSubmitting}
          className={`${inputClass} resize-y`}
        />
      </div>

      {apiError && (
        <p className="text-sm text-red-600 rounded-md bg-red-50 px-3 py-2" role="alert">
          {apiError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
      >
        {isSubmitting ? 'Enviando…' : 'Suscribirse'}
      </button>
    </form>
  );
}
