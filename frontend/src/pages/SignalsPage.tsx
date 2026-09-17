import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";

type SignalStatus = "pending_review" | "under_verification" | "monitoring" | "verified_event" | "rejected" | "closed";
type QueueItem = {
  id: number;
  title: string;
  disease: string;
  location: string | null;
  event_date: string;
  status: SignalStatus;
  article_count: number;
  source_count: number;
  priority: number;
};
type Observation = {
  id: number;
  report_period_start: string | null;
  report_period_end: string | null;
  disease_name: string;
  reported_value: number | null;
  case_type: string | null;
  count_scope: string | null;
  location: string | null;
  evidence_quote: string | null;
  data_quality: string | null;
};
type SignalDetail = QueueItem & {
  case_count: number | null;
  articles: Array<{
    id: number;
    title: string;
    link: string;
    source: string | null;
    published_date: string;
    summary: string | null;
    observations: Observation[];
  }>;
  history: Array<{
    actor_id: number;
    old_status: string | null;
    new_status: string;
    reason: string | null;
    notes: string | null;
    created_at: string;
  }>;
};

const statuses: Array<{ value: SignalStatus; label: string }> = [
  { value: "under_verification", label: "Đang xác minh" },
  { value: "monitoring", label: "Theo dõi thêm" },
  { value: "verified_event", label: "Sự kiện đã xác minh" },
  { value: "rejected", label: "Bác bỏ" },
  { value: "closed", label: "Kết thúc theo dõi" },
];

