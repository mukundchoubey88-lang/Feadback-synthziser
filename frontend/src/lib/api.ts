import type {
  AnalyticsOverview,
  AspectSentimentResult,
  BatchCleanResult,
  CustomerIntentResult,
  FeedbackClassificationDetail,
  FeedbackCreateInput,
  FeedbackPage,
  FeedbackRecord,
  FeedbackVolumeResult,
  HealthResponse,
  HistoricalIntelligenceResult,
  MemoryRecallResult,
  MemoryReflectResult,
  MemoryStatusResult,
  MemorySyncResult,
  QualityInspection,
  QualitySummary,
  RootInfo,
  SentimentTrendsResult,
  ThemeAnalyticsResult,
  ThemeDiscoverResult,
  ThemeRecord,
  UploadJob,
  UploadResult,
} from "./types";

export const API_BASE = (import.meta.env.VITE_API_BASE ?? "http://127.0.0.1:8000").replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  code?: string;

  constructor(message: string, status: number, code?: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
  }
}

function readError(body: unknown, fallback: string): { message: string; code?: string } {
  if (!body || typeof body !== "object") return { message: fallback };
  const record = body as Record<string, unknown>;
  const error = record.error;
  if (error && typeof error === "object") {
    const err = error as Record<string, unknown>;
    if (typeof err.message === "string") {
      return {
        message: err.message,
        code: typeof err.code === "string" ? err.code : undefined,
      };
    }
  }
  if (typeof record.detail === "string") return { message: record.detail };
  if (Array.isArray(record.detail)) {
    const first = record.detail[0];
    if (first && typeof first === "object" && "msg" in first && typeof first.msg === "string") {
      return { message: first.msg };
    }
  }
  return { message: fallback };
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, init);
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_BASE}. Start the backend with uvicorn and confirm CORS allows this origin.`,
      0,
      "NETWORK",
    );
  }

  if (!response.ok) {
    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    const parsed = readError(body, response.statusText || "Request failed");
    throw new ApiError(parsed.message, response.status, parsed.code);
  }

  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export const client = {
  // --- Root & Health ---
  root: () => api<RootInfo>("/"),
  health: () => api<HealthResponse>("/api/health"),

  // --- Feedback Ingestion & Quality ---
  feedback: (params: { page?: number; page_size?: number; product?: string; source?: string }) => {
    const query = new URLSearchParams();
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.page_size ?? 20));
    if (params.product) query.set("product", params.product);
    if (params.source) query.set("source", params.source);
    return api<FeedbackPage>(`/api/feedback?${query.toString()}`);
  },
  feedbackById: (id: string) => api<FeedbackRecord>(`/api/feedback/${id}`),
  createFeedback: (payload: FeedbackCreateInput) =>
    api<FeedbackRecord>("/api/feedback", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  quality: (id: string) => api<QualityInspection>(`/api/feedback/${id}/quality`),
  qualitySummary: (product?: string) => {
    const query = product ? `?product=${encodeURIComponent(product)}` : "";
    return api<QualitySummary>(`/api/feedback/quality/summary${query}`);
  },
  job: (id: string) => api<UploadJob>(`/api/feedback/jobs/${id}`),
  upload: (file: File) => {
    const body = new FormData();
    body.append("file", file);
    return api<UploadResult>("/api/feedback/upload", { method: "POST", body });
  },
  cleanBatch: (limit = 50) =>
    api<BatchCleanResult>(`/api/feedback/clean?limit=${limit}&reprocess=false`, { method: "POST" }),
  cleanOne: (id: string) => api<FeedbackRecord>(`/api/feedback/${id}/clean`, { method: "POST" }),

  // --- Classification & Sentiment (Part 6) ---
  classification: (feedbackId: string) =>
    api<FeedbackClassificationDetail>(`/api/feedback/${feedbackId}/classification`),
  classifyOne: (feedbackId: string, reprocess = false) =>
    api<FeedbackClassificationDetail>(`/api/feedback/${feedbackId}/classify?reprocess=${reprocess}`, {
      method: "POST",
    }),

  // --- Theme Discovery & Lifecycle (Part 7) ---
  themes: (params?: { product?: string; status?: string; category?: string }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.status) query.set("status", params.status);
    if (params?.category) query.set("category", params.category);
    const qs = query.toString();
    return api<ThemeRecord[]>(`/api/themes${qs ? `?${qs}` : ""}`);
  },
  themeById: (themeId: string) => api<ThemeRecord>(`/api/themes/${themeId}`),
  discoverThemes: (payload: {
    product: string;
    similarity_threshold?: number;
    min_cluster_size?: number;
    batch_size?: number;
    force_recluster?: boolean;
  }) =>
    api<ThemeDiscoverResult>("/api/themes/discover", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  activateTheme: (themeId: string) =>
    api<ThemeRecord>(`/api/themes/${themeId}/activate`, { method: "POST" }),
  discardTheme: (themeId: string) =>
    api<ThemeRecord>(`/api/themes/${themeId}/discard`, { method: "POST" }),
  mergeThemes: (sourceThemeId: string, targetThemeId: string) =>
    api<ThemeRecord>(`/api/themes/${sourceThemeId}/merge`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ target_theme_id: targetThemeId }),
    }),

  // --- Sentiment & Temporal Analytics (Part 8) ---
  analyticsOverview: (params?: { product?: string; days?: number; start_date?: string; end_date?: string }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.days) query.set("days", String(params.days));
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    const qs = query.toString();
    return api<AnalyticsOverview>(`/api/analytics/overview${qs ? `?${qs}` : ""}`);
  },
  sentimentTrends: (params?: { product?: string; days?: number; start_date?: string; end_date?: string }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.days) query.set("days", String(params.days));
    if (params?.start_date) query.set("start_date", params.start_date);
    if (params?.end_date) query.set("end_date", params.end_date);
    const qs = query.toString();
    return api<SentimentTrendsResult>(`/api/analytics/sentiment-trends${qs ? `?${qs}` : ""}`);
  },
  aspectSentiment: (params?: { product?: string; days?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.days) query.set("days", String(params.days));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return api<AspectSentimentResult>(`/api/analytics/aspects${qs ? `?${qs}` : ""}`);
  },
  themeAnalytics: (params?: { product?: string; days?: number; limit?: number }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.days) query.set("days", String(params.days));
    if (params?.limit) query.set("limit", String(params.limit));
    const qs = query.toString();
    return api<ThemeAnalyticsResult>(`/api/analytics/themes${qs ? `?${qs}` : ""}`);
  },
  customerIntents: (params?: { product?: string; days?: number }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.days) query.set("days", String(params.days));
    const qs = query.toString();
    return api<CustomerIntentResult>(`/api/analytics/intents${qs ? `?${qs}` : ""}`);
  },
  feedbackVolume: (params?: { product?: string; period_days?: number }) => {
    const query = new URLSearchParams();
    if (params?.product) query.set("product", params.product);
    if (params?.period_days) query.set("period_days", String(params.period_days));
    const qs = query.toString();
    return api<FeedbackVolumeResult>(`/api/analytics/volume${qs ? `?${qs}` : ""}`);
  },

  // --- Hindsight Persistent Memory (Part 9) ---
  memoryStatus: () => api<MemoryStatusResult>("/api/memory/status"),
  memorySync: (payload: { product: string; dry_run?: boolean }) =>
    api<MemorySyncResult>("/api/memory/sync", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  memoryRecall: (payload: { product: string; query: string; limit?: number }) =>
    api<MemoryRecallResult>("/api/memory/recall", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  memoryReflect: (payload: { product: string; query: string }) =>
    api<MemoryReflectResult>("/api/memory/reflect", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  // --- Historical Memory Intelligence Q&A (Part 10) ---
  askIntelligence: (payload: { product: string; question: string }) =>
    api<HistoricalIntelligenceResult>("/api/intelligence/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
};

export function formatWhen(value: string | null | undefined): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(date);
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return value.toFixed(1);
}
