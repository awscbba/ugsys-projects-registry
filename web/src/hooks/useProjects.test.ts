import { renderHook, act } from '@testing-library/react';
import { describe, it, expect, vi } from 'vitest';
import * as fc from 'fast-check';
import { useProjects } from './useProjects';
import type { IProjectApi } from '../services/ports';
import type { Project } from '../types/project';
import type { PaginatedResponse } from '../types/api';

// Mock httpClient and authService to prevent module-level side effects
vi.mock('../services/httpClient', () => ({
  httpClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), patch: vi.fn(), delete: vi.fn() },
  setRefreshTokenFn: vi.fn(),
}));
vi.mock('../services/authService', () => ({
  authService: { login: vi.fn(), register: vi.fn(), refreshToken: vi.fn() },
}));

// ── Helpers ───────────────────────────────────────────────────────────────────

function makeProject(id: string): Project {
  return {
    id,
    name: `Project ${id}`,
    description: 'desc',
    category: 'Tech',
    status: 'active',
    is_enabled: true,
    created_by: 'user-1',
    current_participants: 0,
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
  };
}

function makePaginatedResponse(items: Project[], total: number): PaginatedResponse<Project> {
  return {
    data: items,
    meta: { page: 1, page_size: items.length, total, total_pages: 1, request_id: 'req-1' },
  };
}

function makeMockApi(overrides: Partial<IProjectApi> = {}): IProjectApi {
  return {
    getPublicProjects: vi
      .fn()
      .mockResolvedValue(makePaginatedResponse([makeProject('p1'), makeProject('p2')], 2)),
    getProject: vi.fn(),
    getProjectEnhanced: vi.fn(),
    ...overrides,
  };
}

// ── Unit tests ────────────────────────────────────────────────────────────────

describe('useProjects', () => {
  it('transitions isLoading from true to false', async () => {
    let resolve!: (r: PaginatedResponse<Project>) => void;
    const pending = new Promise<PaginatedResponse<Project>>((res) => {
      resolve = res;
    });
    const api = makeMockApi({ getPublicProjects: vi.fn().mockReturnValue(pending) });
    const { result } = renderHook(() => useProjects(1, 12, api));

    expect(result.current.isLoading).toBe(true);

    await act(async () => {
      resolve(makePaginatedResponse([], 0));
      await pending;
    });

    expect(result.current.isLoading).toBe(false);
  });

  it('sets projects and total from paginated response on success', async () => {
    const projects = [makeProject('a'), makeProject('b')];
    const api = makeMockApi({
      getPublicProjects: vi.fn().mockResolvedValue(makePaginatedResponse(projects, 10)),
    });
    const { result } = renderHook(() => useProjects(1, 12, api));

    await act(async () => {});

    expect(result.current.projects).toEqual(projects);
    expect(result.current.total).toBe(10);
    expect(result.current.error).toBeNull();
  });

  it('sets error string on API failure', async () => {
    const api = makeMockApi({
      getPublicProjects: vi.fn().mockRejectedValue(new Error('Server error')),
    });
    const { result } = renderHook(() => useProjects(1, 12, api));

    await act(async () => {});

    expect(result.current.error).toBe('Server error');
    expect(result.current.projects).toEqual([]);
  });

  it('calls injected api with correct page and pageSize', async () => {
    const api = makeMockApi();
    renderHook(() => useProjects(3, 6, api));

    await act(async () => {});

    expect(api.getPublicProjects).toHaveBeenCalledWith(3, 6);
  });

  // ── Property 1: useProjects uses injected API ───────────────────────────────
  // Feature: web-frontend-quality, Property 1: useProjects uses injected API
  it('Property 1: for any mock IProjectApi, useProjects calls api.getPublicProjects with given page and pageSize', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.integer({ min: 1, max: 100 }),
        fc.integer({ min: 1, max: 50 }),
        async (page, pageSize) => {
          const api = makeMockApi({
            getPublicProjects: vi.fn().mockResolvedValue(makePaginatedResponse([], 0)),
          });
          renderHook(() => useProjects(page, pageSize, api));

          await act(async () => {});

          expect(api.getPublicProjects).toHaveBeenCalledWith(page, pageSize);
        }
      ),
      { numRuns: 50 }
    );
  });
});
