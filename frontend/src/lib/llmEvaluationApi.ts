import { apiFetch, ApiError } from "@/lib/apiClient";

export type Revision = {
  revision_number: number;
  created_at: string;
  reason: string;
  new_ground_truth: { human_label?: string };
  previous_ground_truth: { human_label?: string };
};

export type Run = {
  id: number;
  status: string;
  llm_label?: string | null;
  llm_reason?: string | null;
  model_id: string;
  provider: string;
  prompt_version: string;
  route: string;
  input_keywords: string[];
  latency_ms?: number | null;
  error_code?: string | null;
};

export type Item = {
  id: number;
  canonical_url?: string | null;
  title_snapshot: string;
  summary_snapshot: string;
  human_label?: string | null;
  human_signal_label?: string | null;
  human_diseases?: string[] | null;
  human_location?: string | null;
  human_event_date?: string | null;
  human_case_observations?: Array<Record<string, unknown>> | null;
  review_status: string;
  eligible_for_training: boolean;
  label_revision: number;
  current_inference_run_id?: number | null;
  current_run?: Run | null;
};

export type Metrics = {
  reviewed_count: number;
  precision: number | null;
  selective_recall: number | null;
  end_to_end_recall: number | null;
  f1: number | null;
  coverage: number | null;
  abstention_rate: number | null;
  confusion_matrix: Record<string, Record<string, number>>;
  provider: {
    total: number;
    status_counts: Record<string, number>;
    success_rate: number | null;
    fallback_count: number;
    fallback_rate: number | null;
    latency_p50_ms: number | null;
    latency_p95_ms: number | null;
  };
  extraction?: Record<string, { correct: number; total: number; accuracy: number | null }>;
};

export type DatasetSummary = { eligible_count: number; label_distribution: Record<string, number> };
export type DatasetVersion = { id: number; version: string; status: string; sample_count: number };
export type ItemList = { items: Item[]; total: number };

export const llmApi = {
  detail: (id: number, signal?: AbortSignal) =>
    apiFetch<Item & { revisions: Revision[] }>(`/api/llm-evaluations/items/${id}`, { signal }),
  metrics: (signal?: AbortSignal) => apiFetch<Metrics>("/api/llm-evaluations/metrics", { signal }),
  items: (reviewStatus: "pending" | "processed" = "pending", search = "", signal?: AbortSignal) => {
    const params = new URLSearchParams({ limit: "100", review_status: reviewStatus });
    if (search.trim()) params.set("search", search.trim());
    return apiFetch<ItemList>(`/api/llm-evaluations/items?${params.toString()}`, { signal });
  },
  label: (id: number, body: object) => apiFetch<Item>(`/api/llm-evaluations/items/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  retry: (id: number, body: object = {}) => apiFetch<Run>(`/api/llm-evaluations/items/${id}/retry`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  summary: (signal?: AbortSignal) => apiFetch<DatasetSummary>("/api/llm-evaluations/dataset/summary", { signal }),
  versions: (signal?: AbortSignal) => apiFetch<DatasetVersion[]>("/api/llm-evaluations/dataset/versions", { signal }),
  create: (body: object) => apiFetch<DatasetVersion>("/api/llm-evaluations/dataset/versions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }),
  freeze: (id: number) => apiFetch<DatasetVersion>(`/api/llm-evaluations/dataset/versions/${id}/freeze`, { method: "POST" }),
  download: async (id: number, format: "jsonl" | "csv" | "excel" = "jsonl") => {
    const response = await fetch(`/api/llm-evaluations/dataset/versions/${id}/export?format=${format}`);
    if (!response.ok) throw new ApiError("Không thể tải dataset", response.status);
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `dataset-${id}.${format === "excel" ? "xlsx" : format}`;
    anchor.click();
    URL.revokeObjectURL(url);
  },
};