export default function SignalsPage() {
  const [queue, setQueue] = useState<QueueItem[]>([]);
  const [queueFilter, setQueueFilter] = useState<SignalStatus | "active">("active");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [detail, setDetail] = useState<SignalDetail | null>(null);
  const [status, setStatus] = useState<SignalStatus>("monitoring");
  const [reason, setReason] = useState("");
  const [notes, setNotes] = useState("");
  const [source, setSource] = useState("");
  const [caseObservationId, setCaseObservationId] = useState("");
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [mergeTarget, setMergeTarget] = useState("");
  const [splitIds, setSplitIds] = useState<number[]>([]);

  const loadQueue = async () => {
    const response = await fetch(queueFilter === "active" ? "/api/signals" : `/api/signals?status=${queueFilter}`);
    if (!response.ok) throw new Error("Không tải được hàng đợi tín hiệu");
    setQueue(await response.json());
  };
  useEffect(() => {
    loadQueue().catch((err: Error) => setError(err.message));
  }, [queueFilter]);
  useEffect(() => {
    if (selectedId === null) return;
    setDetail(null);
    fetch(`/api/signals/${selectedId}`)
      .then((response) => {
        if (!response.ok) throw new Error("Không tải được bằng chứng");
        return response.json();
      })
      .then((data: SignalDetail) => {
        setDetail(data);
        setError("");
      })
      .catch((err: Error) => setError(err.message));
  }, [selectedId]);

  const submit = async () => {
    if (selectedId === null) return;
    if (!reason.trim()) {
      setError("Cần ghi lý do cho quyết định này");
      return;
    }
    if (status === "verified_event" && !source.trim()) {
      setError("Cần nguồn xác minh");
      return;
    }
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/signals/${selectedId}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          status,
          reason: reason.trim(),
          notes: notes.trim() || null,
          verification_source: status === "verified_event" ? source.trim() : null,
          reported_case_count: status === "verified_event" && caseObservationId !== "" ? detail?.articles.flatMap((article) => article.observations).find((observation) => observation.id === Number(caseObservationId))?.reported_value : null,
          case_observation_id: status === "verified_event" && caseObservationId !== "" ? Number(caseObservationId) : null,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Không lưu được quyết định");
      }
      await loadQueue();
      setSelectedId(null);
      setDetail(null);
      setReason("");
      setNotes("");
      setSource("");
      setCaseObservationId("");
      toast.success("Đã lưu quyết định và nhật ký");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được quyết định");
    } finally {
      setSaving(false);
    }
  };

  const reorganize = async (kind: "merge" | "split") => {
    if (selectedId === null || !reason.trim()) {
      setError("Cần chọn tín hiệu và nhập lý do gộp/tách");
      return;
    }
    setSaving(true);
    try {
      const body = kind === "merge"
        ? { target_event_id: Number(mergeTarget), reason: reason.trim() }
        : { article_ids: splitIds, reason: reason.trim() };
      const response = await fetch(`/api/signals/${selectedId}/${kind}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.detail || "Không gộp/tách được tín hiệu");
      }
      await loadQueue();
      setSelectedId(null);
      setDetail(null);
      setSplitIds([]);
      setMergeTarget("");
      toast.success("Đã gộp/tách và ghi nhật ký");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không gộp/tách được tín hiệu");
    } finally {
      setSaving(false);
    }
  };
  return (
    <main className="max-w-7xl mx-auto p-6 space-y-5">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Hàng đợi tín hiệu dịch tễ</h1>
          <p className="text-sm text-muted-foreground">Thông tin báo chí chưa được xác minh là sự kiện bệnh truyền nhiễm.</p>
        </div>
        <Link to="/" className="text-primary underline">Về trang chính</Link>
      </div>
      {error && <p role="alert" className="text-red-600">{error}</p>}
      <div className="grid gap-5 md:grid-cols-[320px_1fr]">
        <section aria-label="Danh sách tín hiệu" className="space-y-2">
          <label className="block text-sm">Lọc trạng thái
            <select value={queueFilter} onChange={(event) => { setQueueFilter(event.target.value as SignalStatus | "active"); setSelectedId(null); }} className="mt-1 block w-full rounded border p-2">
              <option value="active">Cần xử lý</option>
              <option value="verified_event">Đã xác minh</option>
              <option value="rejected">Đã bác bỏ</option>
              <option value="closed">Đã kết thúc</option>
            </select>
          </label>
          {queue.length === 0 && <p>Không có tín hiệu cần xử lý.</p>}
          {queue.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => { setSelectedId(item.id); setStatus("monitoring"); setReason(""); setNotes(""); setSource(""); setCaseObservationId(""); setSplitIds([]); }}
              className="block w-full rounded border p-3 text-left hover:bg-accent focus-visible:ring-2 focus-visible:ring-primary"
              aria-pressed={selectedId === item.id}
            >
              <strong className="block">{item.title}</strong>
              <span className="text-sm text-muted-foreground">{item.location || "Chưa rõ địa bàn"} · {item.article_count} bài · {item.source_count} nguồn</span>
              <span className="block text-xs">Trạng thái: {item.status} · Ưu tiên: {item.priority}</span>
            </button>
          ))}
        </section>
        <section aria-label="Bằng chứng và quyết định" className="space-y-4">
          {!selectedId && <p>Chọn một tín hiệu để xem nguồn, số liệu và nhật ký.</p>}
          {selectedId && !detail && <p>Đang tải bằng chứng...</p>}
          {detail && (
            <>
              <div className="rounded border p-4">
                <h2 className="text-xl font-semibold">{detail.title}</h2>
                <p className="text-sm">Bệnh: {detail.disease} · Địa bàn: {detail.location || "chưa rõ"} · Trạng thái: {detail.status}</p>
                <p className="text-sm">Số ca được xác minh: {detail.case_count ?? "—"}</p>
              </div>
              <div className="space-y-3">
                <h3 className="font-semibold">Bài báo và chứng cứ</h3>
                {detail.articles.map((article) => (
                  <article key={article.id} className="rounded border p-4">
                    <a href={article.link} target="_blank" rel="noopener noreferrer" className="font-medium text-primary underline">{article.title}</a>
                    <p className="text-xs text-muted-foreground">{article.source} · {article.published_date?.slice(0, 10)}</p>
                    <p className="mt-2 text-sm">{article.summary}</p>
                    {article.observations.map((observation, index) => (
                      <div key={index} className="mt-2 rounded bg-muted p-2 text-sm">
                        <p>{observation.disease_name}: {observation.reported_value ?? "—"} · {observation.case_type || "chưa rõ loại"} · {observation.count_scope || "chưa rõ kỳ"}</p>
                        <p>Địa bàn: {observation.location || "chưa rõ"} · Chất lượng: {observation.data_quality || "mới"}</p>
                        <p>Trích dẫn trong tiêu đề/tóm tắt: {observation.evidence_quote || "Chưa có"}</p>
                      </div>
                    ))}
                  </article>
                ))}
              </div>
              <div className="rounded border p-4 space-y-3">
                <h3 className="font-semibold">Ghi quyết định</h3>
                <label className="block text-sm">Trạng thái
                  <select value={status} onChange={(event) => setStatus(event.target.value as SignalStatus)} className="mt-1 block w-full rounded border p-2">
                    {statuses.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}
                  </select>
                </label>
                <label className="block text-sm">Lý do
                  <textarea value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 block w-full rounded border p-2" maxLength={500} />
                </label>
                <label className="block text-sm">Ghi chú
                  <textarea value={notes} onChange={(event) => setNotes(event.target.value)} className="mt-1 block w-full rounded border p-2" />
                </label>
                {status === "verified_event" && (
                  <>
                    <label className="block text-sm">Nguồn xác minh
                      <input value={source} onChange={(event) => setSource(event.target.value)} className="mt-1 block w-full rounded border p-2" />
                    </label>
                    <label className="block text-sm">Số ca đã đối soát (chọn chứng cứ; để trống nếu chưa đủ căn cứ)
                      <select value={caseObservationId} onChange={(event) => setCaseObservationId(event.target.value)} className="mt-1 block w-full rounded border p-2">
                        <option value="">Chưa ghi số ca xác nhận</option>
                        {detail.articles.flatMap((article) => article.observations).filter((observation) =>
                          observation.case_type === "confirmed" && observation.count_scope === "cumulative" &&
                          observation.report_period_start && observation.report_period_end &&
                          observation.evidence_quote && observation.location && observation.data_quality === null &&
                          observation.reported_value !== null
                        ).map((observation) => <option key={observation.id} value={observation.id}>
                          #{observation.id}: {observation.reported_value} ca · {observation.location} · {observation.report_period_end?.slice(0, 10)}
                        </option>)}
                      </select>
                    </label>                  </>
                )}
                <button type="button" disabled={saving} onClick={submit} className="rounded bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50">
                  {saving ? "Đang lưu..." : "Lưu quyết định"}
                </button>
              </div>
              <div className="rounded border p-4 space-y-3">
                <h3 className="font-semibold">Gộp hoặc tách cụm</h3>
                <p className="text-sm">Dùng lý do trong ô “Lý do” ở trên. Event đã xác minh phải mở lại trước khi đổi cụm.</p>
                <label className="block text-sm">ID event đích để gộp
                  <input type="number" min="1" value={mergeTarget} onChange={(event) => setMergeTarget(event.target.value)} className="mt-1 block w-full rounded border p-2" />
                </label>
                <button type="button" disabled={saving || !mergeTarget} onClick={() => reorganize("merge")} className="rounded border px-3 py-1 disabled:opacity-50">Gộp vào event đích</button>
                <fieldset>
                  <legend className="text-sm">Chọn một phần bài báo để tách thành event mới</legend>
                  {detail.articles.map((article) => (
                    <label key={article.id} className="block text-sm">
                      <input type="checkbox" checked={splitIds.includes(article.id)} onChange={(event) =>
                        setSplitIds((ids) => event.target.checked ? [...ids, article.id] : ids.filter((id) => id !== article.id))
                      } /> {article.title}
                    </label>
                  ))}
                </fieldset>
                <button type="button" disabled={saving || splitIds.length === 0 || splitIds.length === detail.articles.length} onClick={() => reorganize("split")} className="rounded border px-3 py-1 disabled:opacity-50">Tách event</button>
              </div>
              <div className="space-y-2">
                <h3 className="font-semibold">Nhật ký quyết định</h3>
                {detail.history.length === 0 && <p className="text-sm">Chưa có quyết định.</p>}
                {detail.history.map((item, index) => (
                  <p key={index} className="rounded border p-2 text-sm">
                    {item.created_at?.slice(0, 16)} · Người dùng #{item.actor_id} · {item.old_status || "mới"} → {item.new_status}
                    {item.reason && <> · {item.reason}</>}
                    {item.notes && <> · {item.notes}</>}
                  </p>
                ))}
              </div>
            </>
          )}
        </section>
      </div>
    </main>
  );
}
