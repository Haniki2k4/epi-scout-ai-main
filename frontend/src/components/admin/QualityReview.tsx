import { useEffect, useState } from "react";
import { toast } from "sonner";

type Sample = {
  id: number; link: string; title: string; summary: string | null;
  published_date: string | null; passed_stage1: boolean;
};
type Metrics = {
  stage1: {
    precision: number | null; recall: number | null; f1: number | null;
    true_positive: number; false_positive: number; false_negative: number;
    labeled_sample_count: number;
  };
  period_start: string; period_end: string; note: string;
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

type LabelDraft = { disease: string; location: string; eventDate: string; caseValue: string };

export default function QualityReview() {
  const [samples, setSamples] = useState<Sample[]>([]);
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [sources, setSources] = useState<SourceHealth[]>([]);
  const [pairs, setPairs] = useState<Pair[]>([]);
  const [error, setError] = useState("");
  const [drafts, setDrafts] = useState<Record<number, LabelDraft>>({});
  const updateDraft = (id: number, field: keyof LabelDraft, value: string) =>
    setDrafts((current) => ({ ...current, [id]: { disease: "", location: "", eventDate: "", caseValue: "", ...current[id], [field]: value } }));

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

  const label = async (id: number, human_relevant: boolean) => {
    const draft = drafts[id];
    try {
      const response = await fetch(`/api/quality/samples/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ human_relevant, human_disease: draft?.disease || null, human_location: draft?.location || null, human_event_date: draft?.eventDate ? `${draft.eventDate}T00:00:00` : null, human_case_value: draft?.caseValue ? Number(draft.caseValue) : null }),
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
    <div className="space-y-6">
      {error && <p role="alert" className="text-red-600">{error}</p>}
      <section className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">Đánh giá Stage 1</h2>
        <p className="text-sm">Mẫu có nhãn: {metrics?.stage1.labeled_sample_count ?? 0}. Precision: {percent(metrics?.stage1.precision ?? null)} · Recall: {percent(metrics?.stage1.recall ?? null)} · F1: {percent(metrics?.stage1.f1 ?? null)}.</p>
        <p className="text-xs text-muted-foreground">TP {metrics?.stage1.true_positive ?? 0}, FP {metrics?.stage1.false_positive ?? 0}, FN {metrics?.stage1.false_negative ?? 0}. Kỳ {metrics?.period_start?.slice(0, 10)}–{metrics?.period_end?.slice(0, 10)}.</p>
        <p className="text-xs text-muted-foreground">{metrics?.note}</p>
      </section>
      <section className="rounded border p-4 space-y-2">
        <h2 className="font-semibold">LLM và trích xuất</h2>
        <p className="text-sm">LLM, trên mẫu đã qua Stage 1: {metrics?.llm.labeled_sample_count ?? 0} nhãn · Precision {percent(metrics?.llm.precision ?? null)} · Recall {percent(metrics?.llm.recall ?? null)} · F1 {percent(metrics?.llm.f1 ?? null)}.</p>
        {Object.entries(metrics?.field_accuracy ?? {}).map(([name, value]) => (
          <p key={name} className="text-sm">{name}: {percent(value.accuracy)} ({value.correct}/{value.labeled_count} nhãn có bài lưu).</p>
        ))}
        <p className="text-sm">Trung vị từ lúc bài đăng đến lúc tạo tín hiệu: {metrics?.article_to_signal_latency.median_hours?.toFixed(1) ?? "Chưa có"} giờ ({metrics?.article_to_signal_latency.event_count ?? 0} event).</p>
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Gán nhãn mẫu RSS trước bộ lọc từ khóa</h2>
        {samples.length === 0 && <p className="text-sm">Chưa có mẫu cần gán nhãn.</p>}
        {samples.map((sample) => (
          <article key={sample.id} className="rounded border p-3 space-y-2">
            <a href={sample.link} target="_blank" rel="noopener noreferrer" className="text-primary underline font-medium">{sample.title}</a>
            <p className="text-sm">{sample.summary}</p>
            <p className="text-xs">Stage 1: {sample.passed_stage1 ? "qua" : "loại"} · {sample.published_date?.slice(0, 10)}</p>
            <div className="grid gap-2 sm:grid-cols-4">
              <input aria-label="Bệnh đúng" placeholder="Bệnh đúng" value={drafts[sample.id]?.disease || ""} onChange={(event) => updateDraft(sample.id, "disease", event.target.value)} className="rounded border p-2" />
              <input aria-label="Địa bàn đúng" placeholder="Địa bàn đúng" value={drafts[sample.id]?.location || ""} onChange={(event) => updateDraft(sample.id, "location", event.target.value)} className="rounded border p-2" />
              <input aria-label="Ngày sự kiện đúng" type="date" value={drafts[sample.id]?.eventDate || ""} onChange={(event) => updateDraft(sample.id, "eventDate", event.target.value)} className="rounded border p-2" />
              <input aria-label="Số ca đúng" type="number" min="0" placeholder="Số ca đúng" value={drafts[sample.id]?.caseValue || ""} onChange={(event) => updateDraft(sample.id, "caseValue", event.target.value)} className="rounded border p-2" />
            </div>
            <div className="flex gap-2">
              <button type="button" onClick={() => label(sample.id, true)} className="rounded border px-3 py-1 hover:bg-accent">Liên quan</button>
              <button type="button" onClick={() => label(sample.id, false)} className="rounded border px-3 py-1 hover:bg-accent">Không liên quan</button>
            </div>
          </article>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Đánh giá gom event</h2>
        <p className="text-sm">Cặp có nhãn: {metrics?.event_pair.labeled_pair_count ?? 0} · Precision: {percent(metrics?.event_pair.precision ?? null)} · Recall: {percent(metrics?.event_pair.recall ?? null)} · F1: {percent(metrics?.event_pair.f1 ?? null)}.</p>
        {pairs.map((pair) => (
          <div key={`${pair.article_a_id}-${pair.article_b_id}`} className="rounded border p-3 space-y-2">
            <a href={pair.link_a} target="_blank" rel="noopener noreferrer" className="block text-primary underline">{pair.title_a}</a>
            <a href={pair.link_b} target="_blank" rel="noopener noreferrer" className="block text-primary underline">{pair.title_b}</a>
            <p className="text-xs">Hệ thống: {pair.predicted_same_event ? "cùng event" : "khác event"}</p>
            <button type="button" onClick={() => labelPair(pair, true)} className="rounded border px-3 py-1 mr-2">Cùng event</button>
            <button type="button" onClick={() => labelPair(pair, false)} className="rounded border px-3 py-1">Khác event</button>
          </div>
        ))}
      </section>
      <section className="space-y-2">
        <h2 className="font-semibold">Tình trạng nguồn (30 ngày)</h2>
        {sources.length === 0 && <p className="text-sm">Chưa có crawl_runs.</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead><tr><th className="text-left p-2">Nguồn</th><th>Lần quét</th><th>Entry</th><th>Qua Stage 1</th><th>Đã lưu</th><th>Lỗi</th></tr></thead>
            <tbody>{sources.map((source) => (
              <tr key={source.feed_url} className="border-t">
                <td className="p-2 max-w-xs truncate" title={source.feed_url}>{source.feed_url}</td>
                <td className="text-center">{source.runs}</td><td className="text-center">{source.entries_fetched}</td>
                <td className="text-center">{source.entries_passed_stage1}</td><td className="text-center">{source.entries_saved}</td>
                <td className="text-center">{source.error_count}</td>
              </tr>
            ))}</tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
