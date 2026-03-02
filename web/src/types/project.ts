export type ProjectStatus = 'pending' | 'active' | 'completed' | 'cancelled';
export type SubscriptionStatus = 'pending' | 'active' | 'rejected' | 'cancelled';

export interface ProjectImage {
  image_id: string;
  url: string;
  cloudfront_url: string;
  uploaded_at: string;
}

export interface Project {
  id: string;
  name: string;
  description: string;
  category: string;
  status: ProjectStatus;
  is_enabled: boolean;
  created_by: string;
  current_participants: number;
  max_participants?: number;
  start_date?: string;
  end_date?: string;
  rich_text?: string;
  images?: ProjectImage[];
  created_at: string;
  updated_at: string;
}

export interface Subscription {
  id: string;
  project_id: string;
  person_id: string;
  status: SubscriptionStatus;
  notes?: string;
  created_at: string;
  updated_at: string;
}
