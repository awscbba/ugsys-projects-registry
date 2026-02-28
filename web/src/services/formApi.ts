import { httpClient } from "./httpClient";

export const formApi = {
  submitForm(
    projectId: string,
    personId: string,
    responses: Record<string, string | string[]>,
  ): Promise<{ submission_id: string }> {
    return httpClient.post<{ submission_id: string }>(
      "/api/v1/form-submissions",
      { project_id: projectId, person_id: personId, responses },
    );
  },
};
