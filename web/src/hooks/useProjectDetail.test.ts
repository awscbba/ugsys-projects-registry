import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import * as fc from 'fast-check';
import { useProjectDetail } from './useProjectDetail';
import type { IProjectApi } from '../services/ports';
import type { Project } from '../types/project';

// Mock httpClient and authService to prevent module-level side effects
vi.mock('../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../services/authService', () => ({
  authService: { login: vi.fn(), register: vi.fn(), refreshToken: vi.fn() },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeProject(overrides: Partial<Project> = {}): Project {
  return {
    id: 'proj-1',
    name: 'Test Project',
    description: 'A test project',
    category: 'Tech',
    status: 'active',
    is_enabled: true,
    created_by: 'user-1',
    current_participants: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeMockApi(overrides: Partial<IProjectApi> = {}): IProjectApi {
  return {
    getPublicProjects: vi.fn(),
    getProject: vi.fn(),
    getProjectEnhanced: vi.fn().mockResolvedValue(makeProject()),
    ...overrides,
  };
}

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('useProjectDetail', () => {
  it('isLoading is true during fetch and false after', async () => {
    let resolve!: (p: Project) => void;
    const pending = new Promise<Project>((res) => {
      resolve = res;
    });
    const api = makeMockApi({ getProjectEnhanced: vi.fn().mockReturnValue(pending) });
    const { result } = renderHook(() => useProjectDetail('proj-1', api));

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolve(makeProject());
      await pending;
    });

    expect(result.current.isLoading).toBe(false);
  });

  it('returns the resolved project with error null on success', async () => {
    const project = makeProject({ id: 'proj-42', name: 'My Project' });
    const api = makeMockApi({ getProjectEnhanced: vi.fn().mockResolvedValue(project) });
    const { result } = renderHook(() => useProjectDetail('proj-42', api));

    await act(async () => {});

    expect(result.current.project).toEqual(project);
    expect(result.current.error).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('sets error string on API failure and project is null', async () => {
    const api = makeMockApi({
      getProjectEnhanced: vi.fn().mockRejectedValue(new Error('Not found')),
    });
    const { result } = renderHook(() => useProjectDetail('proj-1', api));

    await act(async () => {});

    expect(result.current.error).toBe('Not found');
    expect(result.current.project).toBeNull();
    expect(result.current.isLoading).toBe(false);
  });

  it('does not update state after unmount (cancelled flag)', async () => {
    let resolve!: (p: Project) => void;
    const pending = new Promise<Project>((res) => {
      resolve = res;
    });
    const api = makeMockApi({ getProjectEnhanced: vi.fn().mockReturnValue(pending) });
    const { result, unmount } = renderHook(() => useProjectDetail('proj-1', api));

    // isLoading starts true (fetch in flight)
    expect(result.current.isLoading).toBe(true);

    unmount();

    await act(async () => {
      resolve(makeProject());
      await pending;
    });

    // After unmount, state is frozen at the pre-unmount snapshot:
    // isLoading was true when unmounted, cancelled flag prevents setIsLoading(false)
    expect(result.current.project).toBeNull();
    // isLoading remains true — the finally block's setIsLoading(false) was cancelled
    expect(result.current.isLoading).toBe(true);
  });

  // ── Property 2: useProjectDetail data flow ──────────────────────────────────
  // Feature: web-frontend-quality, Property 2: useProjectDetail data flow
  it('Property 2: for any projectId and mock api, getProjectEnhanced is called and project returned on success', async () => {
    await fc.assert(
      fc.asyncProperty(fc.uuid(), async (projectId) => {
        const project = makeProject({ id: projectId });
        const api = makeMockApi({ getProjectEnhanced: vi.fn().mockResolvedValue(project) });
        const { result } = renderHook(() => useProjectDetail(projectId, api));

        await act(async () => {});

        expect(api.getProjectEnhanced).toHaveBeenCalledWith(projectId);
        expect(result.current.project).toEqual(project);
        expect(result.current.isLoading).toBe(false);
        expect(result.current.error).toBeNull();
      }),
      { numRuns: 50 }
    );
  });
});
