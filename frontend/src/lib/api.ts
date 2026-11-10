import type {
  BatchCleanResult,
  FeedbackPage,
  FeedbackRecord,
  HealthResponse,
  QualityInspection,
  QualitySummary,
  RootInfo,
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
  root: () => api<RootInfo>("/"),
  health: () => api<HealthResponse>("/api/health"),
  feedback: (params: { page?: number; page_size?: number; product?: string; source?: string }) => {
    const query = new URLSearchParams();
    query.set("page", String(params.page ?? 1));
    query.set("page_size", String(params.page_size ?? 20));
    if (params.product) query.set("product", params.product);
    if (params.source) query.set("source", params.source);
    return api<FeedbackPage>(`/api/feedback?${query.toString()}`);
  },
  feedbackById: (id: string) => api<FeedbackRecord>(`/api/feedback/${id}`),
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
