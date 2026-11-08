export class ApiError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly data?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

export const isApiError = (error: unknown): error is ApiError => error instanceof ApiError;

export async function apiFetch<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, init);
  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body: unknown = await response.json();
      if (body && typeof body === "object") {
        const record = body as Record<string, unknown>;
        detail = record.detail ?? record.message ?? body;
      } else {
        detail = body;
      }
    } catch {
      // Error bodies are not always JSON; statusText is the fallback.
    }

    const rawDetail = typeof detail === "string" ? detail : JSON.stringify(detail) ?? "";
    const message = rawDetail.trim() || response.statusText || "Yêu cầu thất bại";
    throw new ApiError(message, response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const fetchDiseaseOptions = async (signal?: AbortSignal): Promise<string[]> => {
  const rows = await apiFetch<Array<{ text: string }>>(
    "/api/keywords?limit=1000&only_active=false",
    { signal },
  );
  return rows.map((row) => row.text);
};
