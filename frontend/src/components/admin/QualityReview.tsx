import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Check, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import DiseaseMultiSelect from "@/components/admin/DiseaseMultiSelect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch, fetchDiseaseOptions } from "@/lib/apiClient";
import { keywordKeys, qualityKeys } from "@/lib/queryKeys";

const signalTypeLabels: Record<string, string> = { unexplained_cluster: "Chùm ca bất thường", animal_signal: "Tín hiệu từ động vật", environment_signal: "Tín hiệu môi trường", field_response: "Ứng phó thực địa" };
const scanStatusLabels: Record<string, string> = { completed: "Hoàn tất", running: "Đang chạy", failed: "Thất bại" };
const fieldLabels: Record<string, string> = {
  disease: "Bệnh", location: "Địa bàn", event_date: "Ngày sự kiện",
  case_value: "Số ca", disease_name: "Bệnh", case_count: "Số ca",
};
const formatDate = (value: string | null | undefined, withTime = false) =>
  value ? new Date(value).toLocaleString("vi-VN", withTime ? { dateStyle: "short", timeStyle: "short" } : { dateStyle: "short" }) : "Chưa có";
function MetricTile({ label, value }: { label: string; value: string | number }) {
  return <div className="rounded-lg border bg-muted/30 p-4"><p className="text-sm text-muted-foreground">{label}</p><p className="mt-1 text-xl font-semibold">{value}</p></div>;
}
type Sample = {
  id: number; link: string; title: string; summary: string | null;
  published_date: string | null; passed_stage1: boolean;
  stage1_route: string | null; gate_b_mode: string | null; gate_b_evaluated: boolean | null;
  context_signal_type: string | null;
};
type Metrics = {
  stage1: {
    precision: number | null; recall: number | null; f1: number | null;
    true_positive: number; false_positive: number; false_negative: number;
    labeled_sample_count: number;
  };
  period_start: string; period_end: string; note: string;
  scan_status: { current: string | null; is_stale: boolean };
  gate_b: { candidates_total: number; eligible_entries_total: number; active_processed_total: number;
    based_on_completed_at: string | null; by_type: Record<string, number>; detector: { precision: number | null; recall: number | null; true_positive: number; false_positive: number; false_negative: number; matched_labeled: number; unmatched_labeled: number };
    active_llm: { precision: number | null; labeled_count: number } };
  article_to_signal_latency: { median_hours: number | null; event_count: number };
  event_pair: { precision: number | null; recall: number | null; f1: number | null; labeled_pair_count: number };
};
type SourceHealth = {
  source_id: number | null; feed_url: string; runs: number;
  entries_fetched: number; entries_passed_stage1: number;
  entries_saved: number; error_count: number;
};

type Pair = { article_a_id: number; article_b_id: number; title_a: string; title_b: string; link_a: string; link_b: string; predicted_same_event: boolean };
type SampleDraft = { keywords: string[] };
const emptySampleDraft: SampleDraft = { keywords: [] };

