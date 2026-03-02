import type { FormSchema } from '@/types/form';

interface DynamicFormRendererProps {
  schema: FormSchema;
  values: Record<string, string | string[]>;
  onChange: (fieldId: string, value: string | string[]) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}

export default function DynamicFormRenderer({
  schema,
  values,
  onChange,
  errors = {},
  disabled = false,
}: DynamicFormRendererProps) {
  return (
    <div className="flex flex-col gap-4">
      {schema.fields.map((field) => {
        const value = values[field.id];
        const error = errors[field.id];
        const inputId = `field-${field.id}`;

        return (
          <div key={field.id} className="flex flex-col gap-1">
            <label htmlFor={inputId} className="text-sm font-medium text-gray-700">
              {field.question}
              {field.required && (
                <span className="ml-1 text-red-500" aria-hidden="true">
                  *
                </span>
              )}
            </label>

            {field.field_type === 'text' && (
              <input
                id={inputId}
                type="text"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            )}

            {field.field_type === 'textarea' && (
              <textarea
                id={inputId}
                rows={4}
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed resize-y"
              />
            )}

            {field.field_type === 'date' && (
              <input
                id={inputId}
                type="date"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            )}

            {field.field_type === 'number' && (
              <input
                id={inputId}
                type="number"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className="rounded-md border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500 disabled:bg-gray-100 disabled:cursor-not-allowed"
              />
            )}

            {field.field_type === 'poll_single' && (
              <div className="flex flex-col gap-2" role="radiogroup" aria-labelledby={inputId}>
                {(field.options ?? []).map((option) => (
                  <label
                    key={option}
                    className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
                  >
                    <input
                      type="radio"
                      name={inputId}
                      value={option}
                      checked={value === option}
                      onChange={() => onChange(field.id, option)}
                      disabled={disabled}
                      className="text-indigo-600 focus:ring-indigo-500"
                    />
                    {option}
                  </label>
                ))}
              </div>
            )}

            {field.field_type === 'poll_multiple' && (
              <div className="flex flex-col gap-2">
                {(field.options ?? []).map((option) => {
                  const selected = Array.isArray(value) ? value : [];
                  const checked = selected.includes(option);
                  return (
                    <label
                      key={option}
                      className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer"
                    >
                      <input
                        type="checkbox"
                        value={option}
                        checked={checked}
                        onChange={() => {
                          const next = checked
                            ? selected.filter((v) => v !== option)
                            : [...selected, option];
                          onChange(field.id, next);
                        }}
                        disabled={disabled}
                        className="text-indigo-600 focus:ring-indigo-500 rounded"
                      />
                      {option}
                    </label>
                  );
                })}
              </div>
            )}

            {error && (
              <p className="text-xs text-red-600" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
