const STORAGE_KEY = 'projects_view';

type View = 'grid' | 'list' | 'compact';

interface ViewToggleProps {
  view: View;
  onChange: (v: View) => void;
}

const OPTIONS: { value: View; label: string; icon: string }[] = [
  {
    value: 'grid',
    label: 'Grid',
    icon: 'M3 3h7v7H3V3zm0 11h7v7H3v-7zm11-11h7v7h-7V3zm0 11h7v7h-7v-7z',
  },
  {
    value: 'list',
    label: 'Lista',
    icon: 'M4 6h16M4 12h16M4 18h16',
  },
  {
    value: 'compact',
    label: 'Compacto',
    icon: 'M4 6h16M4 10h16M4 14h16M4 18h16',
  },
];

export function loadSavedView(defaultView: View = 'grid'): View {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'grid' || saved === 'list' || saved === 'compact') {
      return saved;
    }
  } catch {
    // localStorage unavailable
  }
  return defaultView;
}

export default function ViewToggle({ view, onChange }: ViewToggleProps) {
  function handleChange(v: View) {
    try {
      localStorage.setItem(STORAGE_KEY, v);
    } catch {
      // ignore
    }
    onChange(v);
  }

  return (
    <div
      role="group"
      aria-label="Cambiar vista"
      className="inline-flex rounded-md shadow-sm border border-gray-200 overflow-hidden"
    >
      {OPTIONS.map(({ value, label, icon }) => {
        const active = view === value;
        return (
          <button
            key={value}
            type="button"
            aria-pressed={active}
            aria-label={label}
            title={label}
            onClick={() => handleChange(value)}
            className={`flex items-center gap-1 px-3 py-2 text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-inset focus:ring-indigo-500 ${
              active ? 'bg-indigo-600 text-white' : 'bg-white text-gray-600 hover:bg-gray-50'
            }`}
          >
            <svg
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <path d={icon} />
            </svg>
            <span className="hidden sm:inline">{label}</span>
          </button>
        );
      })}
    </div>
  );
}
