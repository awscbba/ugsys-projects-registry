export interface PaginatedMeta {
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
  request_id: string;
}

export interface ApiResponse<T> {
  data: T;
  meta: { request_id: string };
}

export interface PaginatedResponse<T> {
  data: T[];
  meta: PaginatedMeta;
}

export interface ApiError {
  error: string;
  message: string;
  data?: Record<string, unknown>;
}
