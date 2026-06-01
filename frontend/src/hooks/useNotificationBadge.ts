import { useCallback } from "react";
import { useQuery } from "@tanstack/react-query";

const POLL_INTERVAL_MS = 5 * 60 * 1000; // poll mỗi 5 phút

async function fetchImportantSignals(): Promise<any[]> {
  const res = await fetch("/api/alerts/important-signals?hours=24&min_score=2");
  if (!res.ok) return [];
  const data = await res.json();
  return Array.isArray(data) ? data : [];
}

/**
 * Hook trả về số lượng tín hiệu cảnh báo quan trọng (score >= 2) trong 24h.
 * Dùng chung queryKey với useImportantSignals → TanStack Query chỉ gọi API 1 lần.
 */
export function useNewArticleCount() {
  const { data = [] } = useQuery({
    queryKey: ['important-signals'],
    queryFn: fetchImportantSignals,
    refetchInterval: POLL_INTERVAL_MS,
  });
  return data.length;
}

/**
 * Hook trả về danh sách chi tiết các tín hiệu cảnh báo quan trọng.
 * Dùng chung queryKey với useNewArticleCount → TanStack Query chỉ gọi API 1 lần.
 */
export function useImportantSignals(isAuthenticated: boolean) {
  const { data: signals = [], isLoading: loading, refetch } = useQuery({
    queryKey: ['important-signals'],
    queryFn: fetchImportantSignals,
    enabled: isAuthenticated,
    refetchInterval: POLL_INTERVAL_MS,
  });

  return { signals, loading, refresh: refetch };
}

/**
 * Hook trả về map alertId → số bài báo khớp.
 * Dùng để hiển thị badge số trên từng bộ lọc trong AlertsPage.
 */
export function useAlertFeedCounts(alertIds: number[], isAuthenticated: boolean) {
  const [counts, setCounts] = useState<Record<number, number>>({});

  const fetchCounts = useCallback(async () => {
    if (!isAuthenticated || alertIds.length === 0) return;
    const token = localStorage.getItem("token");
    const headers = token ? { Authorization: `Bearer ${token}` } : {};

    const results = await Promise.allSettled(
      alertIds.map((id) =>
        fetch(`/api/alerts/${id}/feed?skip=0&limit=1`, { headers })
          .then((r) => r.json())
          .then((d) => ({ id, total: d.total ?? 0 }))
      )
    );

    const newCounts: Record<number, number> = {};
    for (const r of results) {
      if (r.status === "fulfilled") {
        newCounts[r.value.id] = r.value.total;
      }
    }
    setCounts(newCounts);
  }, [alertIds.join(","), isAuthenticated]);

  useEffect(() => {
    fetchCounts();
  }, [fetchCounts]);

  return counts;
}
