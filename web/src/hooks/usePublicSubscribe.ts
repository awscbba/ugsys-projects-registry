import { useState } from 'react';
import type { ISubscriptionApi } from '../services/ports';
import { subscriptionApi } from '../services/subscriptionApi';

export interface PublicSubscribeFormData {
  email: string;
  firstName: string;
  lastName: string;
  notes: string;
}

export interface UsePublicSubscribeResult {
  submit: (projectId: string, data: PublicSubscribeFormData) => Promise<void>;
  isSubmitting: boolean;
  apiError: string | null;
  fieldErrors: Record<string, string>;
  emailExistsFor: string | null;
}

export function usePublicSubscribe(
  onSuccess: (result: { subscription_id?: string }) => void,
  api: ISubscriptionApi = subscriptionApi
): UsePublicSubscribeResult {
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [emailExistsFor, setEmailExistsFor] = useState<string | null>(null);

  async function submit(projectId: string, data: PublicSubscribeFormData): Promise<void> {
    // Field validation — no API call if any required field is empty/whitespace
    const errors: Record<string, string> = {};
    if (!data.email.trim()) errors['email'] = 'El correo es obligatorio';
    if (!data.firstName.trim()) errors['first_name'] = 'El nombre es obligatorio';
    if (!data.lastName.trim()) errors['last_name'] = 'El apellido es obligatorio';

    if (Object.keys(errors).length > 0) {
      setFieldErrors(errors);
      return;
    }

    setIsSubmitting(true);
    setApiError(null);
    setFieldErrors({});

    try {
      const { exists } = await api.publicCheckEmail(data.email.trim());
      if (exists) {
        setEmailExistsFor(data.email.trim());
        return;
      }

      const result = await api.publicSubscribe({
        email: data.email.trim(),
        first_name: data.firstName.trim(),
        last_name: data.lastName.trim(),
        project_id: projectId,
        notes: data.notes.trim() || undefined,
      });
      onSuccess(result);
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : 'Error al procesar la suscripción');
    } finally {
      setIsSubmitting(false);
    }
  }

  return { submit, isSubmitting, apiError, fieldErrors, emailExistsFor };
}
