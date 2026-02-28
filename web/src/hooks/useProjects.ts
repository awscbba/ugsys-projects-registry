import { useState, useEffect } from "react";
import type { Project } from "@/types/project";
import { projectApi } from "@/services/projectApi";

export function useProjects(page: number, pageSize = 12) {
  const [projects, setProjects] = useState<Project[]>([]);
  const [total, setTotal] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    projectApi
      .getPublicProjects(page, pageSize)
      .then((res) => {
        if (!cancelled) {
          setProjects(res.data);
          setTotal(res.meta.total);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          const msg =
            e instanceof Error ? e.message : "Error al cargar proyectos";
          setError(msg);
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [page, pageSize]);

  return { projects, total, isLoading, error };
}
