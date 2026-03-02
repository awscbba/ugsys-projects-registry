export type FieldType = 'text' | 'textarea' | 'poll_single' | 'poll_multiple' | 'date' | 'number';

export interface CustomField {
  id: string;
  field_type: FieldType;
  question: string;
  required: boolean;
  options?: string[];
}

export interface FormSchema {
  fields: CustomField[];
}

export interface FormSubmission {
  id: string;
  project_id: string;
  person_id: string;
  responses: Record<string, string | string[]>;
  submitted_at: string;
}
