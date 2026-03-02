import { useState, useEffect } from 'react';
import type { IProjectApi } from '../services/ports';
import type { FormSchema } from '../types/form';
import type { Project } from '../types/project';
import { projectApi } from '../services/projectApi';

export type EnhancedProject = Project & { form_schema?: FormSchema };

export interface UseProjectDetailResult {
  project: EnhancedProject | null;
  isLoading: boolean;
  error: string | null;
}

export function useProjectDetail(
  projectId: string | undefined,
  api: IProjectApi = projectApi
): UseProjectDetailResult {
  const [project, setProject] = useState<EnhancedProject | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let cancelled = false;
    setIsLoading(true);
    setError(null);

    api
      .getProjectEnhanced(projectId)
      .then((data) => {
        if (!cancelled) {
          setProject(data as EnhancedProject);
        }
      })
      .catch((e: unknown) => {
        if (!cancelled) {
          setError(e instanceof Error ? e.message : 'Error al cargar el proyecto');
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [projectId, api]);

  return { project, isLoading, error };
}
