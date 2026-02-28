import { useState, useEffect } from "react";
import ViewToggle, { loadSavedView } from "@/components/projects/ViewToggle";
import ProjectGrid from "@/components/projects/ProjectGrid";
import ProjectList from "@/components/projects/ProjectList";
import ProjectCompact from "@/components/projects/ProjectCompact";
import { usePagination } from "@/hooks/usePagination";
import { useProjects } from "@/hooks/useProjects";

type View = "grid" | "list" | "compact";

const PAGE_SIZE = 12;

export default function HomePage() {
  const [view, setView] = useState<View>(() => loadSavedView("grid"));
  const [total, setTotal] = useState(0);

  const { page, totalPages, next, prev } = usePagination(total, PAGE_SIZE);
  const { projects, total: fetchedTotal, isLoading, error } = useProjects(
    page,
    PAGE_SIZE,
  );

  useEffect(() => {
    if (fetchedTotal !== total) {
      setTotal(fetchedTotal);
    }
  }, [fetchedTotal, total]);

  return (
    <main
      className="max-w-7xl mx-auto px-4 py-8"
      aria-label="Catálogo de proyectos"
    >
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Proyectos</h1>
        <ViewToggle view={view} onChange={setView} />
      </div>

      {/* Live region for loading / error / content */}
      <div aria-live="polite" aria-atomic="true">
        {isLoading && (
          <div className="flex justify-center py-16">
            <div
              className="w-10 h-10 rounded-full border-4 border-indigo-600 border-t-transparent animate-spin"
              role="status"
              aria-label="Cargando proyectos"
            />
          </div>
        )}

        {!isLoading && error && (
          <div className="flex flex-col items-center gap-4 py-16 text-center">
            <p className="text-red-600">{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="rounded-md bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
            >
              Reintentar
            </button>
          </div>
        )}

        {!isLoading && !error && projects.length === 0 && (
          <p className="text-center text-gray-500 py-16">
            No hay proyectos disponibles
          </p>
        )}

        {!isLoading && !error && projects.length > 0 && (
          <>
            {view === "grid" && <ProjectGrid projects={projects} />}
            {view === "list" && <ProjectList projects={projects} />}
            {view === "compact" && <ProjectCompact projects={projects} />}

            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-4 mt-8">
                <button
                  type="button"
                  onClick={prev}
                  disabled={page === 1}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  aria-label="Página anterior"
                >
                  Anterior
                </button>
                <span className="text-sm text-gray-600">
                  Página {page} de {totalPages}
                </span>
                <button
                  type="button"
                  onClick={next}
                  disabled={page === totalPages}
                  className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                  aria-label="Página siguiente"
                >
                  Siguiente
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </main>
  );
}
