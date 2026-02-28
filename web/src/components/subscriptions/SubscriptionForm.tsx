import { useState } from "react";
import type { FormSchema } from "@/types/form";
import DynamicFormRenderer from "@/components/forms/DynamicFormRenderer";
import { subscriptionApi } from "@/services/subscriptionApi";
import { formApi } from "@/services/formApi";
import { useAuth } from "@/hooks/useAuth";

interface SubscriptionFormProps {
  projectId: string;
  formSchema?: FormSchema;
  isAuthenticated: boolean;
  onSuccess: (result: { subscription_id?: string }) => void;
}

export default function SubscriptionForm({
  projectId,
  formSchema,
  isAuthenticated,
  onSuccess,
}: SubscriptionFormProps) {
  const { user } = useAuth();

  // Shared state
  const [notes, setNotes] = useState("");
  const [formValues, setFormValues] = useState<Record<string, string | string[]>>({});
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  // Public-only state
  const [email, setEmail] = useState("");
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");

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
      const isEmpty =
        val === undefined ||
        val === "" ||
        (Array.isArray(val) && val.length === 0);
      if (isEmpty) {
        errors[field.id] = "Este campo es obligatorio";
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
      const msg =
        err instanceof Error ? err.message : "Error al procesar la suscripción";
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  async function handlePublicSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Client-side validation
    const errors: Record<string, string> = {};
    if (!email.trim()) errors["email"] = "El correo es obligatorio";
    if (!firstName.trim()) errors["first_name"] = "El nombre es obligatorio";
    if (!lastName.trim()) errors["last_name"] = "El apellido es obligatorio";

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
      const msg =
        err instanceof Error ? err.message : "Error al procesar la suscripción";
      setApiError(msg);
    } finally {
      setIsSubmitting(false);
    }
  }

  const inputClass =
    "rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed";

  return (
    <form
      onSubmit={isAuthenticated ? handleAuthenticatedSubmit : handlePublicSubmit}
      noValidate
      className="flex flex-col gap-4"
    >
      {/* Public-only fields */}
      {!isAuthenticated && (
        <>
          <div className="flex flex-col gap-1">
            <label htmlFor="sub-email" className="text-sm font-medium text-gray-700">
              Correo electrónico <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <input
              id="sub-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors["email"] && (
              <p className="text-xs text-red-600" role="alert">{fieldErrors["email"]}</p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="sub-first-name" className="text-sm font-medium text-gray-700">
              Nombre <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <input
              id="sub-first-name"
              type="text"
              value={firstName}
              onChange={(e) => setFirstName(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors["first_name"] && (
              <p className="text-xs text-red-600" role="alert">{fieldErrors["first_name"]}</p>
            )}
          </div>

          <div className="flex flex-col gap-1">
            <label htmlFor="sub-last-name" className="text-sm font-medium text-gray-700">
              Apellido <span className="text-red-500" aria-hidden="true">*</span>
            </label>
            <input
              id="sub-last-name"
              type="text"
              value={lastName}
              onChange={(e) => setLastName(e.target.value)}
              disabled={isSubmitting}
              className={inputClass}
            />
            {fieldErrors["last_name"] && (
              <p className="text-xs text-red-600" role="alert">{fieldErrors["last_name"]}</p>
            )}
          </div>
        </>
      )}

      {/* Notes (optional, both flows) */}
      <div className="flex flex-col gap-1">
        <label htmlFor="sub-notes" className="text-sm font-medium text-gray-700">
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

      {/* Dynamic form fields (authenticated only) */}
      {isAuthenticated && formSchema && formSchema.fields.length > 0 && (
        <DynamicFormRenderer
          schema={formSchema}
          values={formValues}
          onChange={handleFieldChange}
          errors={fieldErrors}
          disabled={isSubmitting}
        />
      )}

      {/* API error */}
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
        {isSubmitting ? "Enviando…" : "Suscribirse"}
      </button>
    </form>
  );
}
