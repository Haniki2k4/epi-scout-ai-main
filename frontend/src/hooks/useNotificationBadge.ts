import { useEffect, useState, useCallback } from "react";

const POLL_INTERVAL_MS = 5 * 60 * 1000; // poll mỗi 5 phút

/**
 * Hook trả về số lượng tín hiệu cảnh báo quan trọng (score >= 2) trong 24h.
 */
export function useNewArticleCount() {
  const [count, setCount] = useState<number>(0);

  const fetchSignalsCount = useCallback(async () => {
    try {
      const res = await fetch("/api/alerts/important-signals?hours=24&min_score=2");
      if (!res.ok) return;
      const data = await res.json();
      setCount(Array.isArray(data) ? data.length : 0);
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    fetchSignalsCount();
    const id = setInterval(fetchSignalsCount, POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchSignalsCount]);

  return count;
}

/**
 * Hook trả về danh sách chi tiết các tín hiệu cảnh báo quan trọng.
 */
export function useImportantSignals(isAuthenticated: boolean) {
  const [signals, setSignals] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSignals = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    try {
      const res = await fetch("/api/alerts/important-signals?hours=24&min_score=2");
      if (!res.ok) return;
      const data = await res.json();
      setSignals(Array.isArray(data) ? data : []);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchSignals();
  }, [fetchSignals]);

  return { signals, loading, refresh: fetchSignals };
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
