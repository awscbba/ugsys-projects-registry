import { useState, useEffect } from 'react';
import ViewToggle, { loadSavedView } from '@/components/projects/ViewToggle';
import ProjectGrid from '@/components/projects/ProjectGrid';
import ProjectList from '@/components/projects/ProjectList';
import ProjectCompact from '@/components/projects/ProjectCompact';
import { usePagination } from '@/hooks/usePagination';
import { useProjects } from '@/hooks/useProjects';

type View = 'grid' | 'list' | 'compact';

const PAGE_SIZE = 12;

export default function HomePage() {
  const [view, setView] = useState<View>(() => loadSavedView('grid'));
  const [total, setTotal] = useState(0);

  const { page, totalPages, next, prev } = usePagination(total, PAGE_SIZE);
  const { projects, total: fetchedTotal, isLoading, error } = useProjects(page, PAGE_SIZE);

  useEffect(() => {
    if (fetchedTotal !== total) {
      setTotal(fetchedTotal);
    }
  }, [fetchedTotal, total]);

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 py-10" aria-label="Catálogo de proyectos">
      {/* Page header */}
      <div className="flex items-end justify-between mb-8 gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white/90 tracking-tight">Proyectos</h1>
          {total > 0 && (
            <p className="mt-1 text-sm text-white/40">{total} proyecto{total !== 1 ? 's' : ''} disponibles</p>
          )}
        </div>
        <ViewToggle view={view} onChange={setView} />
      </div>

      {/* Live region */}
      <div aria-live="polite" aria-atomic="true">
        {isLoading && (
          <div className="flex justify-center py-20">
            <div
              className="w-10 h-10 rounded-full border-2 border-[#FF9900]/30 border-t-[#FF9900] animate-spin"
              role="status"
              aria-label="Cargando proyectos"
            />
          </div>
        )}

        {!isLoading && error && (
          <div className="flex flex-col items-center gap-4 py-20 text-center">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="
                rounded-lg bg-[#FF9900] px-5 py-2 text-sm font-semibold text-[#161d2b]
                hover:bg-[#ffb84d] transition-colors duration-150
                focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#161d2b]
              "
            >
              Reintentar
            </button>
          </div>
        )}

        {!isLoading && !error && projects.length === 0 && (
          <div className="flex flex-col items-center gap-3 py-20 text-center">
            <p className="text-white/40 text-sm">No hay proyectos disponibles</p>
          </div>
        )}

        {!isLoading && !error && projects.length > 0 && (
          <>
            {view === 'grid' && <ProjectGrid projects={projects} />}
            {view === 'list' && <ProjectList projects={projects} />}
            {view === 'compact' && <ProjectCompact projects={projects} />}

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-10">
                <button
                  type="button"
                  onClick={prev}
                  disabled={page === 1}
                  className="
                    rounded-lg border border-white/[0.1] px-5 py-2 text-sm font-medium text-white/60
                    hover:border-white/20 hover:text-white/80 hover:bg-white/[0.04]
                    disabled:opacity-30 disabled:cursor-not-allowed
                    transition-all duration-150
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#161d2b]
                  "
                  aria-label="Página anterior"
                >
                  ← Anterior
                </button>
                <span className="text-sm text-white/35 tabular-nums">
                  {page} / {totalPages}
                </span>
                <button
                  type="button"
                  onClick={next}
                  disabled={page === totalPages}
                  className="
                    rounded-lg border border-white/[0.1] px-5 py-2 text-sm font-medium text-white/60
                    hover:border-white/20 hover:text-white/80 hover:bg-white/[0.04]
                    disabled:opacity-30 disabled:cursor-not-allowed
                    transition-all duration-150
                    focus:outline-none focus-visible:ring-2 focus-visible:ring-[#FF9900] focus-visible:ring-offset-2 focus-visible:ring-offset-[#161d2b]
                  "
                  aria-label="Página siguiente"
                >
                  Siguiente →
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
