import type { Subscription } from "../types/project";
import { httpClient } from "./httpClient";

export const subscriptionApi = {
  subscribe(
    projectId: string,
    notes?: string,
  ): Promise<Subscription> {
    return httpClient.post<Subscription>(
      `/api/v1/projects/${projectId}/subscriptions`,
      notes !== undefined ? { notes } : undefined,
    );
  },

  checkSubscription(
    personId: string,
    projectId: string,
  ): Promise<{ exists: boolean; subscription?: Subscription }> {
    return httpClient.post<{ exists: boolean; subscription?: Subscription }>(
      "/api/v1/subscriptions/check",
      { personId, projectId },
    );
  },

  getMySubscriptions(personId: string): Promise<Subscription[]> {
    return httpClient.get<Subscription[]>(
      `/api/v1/subscriptions/person/${personId}`,
    );
  },

  publicCheckEmail(email: string): Promise<{ exists: boolean }> {
    return httpClient.post<{ exists: boolean }>(
      "/api/v1/public/check-email",
      { email },
    );
  },

  publicSubscribe(data: {
    email: string;
    first_name: string;
    last_name: string;
    project_id: string;
    notes?: string;
  }): Promise<{ subscription_id: string }> {
    return httpClient.post<{ subscription_id: string }>(
      "/api/v1/public/subscribe",
      data,
    );
  },

  publicRegister(data: {
    email: string;
    full_name: string;
    password: string;
  }): Promise<void> {
    return httpClient.post<void>("/api/v1/public/register", data);
  },
};
