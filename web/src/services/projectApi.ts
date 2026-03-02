import type { PaginatedResponse } from '../types/api';
import type { Project } from '../types/project';
import { httpClient } from './httpClient';

export const projectApi = {
  getPublicProjects(page = 1, pageSize = 12): Promise<PaginatedResponse<Project>> {
    // Use getRaw — the endpoint returns the full { data, meta } envelope with pagination info.
    // httpClient.get() would unwrap it and lose meta.total/page/total_pages.
    return httpClient.getRaw<PaginatedResponse<Project>>(
      `/api/v1/projects/public?page=${page}&page_size=${pageSize}`
    );
  },

  getProject(id: string): Promise<Project> {
    return httpClient.get<Project>(`/api/v1/projects/${id}`);
  },

  getProjectEnhanced(id: string): Promise<Project> {
    return httpClient.get<Project>(`/api/v1/projects/${id}/enhanced`);
  },
};
