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
      className="inline-flex rounded-lg overflow-hidden border border-white/[0.08] bg-[#1e2738]"
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
            className={`
              flex items-center gap-1.5 px-3 py-2 text-sm font-medium
              transition-all duration-150
              focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[#FF9900]
              ${active
                ? 'bg-[#FF9900] text-[#161d2b] shadow-[0_0_12px_rgba(255,153,0,0.3)]'
                : 'text-white/50 hover:text-white/80 hover:bg-white/[0.05]'
              }
            `}
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
