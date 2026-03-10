import type { UsePublicSubscribeResult } from '../../hooks/usePublicSubscribe';

interface PublicSubscribeFormProps extends UsePublicSubscribeResult {
  projectId: string;
}

const inputClass =
  'rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 placeholder-white/25 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150';

const labelClass = 'text-sm font-medium text-white/60';
const errorClass = 'text-xs text-red-400';

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
      <div className="flex flex-col gap-1.5">
        <label htmlFor="pf-email" className={labelClass}>
          Correo electrónico <span className="text-red-400" aria-hidden="true">*</span>
        </label>
        <input
          id="pf-email"
          name="email"
          type="email"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['email'] && <p className={errorClass} role="alert">{fieldErrors['email']}</p>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="pf-first-name" className={labelClass}>
          Nombre <span className="text-red-400" aria-hidden="true">*</span>
        </label>
        <input
          id="pf-first-name"
          name="firstName"
          type="text"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['first_name'] && <p className={errorClass} role="alert">{fieldErrors['first_name']}</p>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="pf-last-name" className={labelClass}>
          Apellido <span className="text-red-400" aria-hidden="true">*</span>
        </label>
        <input
          id="pf-last-name"
          name="lastName"
          type="text"
          disabled={isSubmitting}
          className={inputClass}
        />
        {fieldErrors['last_name'] && <p className={errorClass} role="alert">{fieldErrors['last_name']}</p>}
      </div>

      <div className="flex flex-col gap-1.5">
        <label htmlFor="pf-notes" className={labelClass}>
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
        <p className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2" role="alert">
          {apiError}
        </p>
      )}

      <button
        type="submit"
        disabled={isSubmitting}
        className="
          rounded-lg bg-[#FF9900] px-4 py-2.5 text-sm font-semibold text-[#161d2b]
          hover:bg-[#ffb84d] disabled:opacity-50 disabled:cursor-not-allowed
          transition-all duration-150 active:scale-[0.99]
          focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#1e2738]
          shadow-[0_2px_12px_rgba(255,153,0,0.25)]
        "
      >
        {isSubmitting ? 'Enviando…' : 'Suscribirse'}
      </button>
    </form>
  );
}
