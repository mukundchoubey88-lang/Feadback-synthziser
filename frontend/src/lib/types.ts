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


// --- Feedback Creation & Classification ---
export type FeedbackCreateInput = {
  product: string;
  feedback_text: string;
  source?: string;
  feature?: string | null;
  app_version?: string | null;
  customer_id?: string | null;
  timestamp?: string | null;
};

export type AspectSentimentDetail = {
  aspect: string;
  sentiment: string;
  sentiment_score: number;
  confidence: number;
  evidence: string;
};

export type FeedbackClassificationDetail = {
  classification_id: string;
  feedback_id: string;
  classification_version: string;
  run_number: number;
  status: string;
  overall_sentiment: string;
  sentiment_score: number;
  sentiment_intensity: string;
  customer_intent: string;
  identified_product?: string | null;
  identified_feature?: string | null;
  topics?: Array<{ label: string; confidence: number }> | null;
  aspects?: AspectSentimentDetail[] | null;
  pain_points?: string[] | null;
  keywords?: string[] | null;
  confidence_score: number;
  needs_review: boolean;
  review_reason?: string | null;
  classified_at: string;
};

// --- Theme Intelligence (Part 7) ---
export type ThemeRepresentativeFeedback = {
  feedback_id: string;
  feedback_text: string;
  similarity_score?: number | null;
};

export type ThemeRecord = {
  theme_id: string;
  product: string;
  theme_name: string;
  description?: string | null;
  category: string;
  status: string;
  created_at: string;
  merged_into_id?: string | null;
  split_from_id?: string | null;
  feedback_count?: number;
  representative_feedback?: ThemeRepresentativeFeedback[];
};

export type ThemeDiscoverResult = {
  product: string;
  candidate_themes_created: number;
  candidates: ThemeRecord[];
  total_feedback_clustered: number;
  silhouette_score?: number | null;
  message: string;
};

// --- Analytics Dashboard (Part 8) ---
export type SentimentBreakdown = {
  positive: number;
  positive_percentage: number;
  negative: number;
  negative_percentage: number;
  neutral: number;
  neutral_percentage: number;
  mixed: number;
  mixed_percentage: number;
};

export type AnalyticsOverview = {
  product?: string | null;
  total_feedback_count: number;
  classified_feedback_count: number;
  unclassified_feedback_count: number;
  sentiment_breakdown: SentimentBreakdown;
  average_sentiment_score?: number | null;
};

export type DailyTrendItem = {
  date: string;
  total_volume: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  mixed_count: number;
  unclassified_count: number;
  average_sentiment_score?: number | null;
};

export type SentimentTrendsResult = {
  product?: string | null;
  daily_trends: DailyTrendItem[];
};

export type AspectSentimentItem = {
  aspect_name: string;
  total_mentions: number;
  positive_mentions: number;
  negative_mentions: number;
  neutral_mentions: number;
  mixed_mentions: number;
  average_sentiment_score?: number | null;
};

export type AspectSentimentResult = {
  product?: string | null;
  aspects: AspectSentimentItem[];
};

export type ThemeAnalyticsItem = {
  theme_id: string;
  theme_name: string;
  category: string;
  status: string;
  feedback_count: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  average_sentiment_score?: number | null;
  sentiment_distribution: Record<string, number>;
};

export type ThemeAnalyticsResult = {
  product?: string | null;
  themes: ThemeAnalyticsItem[];
};

export type CustomerIntentItem = {
  intent: string;
  count: number;
  percentage: number;
  positive_count: number;
  negative_count: number;
  neutral_count: number;
  average_sentiment_score?: number | null;
};

export type CustomerIntentResult = {
  product?: string | null;
  intents: CustomerIntentItem[];
};

export type FeedbackVolumeResult = {
  product?: string | null;
  current_period_count: number;
  previous_period_count: number;
  percentage_change?: number | null;
  trend_direction: string;
};

// --- Memory & Hindsight (Part 9) ---
export type MemoryItem = {
  memory_id?: string | null;
  bank_id: string;
  hindsight_memory_id?: string | null;
  memory_type: string;
  source_entity_type: string;
  source_reference?: string | null;
  content: string;
  context?: string | null;
  created_at?: string | null;
};

export type MemoryStatusResult = {
  configured: boolean;
  available: boolean;
  base_url?: string | null;
  total_synced_memories: number;
  bank_count: number;
};

export type MemorySyncResult = {
  product: string;
  bank_id: string;
  dry_run: boolean;
  synced_count: number;
  skipped_count: number;
  failed_count: number;
  details: Record<string, number>;
  error?: string | null;
};

export type MemoryRecallResult = {
  product: string;
  bank_id: string;
  query: string;
  available: boolean;
  memories: MemoryItem[];
  error?: string | null;
};

export type MemoryReflectResult = {
  product: string;
  bank_id: string;
  query: string;
  available: boolean;
  reasoning?: string | null;
  supporting_memories: MemoryItem[];
  disclaimer: string;
  error?: string | null;
};

// --- Historical Intelligence Agent Q&A (Part 10) ---
export type FeedbackEvidence = {
  feedback_id: string;
  timestamp: string;
  sentiment?: string | null;
  intent?: string | null;
  quote: string;
};

export type ThemeEvidence = {
  theme_id: string;
  theme_name: string;
  category: string;
  status: string;
};

export type ReleaseEvidence = {
  release_id: string;
  version: string;
  release_date: string;
  change_category: string;
  feature?: string | null;
  description: string;
};

export type IntelligenceEvidenceData = {
  feedback_quotes: FeedbackEvidence[];
  themes: ThemeEvidence[];
  releases: ReleaseEvidence[];
  hindsight_memory_refs: string[];
};

export type IntelligenceSQLMetrics = {
  total_feedback: number;
  classified_feedback: number;
  positive_percentage: number;
  negative_percentage: number;
  neutral_percentage: number;
  average_sentiment_score?: number | null;
  pre_post_comparison?: Record<string, any> | null;
  aspect_mentions?: Record<string, number> | null;
};

export type HistoricalIntelligenceResult = {
  product: string;
  question: string;
  answer: string;
  key_findings: string[];
  sql_metrics: IntelligenceSQLMetrics;
  historical_context?: string | null;
  evidence: IntelligenceEvidenceData;
  hindsight_available: boolean;
  limitations: string[];
};
