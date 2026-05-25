import { useEffect, useRef, useState } from "react";
import { AlertTriangle, RefreshCw, Sparkles, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useToast } from "@/components/ui/use-toast";

type SummaryItem = {
  text: string;
  evidence_count: number;
  confidence: "high" | "medium" | "low";
};

type DailySummary = {
  period: string;
  summaries: SummaryItem[];
  recommendations: string[];
  has_alert: boolean;
  message?: string;
};

const confidenceLabel: Record<SummaryItem["confidence"], string> = {
  high: "Cao",
  medium: "Trung bình",
  low: "Thấp",
};

export function AISummaryCard() {
  const { toast } = useToast();
  const [summary, setSummary] = useState<DailySummary | null>(null);
  const [statusMsg, setStatusMsg] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startPolling = () => {
    if (pollRef.current) return;
    pollRef.current = setInterval(async () => {
      try {
        const r2 = await fetch("/api/report/daily-summary");
        const d2 = await r2.json();
        if (d2.status !== "not_ready") {
          setSummary(d2 as DailySummary);
          setStatusMsg(null);
          setRefreshing(false);
          if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
        }
      } catch {
        // ignore polling errors
      }
    }, 5000);
  };

  const loadSummary = async (refresh = false) => {
    refresh ? setRefreshing(true) : setLoading(true);
    setStatusMsg(null);
    try {
      const res = await fetch(refresh ? "/api/report/daily-summary/refresh" : "/api/report/daily-summary", {
        method: refresh ? "POST" : "GET",
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Không thể tải tóm tắt AI");

      if (data.status === "not_ready" && refresh) {
        setStatusMsg("Đang tạo AI summary trong nền...");
        startPolling();
      } else if (data.status === "not_ready") {
        setStatusMsg(data.message || "Chưa có dữ liệu AI summary.");
      } else if (data.status === "started") {
        setStatusMsg("Đang tạo AI summary trong nền...");
        startPolling();
      } else {
        setSummary(data as DailySummary);
      }
    } catch (error) {
      toast({
        title: "Lỗi",
        description: error instanceof Error ? error.message : "Không thể tải tóm tắt AI",
        variant: "destructive",
      });
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    loadSummary();
    return () => { if (pollRef.current) { clearInterval(pollRef.current); } };
  }, []);

  return (
    <Card className="border-l-4 border-l-blue-500">
      <CardHeader className="flex flex-row items-start justify-between gap-4">
        <div>
          <CardTitle className="flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-blue-500" />
            Tóm tắt tình hình nhanh
          </CardTitle>
          <CardDescription>{summary?.period || "Kết quả giám sát 24 giờ gần nhất"}</CardDescription>
        </div>
        <Button variant="outline" size="sm" onClick={() => loadSummary(true)} disabled={refreshing || loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
          Làm mới
        </Button>
      </CardHeader>
      <CardContent className="space-y-4">
        {loading ? (
          <div className="h-20 rounded-md bg-muted animate-pulse" />
        ) : statusMsg ? (
          <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            {statusMsg}
          </div>
        ) : summary?.message ? (
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">{summary.message}</div>
        ) : summary ? (
          <>
            <div className="space-y-3">
              {(summary.summaries || []).map((item, index) => (
                <div key={index} className="rounded-lg border p-3">
                  <div className="mb-2 flex flex-wrap items-center gap-2">
                    <Badge variant={item.confidence === "high" ? "default" : "secondary"}>
                      Độ tin cậy {confidenceLabel[item.confidence] || item.confidence || "Chưa rõ"}
                    </Badge>
                    <Badge variant="outline">{item.evidence_count} nguồn</Badge>
                  </div>
                  <p className="text-sm leading-relaxed text-foreground">{item.text}</p>
                </div>
              ))}
            </div>
            {summary.has_alert && (
              <div className="flex items-center gap-2 rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
                <AlertTriangle className="h-4 w-4 shrink-0" />
                Có tín hiệu cần tiếp tục xác minh từ các nguồn dữ liệu trong ngày.
              </div>
            )}
            <div className="grid gap-2 md:grid-cols-3">
              {(summary.recommendations || []).slice(0, 3).map((item, index) => (
                <div key={index} className="rounded-lg bg-secondary p-3 text-sm text-muted-foreground">
                  {item}
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="rounded-lg border bg-muted/30 p-4 text-sm text-muted-foreground">
            Chưa có dữ liệu AI summary. Nhấn "Làm mới" để tạo.
          </div>
        )}
      </CardContent>
    </Card>
  );
}
