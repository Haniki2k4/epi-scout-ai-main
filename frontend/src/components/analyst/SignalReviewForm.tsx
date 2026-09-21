import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

export type ContextSignal = {
  article_id: number;
  title: string;
  link: string;
  summary: string | null;
  source: string | null;
  published_date: string | null;
  signal_type: string | null;
  matched_phrases: string[];
  evidence_text: string | null;
  llm_label: string | null;
  llm_reason: string | null;
  review_version: number;
  current_review: { decision: string; reason: string } | null;
  history?: Array<{ id: number; decision: string; reason: string; reviewed_at: string; reviewer_id: number }>;
};

type Decision = "dismissed" | "monitoring_unknown" | "disease_identified" | "ruled_out";

export default function SignalReviewForm({ signal, onSaved, onStale }: {
  signal: ContextSignal;
  onSaved: () => Promise<void>;
  onStale: () => Promise<void>;
}) {
  const [decision, setDecision] = useState<Decision>("monitoring_unknown");
  const [reason, setReason] = useState("");
  const [evidence, setEvidence] = useState("");
  const [disease, setDisease] = useState("");
  const [source, setSource] = useState("");
  const [location, setLocation] = useState("");
  const [requestId, setRequestId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const isDisease = decision === "disease_identified";
  const requiresEvidence = isDisease || decision === "monitoring_unknown";
  const valid = Boolean(reason.trim() && (!requiresEvidence || evidence.trim()) && (!isDisease || (disease.trim() && source.trim())));

  const update = (fn: () => void) => {
    fn();
    setRequestId(null);
  };

  const save = async () => {
    if (!valid || saving) return;
    const id = requestId || crypto.randomUUID();
    setRequestId(id);
    setSaving(true);
    setError("");
    try {
      const response = await fetch(`/api/context-signals/${signal.article_id}/review`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          request_id: id,
          expected_review_version: signal.review_version,
          decision,
          reason: reason.trim(),
          signal_evidence: requiresEvidence ? evidence.trim() : null,
          disease_name: isDisease ? disease.trim() : null,
          disease_source: isDisease ? source.trim() : null,
          location: location.trim() || null,
        }),
      });
      if (!response.ok) {
        const data = await response.json();
        if (response.status === 409) {
          await onStale();
          throw new Error("Bài đã được duyệt ở phiên khác. Dữ liệu đã tải lại; hãy xem quyết định mới.");
        }
        throw new Error(typeof data.detail === "string" ? data.detail : "Không lưu được quyết định");
      }
      await onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Không lưu được quyết định");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Quyết định tín hiệu và bệnh</CardTitle>
        <p className="text-sm text-muted-foreground">Chỉ xác nhận bệnh khi có nguồn xác minh. Bài chưa xác định bệnh vẫn được giữ ẩn.</p>
      </CardHeader>
      <CardContent>
        <form onSubmit={(event) => { event.preventDefault(); void save(); }} className="space-y-4">
          <label className="block space-y-1.5 text-sm font-medium">Kết luận
            <select value={decision} onChange={(event) => update(() => setDecision(event.target.value as Decision))} className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring">
              <option value="monitoring_unknown">Tiếp tục theo dõi, chưa rõ bệnh</option>
              <option value="disease_identified">Đã xác định bệnh và tạo sự kiện</option>
              <option value="dismissed">Bác bỏ tín hiệu</option>
              <option value="ruled_out">Loại trừ sau xác minh</option>
            </select>
          </label>
          <label className="block space-y-1.5 text-sm font-medium">Lý do quyết định <span className="text-destructive">*</span>
            <Textarea required maxLength={500} value={reason} onChange={(event) => update(() => setReason(event.target.value))} placeholder="Ghi căn cứ để người duyệt sau có thể đối chiếu" />
          </label>
          {requiresEvidence && <label className="block space-y-1.5 text-sm font-medium">Bằng chứng tín hiệu <span className="text-destructive">*</span>
            <Textarea required maxLength={5000} value={evidence} onChange={(event) => update(() => setEvidence(event.target.value))} placeholder="Trích thông tin cụ thể từ bài hoặc nguồn xác minh" />
          </label>}
          {isDisease && <>
            <label className="block space-y-1.5 text-sm font-medium">Bệnh đã xác định <span className="text-destructive">*</span>
              <Input required maxLength={255} value={disease} onChange={(event) => update(() => setDisease(event.target.value))} placeholder="Tên bệnh" />
            </label>
            <label className="block space-y-1.5 text-sm font-medium">Nguồn xác nhận bệnh <span className="text-destructive">*</span>
              <Input required maxLength={500} value={source} onChange={(event) => update(() => setSource(event.target.value))} placeholder="Cơ quan, báo cáo hoặc nguồn xác minh" />
            </label>
          </>}
          <label className="block space-y-1.5 text-sm font-medium">Địa bàn
            <Input maxLength={255} value={location} onChange={(event) => update(() => setLocation(event.target.value))} placeholder="Nếu bài có địa bàn cụ thể" />
          </label>
          {error && <p role="alert" className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">{error}</p>}
          <Button type="submit" disabled={!valid || saving}>{saving ? "Đang lưu..." : "Lưu quyết định"}</Button>
        </form>
      </CardContent>
    </Card>
  );
}

