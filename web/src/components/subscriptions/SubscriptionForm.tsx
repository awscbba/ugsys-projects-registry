import { useState } from 'react';
import type { FormSchema } from '@/types/form';
import DynamicFormRenderer from '@/components/forms/DynamicFormRenderer';
import { subscriptionApi } from '@/services/subscriptionApi';
import { formApi } from '@/services/formApi';
import { useAuth } from '@/hooks/useAuth';

interface SubscriptionFormProps {
  projectId: string;
  formSchema?: FormSchema;
  isAuthenticated: boolean;
  onSuccess: (result: { subscription_id?: string }) => void;
}

const inputClass =
  'rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 placeholder-white/25 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150';

const labelClass = 'text-sm font-medium text-white/60';
const errorClass = 'text-xs text-red-400';

export default function SubscriptionForm({
  projectId,
  formSchema,
  isAuthenticated,
  onSuccess,
}: SubscriptionFormProps) {
  const { user } = useAuth();

  const [notes, setNotes] = useState('');
  const [formValues, setFormValues] = useState<Record<string, string | string[]>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const [email, setEmail] = useState('');
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');

  function handleFieldChange(fieldId: string, value: string | string[]) {
    setFormValues((prev) => ({ ...prev, [fieldId]: value }));
    if (fieldErrors[fieldId]) {
      setFieldErrors((prev) => {
        const next = { ...prev };
        delete next[fieldId];
        return next;
      });
    }
  }

  function validateDynamicFields(): boolean {
    if (!formSchema) return true;
    const errors: Record<string, string> = {};
    for (const field of formSchema.fields) {
      if (!field.required) continue;
      const val = formValues[field.id];
      const isEmpty = val === undefined || val === '' || (Array.isArray(val) && val.length === 0);
      if (isEmpty) {
        errors[field.id] = 'Este campo es obligatorio';
      }
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleAuthenticatedSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!validateDynamicFields()) return;

    setIsSubmitting(true);
    setApiError(null);
    try {
      const sub = await subscriptionApi.subscribe(projectId, notes || undefined);

      if (formSchema && user) {
        await formApi.submitForm(projectId, user.sub, formValues);
      }

      onSuccess({ subscription_id: sub.id });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al procesar la suscripción';
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePublicSubmit(e: React.FormEvent) {
    e.preventDefault();

    const errors: Record<string, string> = {};
    if (!email.trim()) errors['email'] = 'El correo es obligatorio';
    if (!firstName.trim()) errors['first_name'] = 'El nombre es obligatorio';
    if (!lastName.trim()) errors['last_name'] = 'El apellido es obligatorio';

    const dynamicValid = validateDynamicFields();
    if (Object.keys(errors).length > 0) {
      setFieldErrors((prev) => ({ ...prev, ...errors }));
      return;
    }
    if (!dynamicValid) return;

    setIsSubmitting(true);
    setApiError(null);
    try {
      const result = await subscriptionApi.publicSubscribe({
        email: email.trim(),
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        project_id: projectId,
        notes: notes || undefined,
      });
      onSuccess(result);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Error al procesar la suscripción';
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <form
      onSubmit={isAuthenticated ? handleAuthenticatedSubmit : handlePublicSubmit}
      noValidate
      className="flex flex-col gap-4"
    >
      {/* Public-only fields */}
      {!isAuthenticated && (
        <>
          <div className="flex flex-col gap-1.5">
            <label htmlFor="sub-email" className={labelClass}>
              Correo electrónico{' '}
              <span className="text-red-400" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="sub-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors['email'] && (
              <p className={errorClass} role="alert">
                {fieldErrors['email']}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="sub-first-name" className={labelClass}>
              Nombre{' '}
              <span className="text-red-400" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="sub-first-name"
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors['first_name'] && (
              <p className={errorClass} role="alert">
                {fieldErrors['first_name']}
              </p>
            )}
          </div>

          <div className="flex flex-col gap-1.5">
            <label htmlFor="sub-last-name" className={labelClass}>
              Apellido{' '}
              <span className="text-red-400" aria-hidden="true">
                *
              </span>
            </label>
            <input
              id="sub-last-name"
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors['last_name'] && (
              <p className={errorClass} role="alert">
                {fieldErrors['last_name']}
              </p>
            )}
          </div>
        </>
      )}

      {/* Notes */}
      <div className="flex flex-col gap-1.5">
        <label htmlFor="sub-notes" className={labelClass}>
          Notas (opcional)
        </label>
        <textarea
          id="sub-notes"
          rows={3}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          disabled={isSubmitting}
          className={`${inputClass} resize-y`}
        />
      </div>

      {/* Dynamic form fields */}
      {isAuthenticated && formSchema && formSchema.fields.length > 0 && (
        <DynamicFormRenderer
          schema={formSchema}
          values={formValues}
          onChange={handleFieldChange}
          errors={fieldErrors}
          disabled={isSubmitting}
        />
      )}

      {apiError && (
        <p
          className="text-sm text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2"
          role="alert"
        >
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
