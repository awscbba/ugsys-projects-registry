import type { FormSchema } from '@/types/form';

interface DynamicFormRendererProps {
  schema: FormSchema;
  values: Record<string, string | string[]>;
  onChange: (fieldId: string, value: string | string[]) => void;
  errors?: Record<string, string>;
  disabled?: boolean;
}

const inputClass =
  'rounded-lg border border-white/[0.1] bg-[#252f42] px-3 py-2.5 text-sm text-white/90 ' +
  'focus:border-[#FF9900]/50 focus:outline-none focus:ring-1 focus:ring-[#FF9900]/50 ' +
  'disabled:opacity-50 disabled:cursor-not-allowed transition-colors duration-150';

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
          <div key={field.id} className="flex flex-col gap-1.5">
            <label htmlFor={inputId} className="text-sm font-medium text-white/60">
              {field.question}
              {field.required && (
                <span className="ml-1 text-red-400" aria-hidden="true">
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
                className={inputClass}
              />
            )}

            {field.field_type === 'textarea' && (
              <textarea
                id={inputId}
                rows={4}
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className={`${inputClass} resize-y`}
              />
            )}

            {field.field_type === 'date' && (
              <input
                id={inputId}
                type="date"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className={inputClass}
              />
            )}

            {field.field_type === 'number' && (
              <input
                id={inputId}
                type="number"
                value={typeof value === 'string' ? value : ''}
                onChange={(e) => onChange(field.id, e.target.value)}
                disabled={disabled}
                className={inputClass}
              />
            )}

            {field.field_type === 'poll_single' && (
              <div className="flex flex-col gap-2" role="radiogroup" aria-labelledby={inputId}>
                {(field.options ?? []).map((option) => (
                  <label
                    key={option}
                    className="flex items-center gap-2.5 text-sm text-white/60 cursor-pointer hover:text-white/80 transition-colors"
                  >
                    <input
                      type="radio"
                      name={inputId}
                      value={option}
                      checked={value === option}
                      onChange={() => onChange(field.id, option)}
                      disabled={disabled}
                      className="accent-[#FF9900] focus:ring-[#FF9900]"
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
                      className="flex items-center gap-2.5 text-sm text-white/60 cursor-pointer hover:text-white/80 transition-colors"
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
                        className="accent-[#FF9900] focus:ring-[#FF9900] rounded"
                      />
                      {option}
                    </label>
                  );
                })}
              </div>
            )}

            {error && (
              <p className="text-xs text-red-400" role="alert">
                {error}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}
