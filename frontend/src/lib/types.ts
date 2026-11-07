export type DependencyStatus = {
  status: string;
  details?: string | null;
};

export type HealthResponse = {
  status: string;
  app_name: string;
  version: string;
  environment: string;
  dependencies: Record<string, DependencyStatus>;
};

export type RootInfo = {
  name: string;
  version: string;
  environment: string;
  docs_url: string;
  status: string;
};

export type FeedbackRecord = {
  feedback_id: string;
  source: string;
  customer_id: string | null;
  feedback_text: string;
  product: string;
  feature: string | null;
  timestamp: string;
  app_version: string | null;
  created_at: string;
  deleted_at: string | null;
  cleaned_feedback_text: string | null;
  quality_status: string;
  quality_score: number | null;
  content_quality_score: number | null;
  metadata_completeness_score: number | null;
  quality_flags: string[] | null;
  pii_detected: boolean;
  pii_types: string[] | null;
  cleaning_version: string | null;
  cleaned_at: string | null;
  processing_status: string;
  processing_error: string | null;
};

export type FeedbackPage = {
  items: FeedbackRecord[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
};

export type UploadResult = {
  job_id: string;
  status: string;
  filename: string;
  total_records: number;
  inserted_records: number;
  duplicate_records: number;
  rejected_records: number;
  errors: Array<Record<string, unknown>> | null;
  message: string;
};

export type UploadJob = {
  job_id: string;
  filename: string;
  format: string;
  status: string;
  total_records: number;
  inserted_records: number;
  rejected_records: number;
  duplicate_records: number;
  error_summary: string | null;
  errors: Array<Record<string, unknown>> | null;
  created_at: string;
  completed_at: string | null;
};

export type BatchCleanResult = {
  total_considered: number;
  processed: number;
  skipped: number;
  clean_count: number;
  flagged_count: number;
  rejected_count: number;
  failed_count: number;
};

export type QualityInspection = {
  feedback_id: string;
  original_feedback_text: string;
  cleaned_feedback_text: string | null;
  quality_status: string;
  quality_score: number | null;
  content_quality_score: number | null;
  metadata_completeness_score: number | null;
  quality_flags: string[] | null;
  pii_detected: boolean;
  pii_types: string[] | null;
  cleaning_version: string | null;
  cleaned_at: string | null;
  processing_status: string;
  processing_error: string | null;
};

export type QualitySummary = {
  total_records: number;
  quality_status_counts: Record<string, number>;
  processing_status_counts: Record<string, number>;
  pii_detected_count: number;
  average_quality_score: number;
  flag_distribution: Record<string, number>;
};