export default function QualityReview() {
  const [params, setParams] = useSearchParams();
  const section = ["review", "results", "sources"].includes(params.get("section") ?? "") ? params.get("section")! : "review";
  const queryClient = useQueryClient();
  const [sampleQueueTab, setSampleQueueTab] = useState<"related" | "unmatched">("related");
  const [selectedSampleId, setSelectedSampleId] = useState<number | null>(null);
  const [sampleDrafts, setSampleDrafts] = useState<Record<number, SampleDraft>>({});
  const [savingId, setSavingId] = useState<number | null>(null);
  const samplesQuery = useQuery({
    queryKey: qualityKeys.samples(),
    queryFn: ({ signal }) => apiFetch<Sample[]>("/api/quality/samples?unlabeled=true&limit=30", { signal }),
    staleTime: 45_000,
    enabled: section === "review",
  });
  const pairsQuery = useQuery({
    queryKey: qualityKeys.eventPairs(),
    queryFn: ({ signal }) => apiFetch<Pair[]>("/api/quality/event-pairs/candidates?limit=20", { signal }),
    staleTime: 45_000,
    enabled: section === "review",
  });
  const keywordOptionsQuery = useQuery({
    queryKey: keywordKeys.diseaseOptions(),
    queryFn: ({ signal }) => fetchDiseaseOptions(signal),
    staleTime: 600_000,
    enabled: section === "review",
  });
  const metricsQuery = useQuery({
    queryKey: qualityKeys.metrics(),
    queryFn: ({ signal }) => apiFetch<Metrics>("/api/quality/metrics", { signal }),
    staleTime: 120_000,
    enabled: section === "results" || section === "sources",
  });
  const sourcesQuery = useQuery({
    queryKey: qualityKeys.sources(),
    queryFn: ({ signal }) => apiFetch<SourceHealth[]>("/api/quality/sources", { signal }),
    staleTime: 180_000,
    enabled: section === "sources",
  });
  const samples = samplesQuery.data ?? [];
  const relatedSamples = samples.filter((sample) => sample.passed_stage1);
  const unmatchedSamples = samples.filter((sample) => !sample.passed_stage1);
  const activeQueueSamples = sampleQueueTab === "related" ? relatedSamples : unmatchedSamples;
  const pairs = pairsQuery.data ?? [];
  const metrics = metricsQuery.data ?? null;
  const sources = sourcesQuery.data ?? [];
  const keywordOptions = keywordOptionsQuery.data ?? [];
  const selectedSample = activeQueueSamples.find((sample) => sample.id === selectedSampleId) ?? activeQueueSamples[0];
  const sampleMutation = useMutation({
    mutationFn: ({ id, human_relevant, keywords }: {
      id: number; human_relevant: boolean; keywords: string[]; tokenAtStart: string | null;
    }) => apiFetch<unknown>(`/api/quality/samples/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ human_relevant, human_diseases: keywords }),
    }),
    onSuccess: (_result, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      queryClient.setQueryData<Sample[]>(qualityKeys.samples(), (current) => current?.filter((sample) => sample.id !== variables.id) ?? []);
      queryClient.invalidateQueries({ queryKey: qualityKeys.metrics() });
    },
  });
  const pairMutation = useMutation({
    mutationFn: ({ pair, same_event }: { pair: Pair; same_event: boolean; tokenAtStart: string | null }) =>
      apiFetch<unknown>("/api/quality/event-pairs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ article_a_id: pair.article_a_id, article_b_id: pair.article_b_id, same_event }),
      }),
    onSuccess: (_result, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      queryClient.setQueryData<Pair[]>(qualityKeys.eventPairs(), (current) => current?.filter((pair) =>
        pair.article_a_id !== variables.pair.article_a_id || pair.article_b_id !== variables.pair.article_b_id,
      ) ?? []);
      queryClient.invalidateQueries({ queryKey: qualityKeys.metrics() });
    },
  });

  const label = async (id: number, human_relevant: boolean) => {
    const tokenAtStart = localStorage.getItem("token");
    setSavingId(id);
    try {
      await sampleMutation.mutateAsync({ id, human_relevant, keywords: sampleDrafts[id]?.keywords ?? [], tokenAtStart });
      if (localStorage.getItem("token") === tokenAtStart) toast.success("Đã lưu nhãn");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không lưu được nhãn");
    } finally { setSavingId(null); }
  };
  const labelPair = async (pair: Pair, same_event: boolean) => {
    const tokenAtStart = localStorage.getItem("token");
    try {
      await pairMutation.mutateAsync({ pair, same_event, tokenAtStart });
      if (localStorage.getItem("token") === tokenAtStart) toast.success("Đã lưu nhãn cặp bài");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Không lưu được nhãn cặp bài");
    }
  };
  const isLoading = section === "review"
    ? samplesQuery.isLoading || pairsQuery.isLoading
    : section === "results"
      ? metricsQuery.isLoading
      : metricsQuery.isLoading || sourcesQuery.isLoading;
  const activeError = section === "review"
    ? samplesQuery.error ?? pairsQuery.error
    : section === "results"
      ? metricsQuery.error
      : metricsQuery.error ?? sourcesQuery.error;
  const retryActiveQueries = () => {
    if (section === "review") {
      void samplesQuery.refetch();
      void pairsQuery.refetch();
    } else if (section === "results") {
      void metricsQuery.refetch();
    } else {
      void metricsQuery.refetch();
      void sourcesQuery.refetch();
    }
  };
  const percent = (value: number | null) => value === null ? "Chưa đủ mẫu" : `${(value * 100).toFixed(1)}%`;

  return (
    <div className="space-y-8 text-sm">
      {isLoading && <p role="status">Đang tải dữ liệu…</p>}
      {activeError && <Button variant="outline" onClick={retryActiveQueries}>Thử lại</Button>}
      {activeError && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-base text-destructive">{activeError instanceof Error ? activeError.message : "Không tải được dữ liệu"}</p>}

      <Tabs value={section} onValueChange={value => setParams(current => { current.set("section", value); return current; })}>
      <TabsList className="h-auto flex flex-wrap justify-start"><TabsTrigger value="review">Hàng đợi đánh giá</TabsTrigger><TabsTrigger value="results">Kết quả Stage 1</TabsTrigger><TabsTrigger value="sources">Thống kê và lỗi nguồn</TabsTrigger></TabsList>
      <TabsContent value="results" className="quality-results">
      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Cửa A · lọc theo từ khóa bệnh</CardTitle>
          <p className="text-base text-muted-foreground">Đánh giá nhị phân trên mẫu RSS đã gán nhãn. Chỉ số này là tham khảo cho cửa A.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="metric-grid">
            <MetricTile label="Mẫu có nhãn" value={metrics?.stage1.labeled_sample_count ?? 0} />
            <MetricTile label="Precision" value={percent(metrics?.stage1.precision ?? null)} />
            <MetricTile label="Recall" value={percent(metrics?.stage1.recall ?? null)} />
            <MetricTile label="F1" value={percent(metrics?.stage1.f1 ?? null)} />
          </div>
          <p className="text-sm text-muted-foreground">Đúng dương (TP): {metrics?.stage1.true_positive ?? 0} · Sai dương (FP): {metrics?.stage1.false_positive ?? 0} · Bỏ sót (FN): {metrics?.stage1.false_negative ?? 0}</p>
          <p className="text-sm text-muted-foreground">Kỳ đánh giá: {formatDate(metrics?.period_start)} – {formatDate(metrics?.period_end)}. {metrics?.note}</p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Cửa B · phát hiện theo ngữ cảnh</CardTitle>
          <p className="text-base text-muted-foreground">Đo trên các bài RSS trượt cửa A. Số ứng viên thể hiện lưu lượng, không phải độ chính xác.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center gap-3 text-sm">
            <Badge variant={metrics?.scan_status.current === "completed" ? "secondary" : "outline"} className="px-3 py-1 text-sm">Lần quét: {scanStatusLabels[metrics?.scan_status.current || ""] || "Chưa có"}</Badge>
            {metrics?.scan_status.is_stale && <Badge variant="outline" className="px-3 py-1 text-sm">Dữ liệu quá 2 giờ</Badge>}
            <span className="text-muted-foreground">Hoàn tất: {formatDate(metrics?.gate_b.based_on_completed_at, true)}</span>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <MetricTile label="Ứng viên / bài đủ điều kiện" value={`${metrics?.gate_b.candidates_total ?? 0} / ${metrics?.gate_b.eligible_entries_total ?? 0}`} />
            <MetricTile label="Đưa sang bước LLM" value={metrics?.gate_b.active_processed_total ?? 0} />
            <MetricTile label="Mẫu đã gán nhãn" value={(metrics?.gate_b.detector.matched_labeled ?? 0) + (metrics?.gate_b.detector.unmatched_labeled ?? 0)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-lg border p-4"><h3 className="font-semibold">Detector</h3><p className="mt-2 text-base">Precision: <strong>{percent(metrics?.gate_b.detector.precision ?? null)}</strong> · Recall: <strong>{percent(metrics?.gate_b.detector.recall ?? null)}</strong></p><p className="mt-2 text-sm text-muted-foreground">TP {metrics?.gate_b.detector.true_positive ?? 0} · FP {metrics?.gate_b.detector.false_positive ?? 0} · FN {metrics?.gate_b.detector.false_negative ?? 0}</p></div>
            <div className="rounded-lg border p-4"><h3 className="font-semibold">LLM cửa B khi Active</h3><p className="mt-2 text-base">Precision: <strong>{percent(metrics?.gate_b.active_llm.precision ?? null)}</strong></p><p className="mt-2 text-sm text-muted-foreground">{metrics?.gate_b.active_llm.labeled_count ?? 0} mẫu có nhãn</p></div>
          </div>
          <p className="text-sm text-muted-foreground">Mẫu khớp: {metrics?.gate_b.detector.matched_labeled ?? 0} · Mẫu không khớp: {metrics?.gate_b.detector.unmatched_labeled ?? 0}. Cần gán nhãn cả hai nhóm để đánh giá bỏ sót; thiếu mẫu không khớp thì recall để trống.</p>
          <p className="text-sm text-muted-foreground">Theo loại: {Object.entries(metrics?.gate_b.by_type ?? {}).map(([name, count]) => `${signalTypeLabels[name] || name}: ${count}`).join(" · ") || "Chưa có dữ liệu"}</p>
          <p className="text-sm text-muted-foreground">“Đưa sang bước LLM” không đồng nghĩa request LLM đã thành công. Chỉ cộng từ các lần quét hoàn tất.</p>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="flex flex-wrap items-center justify-between gap-3 pt-6">
          <div>
            <p className="text-lg font-semibold">Phân tích Stage 2 đã được hợp nhất</p>
            <p className="text-base text-muted-foreground">Xem confusion matrix, trích xuất, provider và dataset tại trang Đánh giá LLM.</p>
          </div>
          <Button asChild><a href="/admin/quality/stage-2">Mở Đánh giá LLM</a></Button>
        </CardContent>
      </Card>

      </TabsContent><TabsContent value="review">
      <section className="space-y-4" aria-labelledby="quality-samples-heading">
        <div><h2 id="quality-samples-heading" className="text-xl font-semibold">Gán nhãn mẫu RSS</h2><p className="mt-1 text-base text-muted-foreground">Đọc bài và xác nhận tuyến Stage 1. Cửa B có thêm nhãn tín hiệu ngữ cảnh.</p></div>
        {!isLoading && samples.length === 0 && <Card><CardContent className="py-8 text-center text-base text-muted-foreground">Chưa có mẫu cần gán nhãn.</CardContent></Card>}
        {samples.length > 0 && <div className="review-layout">
          <aside aria-label="Bài viết chờ đánh giá" className="review-list rounded-lg border bg-card p-3">
            <Tabs value={sampleQueueTab} onValueChange={(value) => {
              const nextTab = value as "related" | "unmatched";
              setSampleQueueTab(nextTab);
              const nextSamples = nextTab === "related" ? relatedSamples : unmatchedSamples;
              setSelectedSampleId(nextSamples[0]?.id ?? null);
            }}>
              <TabsList className="grid h-auto w-full grid-cols-2">
                <TabsTrigger value="related">Liên quan · {relatedSamples.length}</TabsTrigger>
                <TabsTrigger value="unmatched">Không khớp · {unmatchedSamples.length}</TabsTrigger>
              </TabsList>
              {[{ value: "related", title: "Liên quan", items: relatedSamples }, { value: "unmatched", title: "Không khớp", items: unmatchedSamples }].map(({ value, title, items }) => <TabsContent key={value} value={value} aria-label={`Tuyến ${title}`} className="space-y-2">
                {items.length === 0 ? <p className="px-2 py-3 text-sm text-muted-foreground">Không có bài chờ đánh giá.</p> : items.map((sample) => <button key={sample.id} type="button" className="queue-option" aria-pressed={selectedSample?.id === sample.id} disabled={savingId !== null} onClick={() => setSelectedSampleId(sample.id)}>
                <span className="block text-sm font-medium leading-relaxed">{sample.title}</span>
                <span className="mt-2 block text-xs text-muted-foreground">{formatDate(sample.published_date)} · {sample.stage1_route === "context" ? "Cửa B" : "Cửa A"}</span>
              </button>)}
              </TabsContent>)}
            </Tabs>
          </aside>
          <section aria-label="Xem và gán nhãn mẫu">
        {activeQueueSamples.length === 0 && <Card><CardContent className="py-10 text-center"><p className="font-medium">Không có bài trong tuyến này</p><p className="mt-1 text-sm text-muted-foreground">Chọn tab còn lại để xem các bài đang chờ.</p></CardContent></Card>}
        {(selectedSample ? [selectedSample] : []).map((sample) => {
          const route = sample.stage1_route === "keyword" ? "Từ khóa" : sample.stage1_route === "context" ? "Ngữ cảnh" : sample.stage1_route === "none" ? "Không khớp" : "Dữ liệu cũ";
          const gateB = sample.gate_b_mode === "shadow" ? "Đo thử" : sample.gate_b_mode === "active" ? "Đang hoạt động" : sample.gate_b_evaluated ? "Đã kiểm tra, không khớp" : "Không áp dụng";
          return <Card key={sample.id}>
            <CardContent className="space-y-6 p-5 sm:p-7">
              <div className="flex flex-wrap items-center gap-2 border-b pb-4">
                <Badge variant={sample.passed_stage1 ? "secondary" : "outline"} className="px-3 py-1.5">Cửa A · {sample.passed_stage1 ? "Đạt" : "Không đạt"}</Badge>
                <Badge variant="outline" className="px-3 py-1.5">Tuyến · {route}</Badge>
                {sample.stage1_route === "context" || sample.gate_b_evaluated ? <Badge variant="outline" className="px-3 py-1.5">Cửa B · {gateB}</Badge> : null}
                {sample.context_signal_type && <Badge variant="secondary" className="px-3 py-1.5">{signalTypeLabels[sample.context_signal_type] || sample.context_signal_type}</Badge>}
                <span className="ml-auto text-sm text-muted-foreground">Đăng {formatDate(sample.published_date)}</span>
              </div>
              <article className="space-y-3">
                <a href={sample.link} target="_blank" rel="noopener noreferrer" className="block text-xl font-semibold leading-snug text-foreground decoration-primary decoration-2 underline-offset-4 hover:text-primary hover:underline sm:text-2xl">{sample.title}</a>
                {sample.summary ? <p className="rounded-lg bg-muted/40 px-4 py-3 text-base leading-7 text-muted-foreground">{sample.summary}</p> : <p className="rounded-lg bg-muted/40 px-4 py-3 text-sm text-muted-foreground">Bài viết chưa có mô tả. Mở bài gốc để xem nội dung đầy đủ.</p>}
              </article>
              <div className="space-y-3 rounded-xl border bg-muted/20 p-4 sm:p-5">
                <div>
                  <p className="font-semibold">Từ khóa đúng</p>
                  <p className="mt-1 text-sm text-muted-foreground">Chọn từ khóa mô tả chính xác nội dung bài viết.</p>
                </div>
                <DiseaseMultiSelect itemLabel="từ khóa" options={keywordOptions} value={sampleDrafts[sample.id]?.keywords ?? []}
                  onChange={(keywords) => setSampleDrafts((current) => ({ ...current, [sample.id]: { keywords } }))} />
              </div>
              <fieldset disabled={savingId !== null} className="grid grid-cols-1 gap-3 border-t pt-5 sm:grid-cols-2">
                <Button type="button" className="h-11 justify-center gap-2" onClick={() => label(sample.id, true)}><Check className="h-4 w-4" />Liên quan</Button>
                <Button type="button" className="h-11 justify-center gap-2" variant="outline" onClick={() => label(sample.id, false)}><X className="h-4 w-4" />Không khớp</Button>
              </fieldset>
            </CardContent>
          </Card>;
        })}
          </section>
        </div>}
      </section>
      </TabsContent><TabsContent value="sources" className="space-y-6">

      <Card>
        <CardHeader><CardTitle className="text-xl">Đánh giá gom sự kiện</CardTitle><p className="text-base text-muted-foreground">So sánh quyết định gom bài của hệ thống với nhãn người đánh giá.</p></CardHeader>
        <CardContent className="space-y-4">
          <div className="metric-grid">
            <MetricTile label="Cặp có nhãn" value={metrics?.event_pair.labeled_pair_count ?? 0} />
            <MetricTile label="Precision" value={percent(metrics?.event_pair.precision ?? null)} />
            <MetricTile label="Recall" value={percent(metrics?.event_pair.recall ?? null)} />
            <MetricTile label="F1" value={percent(metrics?.event_pair.f1 ?? null)} />
          </div>
          {pairs.length === 0 && <p className="py-4 text-base text-muted-foreground">Chưa có cặp bài cần đánh giá.</p>}
          {pairs.map((pair) => <div key={`${pair.article_a_id}-${pair.article_b_id}`} className="space-y-3 rounded-lg border p-4">
            <Badge variant="outline" className="px-3 py-1 text-sm">Hệ thống: {pair.predicted_same_event ? "Cùng sự kiện" : "Khác sự kiện"}</Badge>
            <div className="space-y-2 text-base"><a href={pair.link_a} target="_blank" rel="noopener noreferrer" className="block font-medium text-primary underline">{pair.title_a}</a><a href={pair.link_b} target="_blank" rel="noopener noreferrer" className="block font-medium text-primary underline">{pair.title_b}</a></div>
            <div className="flex flex-wrap gap-2"><Button type="button" size="sm" onClick={() => labelPair(pair, true)}>Cùng sự kiện</Button><Button type="button" size="sm" variant="outline" onClick={() => labelPair(pair, false)}>Khác sự kiện</Button></div>
          </div>)}
        </CardContent>
      </Card>

      <Card>
        <CardHeader><CardTitle className="text-xl">Tình trạng nguồn RSS · 30 ngày</CardTitle></CardHeader>
        <CardContent>
          {sources.length === 0 ? <p className="text-base text-muted-foreground">Chưa có lượt crawl được ghi nhận.</p> : <div className="overflow-x-auto">
            <table className="w-full min-w-[650px] border-collapse text-sm">
              <thead className="bg-muted/60"><tr><th scope="col" className="p-3 text-left">Nguồn RSS</th><th scope="col" className="p-3 text-right">Lần quét</th><th scope="col" className="p-3 text-right">Bài lấy</th><th scope="col" className="p-3 text-right">Qua cửa A</th><th scope="col" className="p-3 text-right">Đã lưu</th><th scope="col" className="p-3 text-right">Lỗi</th></tr></thead>
              <tbody>{sources.map((source) => <tr key={source.feed_url} className="border-b last:border-0">
                <td className="max-w-xs break-all p-3" title={source.feed_url}>{source.feed_url}</td><td className="p-3 text-right">{source.runs}</td><td className="p-3 text-right">{source.entries_fetched}</td><td className="p-3 text-right">{source.entries_passed_stage1}</td><td className="p-3 text-right">{source.entries_saved}</td><td className="p-3 text-right">{source.error_count}</td>
              </tr>)}</tbody>
            </table>
          </div>}
        </CardContent>
      </Card>
      </TabsContent></Tabs>
    </div>
  );
}
