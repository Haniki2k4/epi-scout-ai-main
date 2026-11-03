import ReviewHistory from "./ReviewHistory";
import {Loader2, Plus, Trash2} from "lucide-react";
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import DiseaseMultiSelect from "@/components/admin/DiseaseMultiSelect";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { fetchDiseaseOptions } from "@/lib/apiClient";
import { keywordKeys, llmEvalKeys } from "@/lib/queryKeys";
import { llmApi, type Item, type Metrics, type DatasetSummary, type DatasetVersion, type ItemList } from "@/lib/llmEvaluationApi";
const pct=(v:number|null|undefined)=>v==null?"—":(v*100).toFixed(1)+"%";
function useMetrics(){const query=useQuery({queryKey:llmEvalKeys.metrics(),queryFn:({signal})=>llmApi.metrics(signal),staleTime:120_000});return{m:query.data??null,e:query.error instanceof Error?query.error.message:"",isLoading:query.isLoading}}
export function Overview(){const{m,e}=useMetrics();if(e)return <p className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;return <div className="metric-grid">{[["Mẫu đã duyệt",m.reviewed_count],["Precision",pct(m.precision)],["Recall đầu-cuối",pct(m.end_to_end_recall)],["F1",pct(m.f1)],["Coverage",pct(m.coverage)],["Abstention",pct(m.abstention_rate)]].map(([k,v])=><Card key={String(k)}><CardHeader><CardTitle className="text-base">{k}</CardTitle></CardHeader><CardContent className="text-3xl font-semibold">{v}</CardContent></Card>)}</div>}
export function ConfusionMatrix(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;const ts=["relevant","noise","irrelevant"],ps=["relevant","noise","irrelevant","unsure"];return <Card><CardHeader><CardTitle>Ma trận nhầm lẫn 3 × 4</CardTitle></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[560px]"><thead><tr><th className="p-3 text-left">Ground truth</th>{ps.map(p=><th key={p} className="p-3 text-right">{p}</th>)}</tr></thead><tbody>{ts.map(t=><tr className="border-t" key={t}><th className="p-3 text-left">{t}</th>{ps.map(p=><td className="p-3 text-right" key={p}>{m.confusion_matrix[t]?.[p]??0}</td>)}</tr>)}</tbody></table><p className="mt-4 text-sm text-muted-foreground">Selective recall {pct(m.selective_recall)} · Recall đầu-cuối {pct(m.end_to_end_recall)}</p></CardContent></Card>}
export function ProviderHealth(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Sức khỏe provider</CardTitle></CardHeader><CardContent><p>Tổng run: <b>{m.provider.total}</b></p><p>Thành công: <b>{pct(m.provider.success_rate)}</b></p><p>Fallback: <b>{m.provider.fallback_count} ({pct(m.provider.fallback_rate)})</b></p><p>p50/p95: <b>{m.provider.latency_p50_ms??"—"} / {m.provider.latency_p95_ms??"—"} ms</b></p></CardContent></Card><Card><CardHeader><CardTitle>Trạng thái</CardTitle></CardHeader><CardContent>{Object.entries(m.provider.status_counts).map(([k,v])=><div className="flex justify-between border-b py-2" key={k}><span>{k}</span><b>{v}</b></div>)}</CardContent></Card></div>}
export function ExtractionMetrics(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;const rows=Object.entries(m.extraction??{});return <Card><CardHeader><CardTitle>Chất lượng trích xuất</CardTitle></CardHeader><CardContent>{rows.length?rows.map(([k,v])=><div className="flex justify-between border-b py-3" key={k}><span>{k}</span><b>{pct(v.accuracy)} ({v.correct}/{v.total})</b></div>):<p className="text-muted-foreground">Chưa đủ ground truth trích xuất.</p>}</CardContent></Card>}
const CASE_TYPES = [
  { value: "confirmed", label: "Ca xác nhận" },
  { value: "suspected", label: "Ca nghi ngờ" },
  { value: "total_unspecified", label: "Không rõ trạng thái" },
  { value: "deaths", label: "Tử vong" },
] as const;
const COUNT_SCOPES = [
  { value: "new", label: "Ca mới" },
  { value: "cumulative", label: "Lũy kế" },
  { value: "period_total", label: "Tổng trong kỳ" },
  { value: "unknown", label: "Không rõ kỳ" },
] as const;
type CaseType = typeof CASE_TYPES[number]["value"];
type CountScope = typeof COUNT_SCOPES[number]["value"];
type CaseObservationDraft = {
  reportedValue: string;
  caseType: CaseType | "";
  countScope: CountScope | "";
  source: Record<string, unknown>;
};
type ReviewDraft = { diseases: string[]; location: string; eventDate: string; caseObservations: CaseObservationDraft[] };
type QueueView = "pending" | "processed";
const isCaseType = (value: unknown): value is CaseType => CASE_TYPES.some((option) => option.value === value);
const isCountScope = (value: unknown): value is CountScope => COUNT_SCOPES.some((option) => option.value === value);
const toDraft = (item: Item): ReviewDraft => ({
  diseases: item.human_diseases ?? [],
  location: item.human_location ?? "",
  eventDate: item.human_event_date?.slice(0, 10) ?? "",
  caseObservations: (item.human_case_observations ?? []).map((observation) => ({
    reportedValue: observation.reported_value == null
      ? (observation.case_count == null ? "" : String(observation.case_count))
      : String(observation.reported_value),
    caseType: isCaseType(observation.case_type) ? observation.case_type : "",
    countScope: isCountScope(observation.count_scope) ? observation.count_scope : "",
    source: Object.fromEntries(Object.entries(observation).filter(([key]) => key !== "case_count")),
  })),
});

const routeLabel = (route?: string) => route === "keyword" ? "Cửa A · từ khóa" : route === "context" ? "Cửa B · ngữ cảnh" : route ?? "Dữ liệu cũ";
const statusLabel = (status?: string) => ({
  success: "Thành công", pending: "Đang chờ", timeout: "Quá thời gian",
  rate_limited: "Giới hạn lượt gọi", provider_error: "Lỗi provider",
  model_unavailable: "Model không khả dụng", disabled: "Đã tắt",
}[status ?? ""] ?? status ?? "Chưa chạy");
const llmLabel = (label?: string | null) => ({
  relevant: "Liên quan", noise: "Nhiễu", irrelevant: "Không liên quan", unsure: "Chưa chắc chắn",
}[label ?? ""] ?? label ?? "Chưa có nhãn");

export function ReviewQueue() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const [view, setView] = useState<QueueView>("pending");
  const [searchText, setSearchText] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [drafts, setDrafts] = useState<Record<number, ReviewDraft>>({});
  const [dirtyIds, setDirtyIds] = useState<Set<number>>(() => new Set());
  const [savingId, setSavingId] = useState<number | null>(null);
  const [retryingId, setRetryingId] = useState<number | null>(null);

  const activeSearch = view === "processed" ? debouncedSearch : "";
  const itemsQuery = useQuery({
    queryKey: llmEvalKeys.items(view, activeSearch),
    queryFn: ({ signal }) => llmApi.items(view, activeSearch, signal),
    staleTime: 45_000,
  });
  const diseaseOptionsQuery = useQuery({
    queryKey: keywordKeys.diseaseOptions(),
    queryFn: ({ signal }) => fetchDiseaseOptions(signal),
    staleTime: 600_000,
  });
  const items = itemsQuery.data?.items ?? [];
  const totalItems = itemsQuery.data?.total ?? 0;
  const selectedItem = items.find((item) => item.id === selectedItemId) ?? items[0];
  useEffect(() => {
    if (view !== "processed") return;
    const timeoutId = window.setTimeout(() => setDebouncedSearch(searchText.trim()), 300);
    return () => window.clearTimeout(timeoutId);
  }, [view, searchText]);
  useEffect(() => {
    const responseItems = itemsQuery.data?.items;
    if (!responseItems) return;
    setDrafts((current) => {
      const next = { ...current };
      for (const item of responseItems) {
        if (!next[item.id] || !dirtyIds.has(item.id)) next[item.id] = toDraft(item);
      }
      return next;
    });
  }, [itemsQuery.data?.items, dirtyIds]);
  const diseaseOptions = diseaseOptionsQuery.data ?? [];

  const updateDraft = (id: number, patch: Partial<ReviewDraft>) => {
    setDirtyIds((current) => new Set(current).add(id));
    const item = items.find((candidate) => candidate.id === id);
    const emptyDraft: ReviewDraft = { diseases: [], location: "", eventDate: "", caseObservations: [] };
    setDrafts((current) => ({ ...current, [id]: { ...(current[id] ?? (item ? toDraft(item) : emptyDraft)), ...patch } }));
  }

  const retryMutation = useMutation({
    mutationFn: ({ itemId }: { itemId: number; tokenAtStart: string | null; queryKey: ReturnType<typeof llmEvalKeys.items> }) => llmApi.retry(itemId),
    onSuccess: (run, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      queryClient.setQueryData<ItemList>(variables.queryKey, (current) => current && ({
        ...current,
        items: current.items.map((candidate) => candidate.id === variables.itemId
          ? { ...candidate, current_inference_run_id: run.id, current_run: run }
          : candidate),
      }));
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.metrics() });
    },
  });

  const saveMutation = useMutation({
    mutationFn: ({ itemId, body }: { itemId: number; body: object; tokenAtStart: string | null; view: QueueView; search: string }) => llmApi.label(itemId, body),
    onSuccess: (updatedItem, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      const currentKey = llmEvalKeys.items(variables.view, variables.search);
      queryClient.setQueryData<ItemList>(currentKey, (current) => {
        if (!current) return current;
        if (variables.view === "pending") {
          return {
            ...current,
            items: current.items.filter((candidate) => candidate.id !== updatedItem.id),
            total: Math.max(0, current.total - 1),
          };
        }
        return { ...current, items: current.items.map((candidate) => candidate.id === updatedItem.id ? updatedItem : candidate) };
      });
      if (variables.view === "pending") {
        void queryClient.invalidateQueries({ queryKey: ["llm-evaluations", "items", { view: "processed" }] });
      }
      setDirtyIds((current) => { const next = new Set(current); next.delete(updatedItem.id); return next; });
      setDrafts((current) => ({ ...current, [updatedItem.id]: toDraft(updatedItem) }));
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.metrics() });
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.datasetSummary() });
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.detail(updatedItem.id) });
    },
  });

  const retry = async (item: Item) => {
    const tokenAtStart = localStorage.getItem("token");
    setRetryingId(item.id);
    try {
      await retryMutation.mutateAsync({
        itemId: item.id,
        tokenAtStart,
        queryKey: llmEvalKeys.items(view, activeSearch),
      });
      if (localStorage.getItem("token") === tokenAtStart) toast({ title: "Đã chạy lại LLM cho bài viết" });
    } catch (reason) {
      toast({ title: "Retry thất bại", description: reason instanceof Error ? reason.message : "Lỗi", variant: "destructive" });
    } finally {
      setRetryingId(null);
    }
  };

  const save = async (item: Item, label: string, signalLabel?: string) => {
    const draft = drafts[item.id] ?? toDraft(item);
    const enteredObservations = draft.caseObservations.filter((observation) => observation.reportedValue.trim());
    const hasInvalidValue = enteredObservations.some((observation) => {
      const value = Number(observation.reportedValue);
      return !Number.isSafeInteger(value) || value <= 0 || !observation.caseType || !observation.countScope;
    });
    if (hasInvalidValue) {
      toast({ title: "Quan sát số ca chưa đầy đủ", description: "Nhập số nguyên lớn hơn 0 và chọn loại số liệu cùng phạm vi cho mỗi quan sát.", variant: "destructive" });
      return;
    }
    const observations = enteredObservations.map((observation) => ({
      ...observation.source,
      reported_value: Number(observation.reportedValue),
      case_type: observation.caseType,
      count_scope: observation.countScope,
    }));
    try {
      setSavingId(item.id);
      const tokenAtStart = localStorage.getItem("token");
      await saveMutation.mutateAsync({ itemId: item.id, view, search: activeSearch, tokenAtStart, body: {
        expected_revision: item.label_revision,
        reviewed_inference_run_id: item.current_run?.id ?? item.current_inference_run_id,
        human_label: label,
        human_signal_label: signalLabel ?? null,
        human_diseases: draft.diseases,
        human_location: draft.location.trim() || null,
        human_event_date: draft.eventDate ? `${draft.eventDate}T00:00:00` : null,
        human_case_observations: observations,
        eligible_for_training: label !== "unsure",
        reason: "Đánh giá thủ công",
      } });
      if (localStorage.getItem("token") === tokenAtStart) toast({ title: "Đã lưu đánh giá" });
    } catch (reason) {
      toast({ title: "Không thể lưu", description: reason instanceof Error ? reason.message : "Lỗi", variant: "destructive" });
    } finally { setSavingId(null); }
  };

  const queueControls = <div className="flex flex-wrap gap-2" aria-label="Bộ lọc hàng chờ">
    <Button variant={view === "pending" ? "default" : "outline"} onClick={() => setView("pending")}>Chưa gán nhãn</Button>
    <Button variant={view === "processed" ? "default" : "outline"} onClick={() => setView("processed")}>Đã xử lý</Button>
    {view === "processed" && <Input
      type="search"
      aria-label="Tìm bài báo đã xử lý"
      placeholder="Tìm theo tiêu đề, nội dung hoặc URL…"
      value={searchText}
      onChange={(event) => setSearchText(event.target.value)}
      className="min-w-56 flex-1"
    />}
  </div>;

  const queueError = itemsQuery.error ?? diseaseOptionsQuery.error;
  if (itemsQuery.isLoading || diseaseOptionsQuery.isLoading) return <div className="space-y-4">{queueControls}<p>Đang tải hàng chờ…</p></div>;
  if (queueError) return <div className="space-y-3">{queueControls}<p className="text-destructive">{queueError instanceof Error ? queueError.message : "Không tải được dữ liệu"}</p><Button onClick={() => { void itemsQuery.refetch(); void diseaseOptionsQuery.refetch(); }}>Thử lại</Button></div>;
  if (items.length === 0) return <div className="space-y-4">{queueControls}<p className="text-muted-foreground">{view === "pending" ? "Không còn bài chưa gán nhãn." : activeSearch ? `Không tìm thấy bài báo phù hợp trong ${totalItems} bài đã xử lý.` : "Chưa có bài đã xử lý."}</p></div>;

  return <div className="space-y-4">{queueControls}{itemsQuery.isFetching && <p role="status" className="text-xs text-muted-foreground">Đang cập nhật nền…</p>}<div className="review-layout">
    <aside className="review-list rounded-lg border bg-card p-3" aria-label="Bài viết trong hàng đợi">
      <p className="mb-3 px-2 text-sm font-semibold">{view === "pending" ? "Bài chưa gán nhãn" : "Bài đã xử lý"} · {items.length}/{totalItems}</p>
      <div className="space-y-2">{items.map((item) => <button key={item.id} type="button" className="queue-option" aria-pressed={selectedItem?.id === item.id} disabled={savingId !== null} onClick={() => setSelectedItemId(item.id)}>
        <span className="block text-sm font-medium leading-relaxed">{item.title_snapshot}</span><span className="mt-2 block text-xs text-muted-foreground">{routeLabel(item.current_run?.route)} · {llmLabel(item.current_run?.llm_label)}</span>
      </button>)}</div>
    </aside>
    <section aria-label="Xem và gán nhãn bài viết">{(selectedItem ? [selectedItem] : []).map((item) => {
    const draft = drafts[item.id] ?? toDraft(item);
    const isContextRoute = item.current_run?.route === "context";
    return <Card key={item.id}><CardContent className="space-y-4 pt-6">
      <div className="flex flex-wrap gap-2 text-sm [&>div]:break-all [&>div]:text-xs">
        <Badge>Tuyến: {routeLabel(item.current_run?.route)}</Badge>
        <Badge variant="outline">Model: {item.current_run?.model_id ?? "Chưa có"}</Badge>
        <Badge variant="outline">Prompt: {item.current_run?.prompt_version ?? "Chưa có"}</Badge>
        <Badge variant="secondary">Trạng thái: {statusLabel(item.current_run?.status)}</Badge>
        <Badge variant="secondary">Phiên bản nhãn: {item.label_revision}</Badge>
      </div>
      <div className="grid gap-3 rounded-lg border bg-muted/30 p-3 md:grid-cols-2">
        <div>
          <p className="mb-2 text-sm font-semibold">Từ khóa nhận diện</p>
          <div className="flex flex-wrap gap-2">
            {item.current_run?.input_keywords?.length
              ? item.current_run.input_keywords.map((keyword) => <Badge key={keyword} variant="outline">{keyword}</Badge>)
              : <span className="text-sm text-muted-foreground">Không có từ khóa</span>}
          </div>
        </div>
        <div>
          <p className="mb-2 text-sm font-semibold">Nhãn LLM đã gán</p>
          <Badge variant={item.current_run?.llm_label === "relevant" ? "default" : "secondary"}>
            {llmLabel(item.current_run?.llm_label)}
          </Badge>
          {item.current_run && item.current_run.status !== "success" && (
            <p className="mt-2 text-xs text-muted-foreground">Chưa có kết quả phân loại thành công cho lần chạy này.</p>
          )}
        </div>
      </div>
      <a href={item.canonical_url ?? "#"} target="_blank" rel="noreferrer" className="text-lg font-semibold text-primary underline">{item.title_snapshot}</a>
      <p>{item.summary_snapshot}</p>
      <div className="rounded-lg border p-3 space-y-2 text-sm"><p><strong>Lý do LLM:</strong> {item.current_run?.llm_reason || "Chưa có nhận xét"}</p><p><strong>Nhãn người duyệt:</strong> {llmLabel(item.human_label)}</p><ReviewHistory key={`${item.id}-${item.label_revision}`} itemId={item.id}/></div>
      <div className="review-fields">
        <DiseaseMultiSelect options={diseaseOptions} value={draft.diseases}
          onChange={(diseases) => updateDraft(item.id, { diseases })} />
        <label className="block space-y-1 text-sm"><span className="block font-medium">Địa bàn đúng</span><Input aria-label="Địa bàn đúng" placeholder="Địa bàn đúng" value={draft.location}
          onChange={(event) => updateDraft(item.id, { location: event.target.value })} /></label>
        <label className="block space-y-1 text-sm"><span className="block font-medium">Ngày sự kiện đúng</span><Input aria-label="Ngày sự kiện đúng" type="date" value={draft.eventDate}
          onChange={(event) => updateDraft(item.id, { eventDate: event.target.value })} /></label>
        <fieldset className="space-y-3 text-sm md:col-span-2">
          <legend className="mb-1 font-medium">Các quan sát số ca</legend>
          {draft.caseObservations.map((observation, index) => (
            <div key={index} className="grid items-end gap-3 rounded-md border p-3 sm:grid-cols-[minmax(5rem,0.6fr)_minmax(9rem,1fr)_minmax(9rem,1fr)_auto]">
              <label className="space-y-1"><span className="block text-xs text-muted-foreground">Số lượng</span><Input aria-label={`Số lượng quan sát ${index + 1}`} type="number" min="1" step="1" value={observation.reportedValue}
                onChange={(event) => updateDraft(item.id, { caseObservations: draft.caseObservations.map((current, currentIndex) => currentIndex === index ? { ...current, reportedValue: event.target.value } : current) })} /></label>
              <label className="space-y-1"><span className="block text-xs text-muted-foreground">Loại số liệu</span><Select value={observation.caseType} onValueChange={(value) => updateDraft(item.id, { caseObservations: draft.caseObservations.map((current, currentIndex) => currentIndex === index ? { ...current, caseType: value as CaseType } : current) })}>
                <SelectTrigger aria-label={`Loại số liệu quan sát ${index + 1}`}><SelectValue placeholder="Chọn loại" /></SelectTrigger><SelectContent>{CASE_TYPES.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
              </Select></label>
              <label className="space-y-1"><span className="block text-xs text-muted-foreground">Phạm vi số</span><Select value={observation.countScope} onValueChange={(value) => updateDraft(item.id, { caseObservations: draft.caseObservations.map((current, currentIndex) => currentIndex === index ? { ...current, countScope: value as CountScope } : current) })}>
                <SelectTrigger aria-label={`Phạm vi số quan sát ${index + 1}`}><SelectValue placeholder="Chọn phạm vi" /></SelectTrigger><SelectContent>{COUNT_SCOPES.map((option) => <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>)}</SelectContent>
              </Select></label>
              <Button type="button" variant="ghost" size="icon" aria-label={`Xóa quan sát ${index + 1}`} onClick={() => updateDraft(item.id, { caseObservations: draft.caseObservations.filter((_, currentIndex) => currentIndex !== index) })}><Trash2 /></Button>
            </div>
          ))}
          <Button type="button" variant="outline" size="sm" onClick={() => updateDraft(item.id, { caseObservations: [...draft.caseObservations, { reportedValue: "", caseType: "", countScope: "", source: {} }] })}><Plus />Thêm quan sát số ca</Button>
        </fieldset>
      </div>
      <fieldset disabled={savingId !== null || retryingId === item.id} className="review-actions flex flex-wrap gap-2 rounded-lg bg-card py-2">
        {isContextRoute ? <>
          <Button onClick={() => save(item, "relevant", "confirmed_event")}>Ca/ổ dịch thật</Button>
          <Button variant="secondary" onClick={() => save(item, "relevant", "early_signal")}>Tín hiệu sớm</Button>
        </> : <Button onClick={() => save(item, "relevant")}>Liên quan</Button>}
        <Button variant="outline" onClick={() => save(item, "noise")}>Nhiễu</Button>
        <Button variant="outline" onClick={() => save(item, "irrelevant")}>Không liên quan</Button>
        <Button variant="ghost" onClick={() => save(item, "unsure")}>Chưa chắc chắn</Button>{item.current_run && !["success", "pending"].includes(item.current_run.status) && <Button type="button" variant="secondary" disabled={retryingId !== null} aria-busy={retryingId === item.id} onClick={() => void retry(item)}>{retryingId === item.id ? <><Loader2 className="animate-spin" />Đang chạy lại…</> : "Retry LLM"}</Button>}
      </fieldset>
    </CardContent></Card>;
  })}</section></div></div>;
}
export function DatasetVersions() {
  const { toast } = useToast();
  const queryClient = useQueryClient();
  const [tag, setTag] = useState("");
  const summaryQuery = useQuery({
    queryKey: llmEvalKeys.datasetSummary(),
    queryFn: ({ signal }) => llmApi.summary(signal),
    staleTime: 120_000,
  });
  const versionsQuery = useQuery({
    queryKey: llmEvalKeys.datasetVersions(),
    queryFn: ({ signal }) => llmApi.versions(signal),
    staleTime: 180_000,
  });
  const createMutation = useMutation({
    mutationFn: ({ versionTag }: { versionTag: string; tokenAtStart: string | null }) => llmApi.create({
      version_tag: versionTag,
      split_strategy: "temporal_grouped",
      split_seed: 42,
      notes: null,
    }),
    onSuccess: (_version, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      setTag("");
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.datasetVersions() });
    },
  });
  const freezeMutation = useMutation({
    mutationFn: ({ id }: { id: number; tokenAtStart: string | null }) => llmApi.freeze(id),
    onSuccess: (_version, variables) => {
      if (localStorage.getItem("token") !== variables.tokenAtStart) return;
      void queryClient.invalidateQueries({ queryKey: llmEvalKeys.datasetVersions() });
    },
  });
  const versions: DatasetVersion[] = versionsQuery.data ?? [];
  const summary: DatasetSummary | undefined = summaryQuery.data;
  const queryError = versionsQuery.error ?? summaryQuery.error;

  const create = async () => {
    try {
      await createMutation.mutateAsync({ versionTag: tag, tokenAtStart: localStorage.getItem("token") });
    } catch (error) {
      toast({ title: "Lỗi", description: error instanceof Error ? error.message : "Không thể tạo version", variant: "destructive" });
    }
  };

  const freeze = async (id: number) => {
    try {
      await freezeMutation.mutateAsync({ id, tokenAtStart: localStorage.getItem("token") });
    } catch (error) {
      toast({ title: "Lỗi", description: error instanceof Error ? error.message : "Không thể freeze version", variant: "destructive" });
    }
  };

  if (versionsQuery.isLoading || summaryQuery.isLoading) return <p role="status">Đang tải dataset…</p>;
  if (queryError) return <div role="alert" className="space-y-2 text-destructive">
    <p>{queryError instanceof Error ? queryError.message : "Không tải được dataset"}</p>
    <Button variant="outline" onClick={() => { void versionsQuery.refetch(); void summaryQuery.refetch(); }}>Thử lại</Button>
  </div>;

  return <div className="space-y-4">
    <Card><CardContent className="pt-6">
      <p className="text-3xl font-semibold">{summary?.eligible_count ?? 0}</p>
      <p className="text-sm text-muted-foreground">mẫu đủ điều kiện · {JSON.stringify(summary?.label_distribution ?? {})}</p>
      <div className="mt-4 flex gap-2">
        <Input value={tag} onChange={(event) => setTag(event.target.value)} placeholder="2026.09-v1" />
        <Button disabled={!tag.trim() || createMutation.isPending} onClick={() => void create()}>
          {createMutation.isPending ? "Đang tạo…" : "Tạo version"}
        </Button>
      </div>
    </CardContent></Card>
    {versions.map((version) => <Card key={version.id}><CardContent className="flex items-center justify-between pt-6">
      <div><b>{version.version}</b><p className="text-sm">{version.status} · {version.sample_count} mẫu</p></div>
      <div className="flex gap-2">
        {version.status === "draft" && <Button variant="outline" disabled={freezeMutation.isPending} onClick={() => void freeze(version.id)}>Freeze</Button>}
        <Button variant="outline" onClick={() => void llmApi.download(version.id, "jsonl").catch((error: Error) => toast({ title: "Lỗi tải", description: error.message, variant: "destructive" }))}>JSONL</Button>
        <Button variant="outline" onClick={() => void llmApi.download(version.id, "csv").catch((error: Error) => toast({ title: "Lỗi tải", description: error.message, variant: "destructive" }))}>CSV</Button>
        <Button variant="outline" onClick={() => void llmApi.download(version.id, "excel").catch((error: Error) => toast({ title: "Lỗi tải", description: error.message, variant: "destructive" }))}>Excel</Button>
      </div>
    </CardContent></Card>)}
  </div>;
}
