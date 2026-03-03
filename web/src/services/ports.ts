import type { PaginatedResponse } from '../types/api';
import type { Project, Subscription } from '../types/project';

export interface IProjectApi {
  getPublicProjects(page?: number, pageSize?: number): Promise<PaginatedResponse<Project>>;
  getProject(id: string): Promise<Project>;
  getProjectEnhanced(id: string): Promise<Project>;
}

export interface ISubscriptionApi {
  subscribe(projectId: string, notes?: string): Promise<Subscription>;
  checkSubscription(
    personId: string,
    projectId: string
  ): Promise<{ exists: boolean; subscription?: Subscription }>;
  getMySubscriptions(personId: string): Promise<Subscription[]>;
  publicCheckEmail(email: string): Promise<{ exists: boolean }>;
  publicSubscribe(data: {
    email: string;
    first_name: string;
    last_name: string;
    project_id: string;
    notes?: string;
  }): Promise<{ subscription_id: string }>;
  publicRegister(data: { email: string; full_name: string; password: string }): Promise<void>;
}
