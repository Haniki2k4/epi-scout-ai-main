import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import DiseaseMultiSelect from "@/components/admin/DiseaseMultiSelect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

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
  llm: { precision: number | null; recall: number | null; f1: number | null; labeled_sample_count: number };
  field_accuracy: Record<string, { accuracy: number | null; correct: number; labeled_count: number }>;
  article_to_signal_latency: { median_hours: number | null; event_count: number };
  event_pair: { precision: number | null; recall: number | null; f1: number | null; labeled_pair_count: number };
};
type SourceHealth = {
  source_id: number | null; feed_url: string; runs: number;
  entries_fetched: number; entries_passed_stage1: number;
  entries_saved: number; error_count: number;
};

type Pair = { article_a_id: number; article_b_id: number; title_a: string; title_b: string; link_a: string; link_b: string; predicted_same_event: boolean };

type LabelDraft = { diseases: string[]; location: string; eventDate: string; caseValue: string };
const emptyDraft: LabelDraft = { diseases: [], location: "", eventDate: "", caseValue: "" };

export default function QualityReview() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<number, LabelDraft>>({});
  const [diseaseOptions, setDiseaseOptions] = useState<string[]>([]);
  const updateDraft = (id: number, field: Exclude<keyof LabelDraft, "diseases">, value: string) =>
    setDrafts((current) => ({ ...current, [id]: { ...(current[id] ?? emptyDraft), [field]: value } }));

  const updateDiseases = (id: number, diseases: string[]) => setDrafts((current) => ({ ...current, [id]: { ...(current[id] ?? emptyDraft), diseases } }));

  const refresh = async () => {
    try {
      const responses = await Promise.all([
        fetch("/api/quality/samples?unlabeled=true&limit=30"),
        fetch("/api/quality/metrics"),
        fetch("/api/quality/sources"),
        fetch("/api/quality/event-pairs/candidates?limit=20"),
      ]);
      if (responses.some((response) => !response.ok)) throw new Error("Không tải được dữ liệu chất lượng");
      const [sampleData, metricData, sourceData, pairData] = await Promise.all(responses.map((response) => response.json()));
      setSamples(sampleData);
      setMetrics(metricData);
      setSources(sourceData);
      setPairs(pairData);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không tải được dữ liệu");
    }
  };
  useEffect(() => { refresh(); }, []);
  useEffect(() => {
    fetch("/api/keywords?limit=1000&only_active=false")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Could not load disease suggestions")))
      .then((rows: Array<{ text: string }>) => setDiseaseOptions(rows.map((row) => row.text)))
      .catch((error: Error) => console.warn(error.message));
  }, []);

  const label = async (id: number, human_relevant: boolean, human_signal_label?: string) => {
    const draft = drafts[id];
    try {
      const response = await fetch(`/api/quality/samples/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ human_relevant, human_signal_label, human_diseases: draft?.diseases || [], human_location: draft?.location || null, human_event_date: draft?.eventDate ? `${draft.eventDate}T00:00:00` : null, human_case_value: draft?.caseValue ? Number(draft.caseValue) : null }),
      });
      if (!response.ok) throw new Error("Không lưu được nhãn");
      toast.success("Đã lưu nhãn");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được nhãn");
    }
  };
  const labelPair = async (pair: Pair, same_event: boolean) => {
    try {
      const response = await fetch("/api/quality/event-pairs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ article_a_id: pair.article_a_id, article_b_id: pair.article_b_id, same_event }),
      });
      if (!response.ok) throw new Error("Không lưu được nhãn cặp bài");
      toast.success("Đã lưu nhãn cặp bài");
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được nhãn");
    }
  };
  const percent = (value: number | null) => value === null ? "Chưa đủ mẫu" : `${(value * 100).toFixed(1)}%`;

  return (
    <div className="space-y-8 text-sm">
      {error && <p role="alert" className="rounded-lg border border-destructive/30 bg-destructive/10 p-4 text-base text-destructive">{error}</p>}

      <Card>
        <CardHeader>
          <CardTitle className="text-xl">Cửa A · lọc theo từ khóa bệnh</CardTitle>
          <p className="text-base text-muted-foreground">Đánh giá nhị phân trên mẫu RSS đã gán nhãn. Chỉ số này là tham khảo cho cửa A.</p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
        <CardHeader><CardTitle className="text-xl">LLM và trích xuất dữ liệu</CardTitle><p className="text-base text-muted-foreground">Đo trên mẫu đã qua bước lọc ban đầu.</p></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <MetricTile label="Mẫu LLM có nhãn" value={metrics?.llm.labeled_sample_count ?? 0} />
            <MetricTile label="Precision" value={percent(metrics?.llm.precision ?? null)} />
            <MetricTile label="Recall" value={percent(metrics?.llm.recall ?? null)} />
            <MetricTile label="F1" value={percent(metrics?.llm.f1 ?? null)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(metrics?.field_accuracy ?? {}).map(([name, value]) => <div key={name} className="rounded-lg border p-4"><p className="font-medium">{fieldLabels[name] || name}</p><p className="mt-1 text-base font-semibold">{percent(value.accuracy)}</p><p className="text-sm text-muted-foreground">{value.correct}/{value.labeled_count} nhãn có bài lưu</p></div>)}
          </div>
          <p className="rounded-lg bg-muted p-4 text-base">Trung vị từ khi đăng bài đến lúc tạo tín hiệu: <strong>{metrics?.article_to_signal_latency.median_hours?.toFixed(1) ?? "Chưa có"} giờ</strong> ({metrics?.article_to_signal_latency.event_count ?? 0} sự kiện).</p>
        </CardContent>
      </Card>

      <section className="space-y-4" aria-labelledby="quality-samples-heading">
        <div><h2 id="quality-samples-heading" className="text-xl font-semibold">Gán nhãn mẫu RSS</h2><p className="mt-1 text-base text-muted-foreground">Mẫu đo chất lượng, không phải hàng chờ NVYT. Với cửa B, gán nhãn cả bài khớp và không khớp detector.</p></div>
        {samples.length === 0 && <Card><CardContent className="py-8 text-center text-base text-muted-foreground">Chưa có mẫu cần gán nhãn.</CardContent></Card>}
        {samples.map((sample) => {
          const isContext = sample.stage1_route === "context" || (sample.stage1_route === "none" && sample.gate_b_evaluated);
          const route = sample.stage1_route === "keyword" ? "Từ khóa" : sample.stage1_route === "context" ? "Ngữ cảnh" : sample.stage1_route === "none" ? "Không khớp" : "Dữ liệu cũ";
          const gateB = sample.gate_b_mode === "shadow" ? "Đo thử" : sample.gate_b_mode === "active" ? "Đang hoạt động" : sample.gate_b_evaluated ? "Đã kiểm tra, không khớp" : "Không áp dụng";
          return <Card key={sample.id}>
            <CardContent className="space-y-4 pt-6">
              <div className="flex flex-wrap gap-3 rounded-lg border bg-muted/40 p-4">
                <div className="min-w-[120px] flex-1"><p className="text-sm text-muted-foreground">Qua cửa A</p><Badge variant={sample.passed_stage1 ? "secondary" : "outline"} className="mt-1 px-3 py-1 text-sm">{sample.passed_stage1 ? "Đạt" : "Không đạt"}</Badge></div>
                <div className="min-w-[120px] flex-1"><p className="text-sm text-muted-foreground">Tuyến xử lý</p><p className="mt-1 text-base font-semibold">{route}</p></div>
                <div className="min-w-[120px] flex-1"><p className="text-sm text-muted-foreground">Ngày đăng</p><p className="mt-1 text-base font-semibold">{formatDate(sample.published_date)}</p></div>
              </div>
              <div className="flex flex-wrap items-center gap-2 text-sm"><Badge variant="outline" className="px-3 py-1 text-sm">Cửa B: {gateB}</Badge>{sample.context_signal_type && <Badge variant="secondary" className="px-3 py-1 text-sm">{signalTypeLabels[sample.context_signal_type] || sample.context_signal_type}</Badge>}</div>
              <a href={sample.link} target="_blank" rel="noopener noreferrer" className="block text-lg font-semibold leading-snug text-primary underline underline-offset-2">{sample.title}</a>
              {sample.summary && <p className="text-base leading-relaxed">{sample.summary}</p>}
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <DiseaseMultiSelect options={diseaseOptions} value={drafts[sample.id]?.diseases || []} onChange={(diseases) => updateDiseases(sample.id, diseases)} />
                <Input aria-label="Địa bàn đúng" placeholder="Địa bàn đúng" value={drafts[sample.id]?.location || ""} onChange={(event) => updateDraft(sample.id, "location", event.target.value)} />
                <Input aria-label="Ngày sự kiện đúng" type="date" value={drafts[sample.id]?.eventDate || ""} onChange={(event) => updateDraft(sample.id, "eventDate", event.target.value)} />
                <Input aria-label="Số ca đúng" type="number" min="0" placeholder="Số ca đúng" value={drafts[sample.id]?.caseValue || ""} onChange={(event) => updateDraft(sample.id, "caseValue", event.target.value)} />
              </div>
              <div className="flex flex-wrap gap-2">
                {isContext ? <>
                  <Button type="button" size="sm" onClick={() => label(sample.id, true, "confirmed_event")}>Ca/ổ dịch thật</Button>
                  <Button type="button" size="sm" variant="secondary" onClick={() => label(sample.id, true, "early_signal")}>Tín hiệu sớm</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => label(sample.id, false, "noise")}>Nhiễu</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => label(sample.id, false, "irrelevant")}>Không liên quan</Button>
                </> : <>
                  <Button type="button" size="sm" onClick={() => label(sample.id, true)}>Liên quan</Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => label(sample.id, false)}>Không liên quan</Button>
                </>}
              </div>
            </CardContent>
          </Card>;
        })}
      </section>

      <Card>
        <CardHeader><CardTitle className="text-xl">Đánh giá gom sự kiện</CardTitle><p className="text-base text-muted-foreground">So sánh quyết định gom bài của hệ thống với nhãn người đánh giá.</p></CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
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
    </div>
  );
}
