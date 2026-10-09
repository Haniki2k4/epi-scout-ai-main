import ReviewHistory from "./ReviewHistory";
import {useEffect,useState} from "react";import DiseaseMultiSelect from "@/components/admin/DiseaseMultiSelect";import {Textarea} from "@/components/ui/textarea";import {Card,CardContent,CardHeader,CardTitle} from "@/components/ui/card";import {Button} from "@/components/ui/button";import {Input} from "@/components/ui/input";import {Badge} from "@/components/ui/badge";import {useToast} from "@/components/ui/use-toast";import {llmApi,type Item,type Metrics} from "@/lib/llmEvaluationApi";
const pct=(v:number|null|undefined)=>v==null?"—":(v*100).toFixed(1)+"%";
function useMetrics(){const[m,setM]=useState<Metrics|null>(null);const[e,setE]=useState("");useEffect(()=>{llmApi.metrics().then(setM).catch(x=>setE(x.message))},[]);return{m,e}}
export function Overview(){const{m,e}=useMetrics();if(e)return <p className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;return <div className="metric-grid">{[["Mẫu đã duyệt",m.reviewed_count],["Precision",pct(m.precision)],["Recall đầu-cuối",pct(m.end_to_end_recall)],["F1",pct(m.f1)],["Coverage",pct(m.coverage)],["Abstention",pct(m.abstention_rate)]].map(([k,v])=><Card key={String(k)}><CardHeader><CardTitle className="text-base">{k}</CardTitle></CardHeader><CardContent className="text-3xl font-semibold">{v}</CardContent></Card>)}</div>}
export function ConfusionMatrix(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;const ts=["relevant","noise","irrelevant"],ps=["relevant","noise","irrelevant","unsure"];return <Card><CardHeader><CardTitle>Ma trận nhầm lẫn 3 × 4</CardTitle></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[560px]"><thead><tr><th className="p-3 text-left">Ground truth</th>{ps.map(p=><th key={p} className="p-3 text-right">{p}</th>)}</tr></thead><tbody>{ts.map(t=><tr className="border-t" key={t}><th className="p-3 text-left">{t}</th>{ps.map(p=><td className="p-3 text-right" key={p}>{m.confusion_matrix[t]?.[p]??0}</td>)}</tr>)}</tbody></table><p className="mt-4 text-sm text-muted-foreground">Selective recall {pct(m.selective_recall)} · Recall đầu-cuối {pct(m.end_to_end_recall)}</p></CardContent></Card>}
export function ProviderHealth(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;return <div className="grid gap-4 lg:grid-cols-2"><Card><CardHeader><CardTitle>Sức khỏe provider</CardTitle></CardHeader><CardContent><p>Tổng run: <b>{m.provider.total}</b></p><p>Thành công: <b>{pct(m.provider.success_rate)}</b></p><p>Fallback: <b>{m.provider.fallback_count} ({pct(m.provider.fallback_rate)})</b></p><p>p50/p95: <b>{m.provider.latency_p50_ms??"—"} / {m.provider.latency_p95_ms??"—"} ms</b></p></CardContent></Card><Card><CardHeader><CardTitle>Trạng thái</CardTitle></CardHeader><CardContent>{Object.entries(m.provider.status_counts).map(([k,v])=><div className="flex justify-between border-b py-2" key={k}><span>{k}</span><b>{v}</b></div>)}</CardContent></Card></div>}
export function ExtractionMetrics(){const{m,e}=useMetrics();if(e)return <p role="alert" className="text-destructive">{e}</p>;if(!m)return <p>Đang tải…</p>;const rows=Object.entries(m.extraction??{});return <Card><CardHeader><CardTitle>Chất lượng trích xuất</CardTitle></CardHeader><CardContent>{rows.length?rows.map(([k,v])=><div className="flex justify-between border-b py-3" key={k}><span>{k}</span><b>{pct(v.accuracy)} ({v.correct}/{v.total})</b></div>):<p className="text-muted-foreground">Chưa đủ ground truth trích xuất.</p>}</CardContent></Card>}
type ReviewDraft = { diseases: string[]; location: string; eventDate: string; caseObservations: string };
type QueueView = "pending" | "processed";
const toDraft = (item: Item): ReviewDraft => ({
  diseases: item.human_diseases ?? [],
  location: item.human_location ?? "",
  eventDate: item.human_event_date?.slice(0, 10) ?? "",
  caseObservations: JSON.stringify(item.human_case_observations ?? [], null, 2),
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
  const [items, setItems] = useState<Item[]>([]);
  const [selectedItemId, setSelectedItemId] = useState<number | null>(null);
  const selectedItem = items.find((item) => item.id === selectedItemId) ?? items[0];
  const [view, setView] = useState<QueueView>("pending");
  const [drafts, setDrafts] = useState<Record<number, ReviewDraft>>({});
  const [diseaseOptions, setDiseaseOptions] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [savingId, setSavingId] = useState<number | null>(null);

  const load = () => {
    setLoading(true);
    setError("");
    return llmApi.items(view).then((response) => {
      setItems(response.items);
      setDrafts(Object.fromEntries(response.items.map((item) => [item.id, toDraft(item)])));
    }).catch((reason: Error) => setError(reason.message)).finally(() => setLoading(false));
  };
  useEffect(() => { void load(); }, [view]);
  useEffect(() => {
    fetch("/api/keywords?limit=1000&only_active=false")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Không tải được danh sách bệnh")))
      .then((rows: Array<{ text: string }>) => setDiseaseOptions(rows.map((row) => row.text)))
      .catch((reason: Error) => console.warn(reason.message));
  }, []);

  const updateDraft = (id: number, patch: Partial<ReviewDraft>) =>
    setDrafts((current) => ({ ...current, [id]: { ...current[id], ...patch } }));

  const save = async (item: Item, label: string, signalLabel?: string) => {
    const draft = drafts[item.id] ?? toDraft(item);
    let observations: Array<Record<string, unknown>>;
    try {
      const parsed = JSON.parse(draft.caseObservations || "[]");
      if (!Array.isArray(parsed)) throw new Error();
      observations = parsed;
    } catch {
      toast({ title: "Dữ liệu số ca chưa hợp lệ", description: "Trường số ca phải là một JSON array.", variant: "destructive" });
      return;
    }
    try {
      setSavingId(item.id);
      const updated = await llmApi.label(item.id, {
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
      });
      setItems((current) => view === "pending"
        ? current.filter((candidate) => candidate.id !== item.id)
        : current.map((candidate) => candidate.id === item.id ? updated : candidate));
      setDrafts((current) => ({ ...current, [item.id]: toDraft(updated) }));
      toast({ title: "Đã lưu đánh giá" });
    } catch (reason) {
      toast({ title: "Không thể lưu", description: reason instanceof Error ? reason.message : "Lỗi", variant: "destructive" });
    } finally { setSavingId(null); }
  };

  const queueControls = <div className="flex flex-wrap gap-2" aria-label="Bộ lọc hàng chờ">
    <Button variant={view === "pending" ? "default" : "outline"} onClick={() => setView("pending")}>Chưa gán nhãn</Button>
    <Button variant={view === "processed" ? "default" : "outline"} onClick={() => setView("processed")}>Đã xử lý</Button>
  </div>;

  if (loading) return <div className="space-y-4">{queueControls}<p>Đang tải hàng chờ…</p></div>;
  if (error) return <div className="space-y-3"><p className="text-destructive">{error}</p><Button onClick={load}>Thử lại</Button></div>;
  if (items.length === 0) return <div className="space-y-4">{queueControls}<p className="text-muted-foreground">{view === "pending" ? "Không còn bài chưa gán nhãn." : "Chưa có bài đã xử lý."}</p></div>;

  return <div className="space-y-4">{queueControls}<div className="review-layout">
    <aside className="review-list rounded-lg border bg-card p-3" aria-label="Bài viết trong hàng đợi">
      <p className="mb-3 px-2 text-sm font-semibold">{view === "pending" ? "Bài chưa gán nhãn" : "Bài đã xử lý"} · {items.length}</p>
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
        <label className="block space-y-1 text-sm"><span className="block font-medium">Các quan sát số ca</span><Textarea aria-label="Các quan sát số ca" rows={3}
          placeholder='Các quan sát số ca dạng JSON, ví dụ [{"case_count": 3}]'
          value={draft.caseObservations}
          onChange={(event) => updateDraft(item.id, { caseObservations: event.target.value })} /></label>
      </div>
      <fieldset disabled={savingId !== null} className="review-actions flex flex-wrap gap-2 rounded-lg bg-card py-2">
        {isContextRoute ? <>
          <Button onClick={() => save(item, "relevant", "confirmed_event")}>Ca/ổ dịch thật</Button>
          <Button variant="secondary" onClick={() => save(item, "relevant", "early_signal")}>Tín hiệu sớm</Button>
        </> : <Button onClick={() => save(item, "relevant")}>Liên quan</Button>}
        <Button variant="outline" onClick={() => save(item, "noise")}>Nhiễu</Button>
        <Button variant="outline" onClick={() => save(item, "irrelevant")}>Không liên quan</Button>
        <Button variant="ghost" onClick={() => save(item, "unsure")}>Chưa chắc chắn</Button>{item.current_run && !["success", "pending"].includes(item.current_run.status) && <Button variant="secondary" onClick={() => llmApi.retry(item.id).then(load).catch((reason: Error) => toast({ title: "Retry thất bại", description: reason.message, variant: "destructive" }))}>Retry LLM</Button>}
      </fieldset>
    </CardContent></Card>;
  })}</section></div></div>;
}
export function DatasetVersions(){const{toast}=useToast();const[v,setV]=useState<any[]>([]);const[s,setS]=useState<any>();const[tag,setTag]=useState("");const load=()=>Promise.all([llmApi.versions(),llmApi.summary()]).then(([a,b])=>{setV(a);setS(b)});useEffect(()=>{load().catch(()=>{})},[]);const create=()=>llmApi.create({version_tag:tag,split_strategy:"temporal_grouped",split_seed:42,notes:null}).then(()=>{setTag("");load()}).catch(e=>toast({title:"Lỗi",description:e.message,variant:"destructive"}));return <div className="space-y-4"><Card><CardContent className="pt-6"><p className="text-3xl font-semibold">{s?.eligible_count??0}</p><p className="text-sm text-muted-foreground">mẫu đủ điều kiện · {JSON.stringify(s?.label_distribution??{})}</p><div className="mt-4 flex gap-2"><Input value={tag} onChange={e=>setTag(e.target.value)} placeholder="2026.09-v1"/><Button disabled={!tag} onClick={create}>Tạo version</Button></div></CardContent></Card>{v.map(x=><Card key={x.id}><CardContent className="flex items-center justify-between pt-6"><div><b>{x.version}</b><p className="text-sm">{x.status} · {x.sample_count} mẫu</p></div><div className="flex gap-2">{x.status==="draft"&&<Button variant="outline" onClick={()=>llmApi.freeze(x.id).then(load)}>Freeze</Button>}<Button variant="outline" onClick={()=>llmApi.download(x.id,"jsonl").catch(e=>toast({title:"Lỗi tải",description:e.message,variant:"destructive"}))}>JSONL</Button><Button variant="outline" onClick={()=>llmApi.download(x.id,"csv").catch(e=>toast({title:"Lỗi tải",description:e.message,variant:"destructive"}))}>CSV</Button><Button variant="outline" onClick={()=>llmApi.download(x.id,"excel").catch(e=>toast({title:"Lỗi tải",description:e.message,variant:"destructive"}))}>Excel</Button></div></CardContent></Card>)}</div>}
