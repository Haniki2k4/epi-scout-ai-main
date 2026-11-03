export const qualityKeys = {
  all: ["quality"] as const,
  samples: (filters: { unlabeled?: boolean; limit?: number } = { unlabeled: true, limit: 30 }) =>
    ["quality", "samples", filters] as const,
  metrics: () => ["quality", "metrics"] as const,
  sources: () => ["quality", "sources"] as const,
  eventPairs: (filters: { limit?: number } = { limit: 20 }) =>
    ["quality", "event-pairs", filters] as const,
};

export const llmEvalKeys = {
  all: ["llm-evaluations"] as const,
  items: (view: "pending" | "processed", search = "", limit = 100) =>
    ["llm-evaluations", "items", { view, search, limit }] as const,
  detail: (id: number) => ["llm-evaluations", "item", id] as const,
  metrics: () => ["llm-evaluations", "metrics"] as const,
  datasetSummary: () => ["llm-evaluations", "dataset", "summary"] as const,
  datasetVersions: () => ["llm-evaluations", "dataset", "versions"] as const,
};

export const keywordKeys = {
  all: ["keywords"] as const,
  diseaseOptions: (params: { limit: number; only_active: boolean } = { limit: 1000, only_active: false }) =>
    ["keywords", "disease-options", params] as const,
};
