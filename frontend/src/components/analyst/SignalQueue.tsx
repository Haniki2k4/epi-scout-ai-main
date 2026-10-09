import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowLeft, ExternalLink, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import SignalReviewForm, { type ContextSignal } from "./SignalReviewForm";

const signalLabels: Record<string, string> = {
  unexplained_cluster: "Chùm ca bất thường",
  animal_signal: "Tín hiệu từ động vật",
  environment_signal: "Tín hiệu môi trường",
  field_response: "Ứng phó thực địa",
};
const decisionLabels: Record<string, string> = {
  dismissed: "Bác bỏ tín hiệu",
  monitoring_unknown: "Tiếp tục theo dõi",
  disease_identified: "Đã xác định bệnh",
  ruled_out: "Đã loại trừ",
};
const formatDate = (value: string | null) => value ? new Date(value).toLocaleDateString("vi-VN") : "Chưa rõ ngày";

export default function SignalQueue() {
  const [view, setView] = useState<"pending" | "monitoring">("pending");
  const [items, setItems] = useState<ContextSignal[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [selected, setSelected] = useState<ContextSignal | null>(null);
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const response = await fetch(`/api/context-signals/queue?view=${view}&limit=100`);
      if (!response.ok) throw new Error("Không tải được hàng chờ tín hiệu");
      setItems(await response.json());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được hàng chờ");
    } finally {
      setLoading(false);
    }
  }, [view]);

  const loadSelected = useCallback(async (id: number) => {
    setDetailLoading(true);
    try {
      const response = await fetch(`/api/context-signals/${id}`);
      if (!response.ok) throw new Error("Không tải được chi tiết bài");
      setSelected(await response.json());
      setError("");
    } finally {
      setDetailLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (selectedId === null) {
      setSelected(null);
      return;
    }
    setSelected(null);
    void loadSelected(selectedId).catch((err: Error) => setError(err.message));
  }, [selectedId, loadSelected]);

  return (
    <div className="space-y-5">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex items-start gap-3">
          <Button asChild variant="ghost" size="icon" aria-label="Về hàng đợi tín hiệu"><Link to="/signals"><ArrowLeft className="h-5 w-5" /></Link></Button>
          <div>
            <h1 className="text-2xl font-bold tracking-tight">Tín hiệu theo ngữ cảnh</h1>
            <p className="text-sm text-muted-foreground">Bài trượt cửa từ khóa nhưng có dấu hiệu dịch tễ. NVYT xác minh tín hiệu và bệnh trong cùng một lần duyệt.</p>
          </div>
        </div>
        <Button variant="outline" size="sm" onClick={() => void load()} disabled={loading}><RefreshCw className="mr-2 h-4 w-4" />Làm mới</Button>
      </header>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Lọc hàng chờ">
        <Button type="button" variant={view === "pending" ? "default" : "outline"} onClick={() => { setView("pending"); setSelectedId(null); }} aria-pressed={view === "pending"}>Chờ duyệt</Button>
        <Button type="button" variant={view === "monitoring" ? "default" : "outline"} onClick={() => { setView("monitoring"); setSelectedId(null); }} aria-pressed={view === "monitoring"}>Đang theo dõi</Button>
      </div>
      {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
      <div className="review-layout">
        <Card aria-label="Danh sách bài" className="review-list h-fit">
          <CardHeader><CardTitle className="flex items-center gap-2 text-base">{view === "pending" ? "Bài chờ duyệt" : "Bài đang theo dõi"} <Badge variant="secondary">{items.length}</Badge></CardTitle></CardHeader>
          <CardContent className="space-y-2">
            {loading && <p role="status" className="text-sm text-muted-foreground">Đang tải danh sách...</p>}
            {!loading && items.length === 0 && <p className="py-8 text-center text-sm text-muted-foreground">Chưa có bài trong nhóm này.</p>}
            {!loading && items.map((item) => (
              <button type="button" key={item.article_id} aria-pressed={selectedId === item.article_id}
                onClick={() => setSelectedId(item.article_id)}
                className={`block w-full rounded-lg border p-3 text-left transition-colors hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${selectedId === item.article_id ? "border-primary bg-primary/5" : ""}`}>
                <strong className="mb-2 block text-sm leading-snug">{item.title}</strong>
                <span className="mb-2 block text-xs text-muted-foreground">{item.source || "Nguồn chưa rõ"} · {formatDate(item.published_date)}</span>
                <Badge variant="secondary">{signalLabels[item.signal_type || ""] || "Tín hiệu khác"}</Badge>
              </button>
            ))}
          </CardContent>
        </Card>
        <section aria-label="Chi tiết tín hiệu" className="space-y-4">
          {detailLoading && <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">Đang tải chi tiết...</CardContent></Card>}
          {!detailLoading && !selected && <Card><CardContent className="py-12 text-center text-sm text-muted-foreground">Chọn một bài để xem nguồn, bằng chứng và đưa ra quyết định.</CardContent></Card>}
          {!detailLoading && selected && <>
            <Card>
              <CardHeader className="space-y-3">
                <div className="flex flex-wrap items-center gap-2"><Badge variant="secondary">{signalLabels[selected.signal_type || ""] || "Tín hiệu khác"}</Badge><span className="text-xs text-muted-foreground">{selected.source || "Nguồn chưa rõ"} · {formatDate(selected.published_date)}</span></div>
                <CardTitle className="text-lg leading-snug">{selected.title}</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4 text-sm">
                <a href={selected.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-primary underline">Mở bài gốc <ExternalLink className="h-3.5 w-3.5" /></a>
                {selected.summary && <p className="whitespace-pre-line leading-relaxed">{selected.summary}</p>}
                <div className="space-y-2 rounded-lg bg-muted p-3">
                  <p><strong>Cụm từ khớp:</strong> {selected.matched_phrases.join(", ") || "Chưa có"}</p>
                  <p><strong>Bằng chứng phát hiện:</strong> {selected.evidence_text || "Chưa có"}</p>
                  <p><strong>LLM tham khảo:</strong> {selected.llm_label || "Chưa có"} · {selected.llm_reason || "Chưa có nhận xét"}</p>
                </div>
                {selected.current_review && <p><strong>Quyết định hiện tại:</strong> {decisionLabels[selected.current_review.decision] || selected.current_review.decision} · {selected.current_review.reason}</p>}
                {selected.history && selected.history.length > 0 && <div className="space-y-1">
                  <h3 className="font-semibold">Lịch sử duyệt</h3>
                  <ol className="list-inside list-decimal text-muted-foreground">
                    {selected.history.map((review) => <li key={review.id}>{formatDate(review.reviewed_at)} · {decisionLabels[review.decision] || review.decision} · {review.reason}</li>)}
                  </ol>
                </div>}
              </CardContent>
            </Card>
            <SignalReviewForm key={`${selected.article_id}-${selected.review_version}`} signal={selected}
              onSaved={async () => { setSelectedId(null); setSelected(null); await load(); }}
              onStale={async () => { await loadSelected(selected.article_id); await load(); }} />
          </>}
        </section>
      </div>
    </div>
  );
}

