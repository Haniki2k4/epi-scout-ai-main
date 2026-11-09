import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Area, CartesianGrid, ComposedChart, Legend, Line, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { DiseaseSelectorModal } from "@/components/DiseaseSelectorModal";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/ui/use-toast";

type Mode = "zscore" | "forecast";
interface Spike {
  date: string; count: number; ma: number | null; std: number | null;
  zscore: number | null; spike_level: string;
}
interface Forecast {
  historical: { ds: string; y: number }[];
  forecast: { ds: string; yhat: number; yhat_lower: number; yhat_upper: number }[];
  history_days: number; interval_width: number; error?: string;
  metrics: { mae: number | null; rmse: number | null; eval_method: string; train_days?: number; test_days?: number };
}

interface AnalysisSection {
  disease: string;
  summary: string;
  remarks: string[];
  chart_data: Spike[] | Forecast;
}
interface AnalysisSnapshot {
  snapshot_id: string;
  generated_at: string;
  sections: AnalysisSection[];
}
interface AnalysisQuery {
  data?: AnalysisSnapshot;
  isPending: boolean;
  isError: boolean;
  error: Error | null;
  refetch: () => unknown;
}

const dayLabel = (date: string) => `${date.slice(8, 10)}/${date.slice(5, 7)}`;
const number = (value: number) => value.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
const tooltipStyle = { backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: 8 };

function DiseasePanel({ disease, mode, days, intervalWidth, section, query }: { disease: string; mode: Mode; days: number; intervalWidth: number; section?: AnalysisSection; query: AnalysisQuery }) {
  const rows = mode === 'zscore' ? (section?.chart_data as Spike[] || []) : [];
  const forecast = mode === 'forecast' ? section?.chart_data as Forecast | undefined : undefined;
  const alerts = rows.filter(row => row.spike_level === "alert" || row.spike_level === "danger");
  const evaluated = rows.filter(row => row.zscore != null).length;
  const historical = forecast?.historical || [];
  const total = mode === "zscore" ? rows.reduce((sum, row) => sum + row.count, 0) : historical.reduce((sum, row) => sum + row.y, 0);

  return <Card className="min-w-0" aria-label={`${mode === "zscore" ? "Đột biến" : "Dự báo"}: ${disease}`}>
    <CardHeader>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <CardTitle className="text-xl">{disease}</CardTitle>
        <Badge variant="secondary">{mode === "zscore" ? `${days} ngày · đường nền 14 ngày` : "Dự báo 7 ngày"}</Badge>
      </div>
      <CardDescription>Chỉ các bài được gán nhãn {disease}. Một bài nhắc nhiều bệnh được tính một lần trong từng bệnh tương ứng.</CardDescription>
    </CardHeader>
    <CardContent className="space-y-4">
      {query.isPending ? <p role="status" className="py-8">Đang phân tích {disease}...</p> : query.isError ?
        <div role="alert">{query.error?.message} <Button variant="outline" onClick={() => void query.refetch()}>Thử lại</Button></div> : <>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
          <Metric label={mode === "zscore" ? `Bài trong ${days} ngày` : "Bài trong lịch sử quan sát"} value={number(total)} />
          <Metric label={mode === "zscore" ? "Ngày vượt ngưỡng" : "Ngày lịch sử hoàn chỉnh"} value={mode === "zscore" ? (evaluated ? String(alerts.length) : "Chưa đánh giá") : String(forecast?.history_days ?? 0)} />
          <Metric label={mode === "zscore" ? "Ngày tính được Z-score" : "Khoảng dự báo"} value={mode === "zscore" ? `${evaluated}/${rows.length}` : `${Math.round(intervalWidth * 100)}%`} />
        </div>
        <div className="space-y-3 border-t pt-4 text-sm">
          <h4 className="font-semibold">Nhận xét riêng cho {disease}</h4>
          {section?.remarks.map((remark, index) => <p key={index}>{remark}</p>)}
          {!!forecast?.forecast.length && <Table><TableHeader><TableRow><TableHead>Ngày</TableHead><TableHead>Bài dự kiến</TableHead><TableHead>Giới hạn dưới</TableHead><TableHead>Giới hạn trên</TableHead></TableRow></TableHeader>
            <TableBody>{forecast.forecast.map(row => <TableRow key={row.ds}><TableCell>{row.ds}</TableCell><TableCell>{number(row.yhat)}</TableCell><TableCell>{number(row.yhat_lower)}</TableCell><TableCell>{number(row.yhat_upper)}</TableCell></TableRow>)}</TableBody>
          </Table>}
        </div>
      </>}
    </CardContent>
  </Card>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-lg bg-muted/40 p-3"><p className="text-xs text-muted-foreground">{label}</p><p className="mt-1 text-lg font-semibold">{value}</p></div>;
}

const colors = ["#0284c7", "#d97706", "#0d9488", "#9333ea", "#dc2626", "#4f46e5"];

function ComparisonChart({ diseases, mode, intervalWidth, query }: { diseases: string[]; mode: Mode; intervalWidth: number; query: AnalysisQuery }) {
  type Row = { date: string } & Record<string, string | number | [number, number] | null>;
  const byDate = new Map<string, Row>();
  const point = (date: string) => {
    if (!byDate.has(date)) byDate.set(date, { date });
    return byDate.get(date)!;
  };
  (query.data?.sections || []).forEach((section, index) => {
    if (mode === "zscore") {
      (section.chart_data as Spike[]).forEach(row => Object.assign(point(row.date), {
        [`actual${index}`]: row.count, [`mean${index}`]: row.ma,
        [`threshold${index}`]: row.std != null && row.std > 0 && row.ma != null ? row.ma + 2 * row.std : null,
        [`spike${index}`]: ["alert", "danger"].includes(row.spike_level) ? row.count : null,
      }));
    } else {
      const data = section.chart_data as Forecast;
      data.historical.forEach(row => { point(row.ds)[`actual${index}`] = row.y; });
      data.forecast.forEach(row => Object.assign(point(row.ds), {
        [`forecast${index}`]: row.yhat, [`band${index}`]: [row.yhat_lower, row.yhat_upper],
      }));
    }
  });
  const data = [...byDate.values()].sort((a, b) => a.date.localeCompare(b.date));
  if (!diseases.length) return <p className="flex h-[400px] items-center justify-center text-sm text-muted-foreground">Chọn tối đa 6 bệnh ở góc phải để xem biểu đồ.</p>;
  if (query.isPending) return <p role="status" className="flex h-[400px] items-center justify-center text-sm">Đang tải dữ liệu các bệnh đã chọn...</p>;
  return <>
    {query.isError && <p role="alert">{query.error?.message} <Button variant="outline" onClick={() => void query.refetch()}>Thử lại</Button></p>}
    <div className="h-[440px] w-full" role="img" aria-label={`Biểu đồ ${mode === "zscore" ? "đột biến" : "dự báo"} riêng cho ${diseases.join(", ")}`}>
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 20, right: 20, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="hsl(var(--border))" />
          <XAxis dataKey="date" tickFormatter={dayLabel} minTickGap={30} tick={{ fontSize: 12 }} />
          <YAxis allowDecimals={false} width={45} tick={{ fontSize: 12 }} />
          <Tooltip contentStyle={tooltipStyle} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {diseases.map((disease, index) => <Line key={`actual${index}`} dataKey={`actual${index}`} name={disease} stroke={colors[index]} strokeWidth={2} dot={false} />)}
          {diseases.flatMap((disease, index) => mode === "zscore" ? [
            <Line key={`mean${index}`} dataKey={`mean${index}`} name={`${disease} · TB 14 ngày`} stroke={colors[index]} strokeOpacity={0.45} dot={false} legendType="none" />,
            <Line key={`threshold${index}`} dataKey={`threshold${index}`} name={`${disease} · ngưỡng MA + 2σ`} stroke={colors[index]} strokeDasharray="5 4" dot={false} legendType="none" />,
            <Line key={`spike${index}`} dataKey={`spike${index}`} name={`${disease} · vượt ngưỡng`} stroke="transparent" dot={{ r: 5, fill: colors[index] }} legendType="none" />,
          ] : [
            <Area key={`band${index}`} dataKey={`band${index}`} name={`${disease} · khoảng ${Math.round(intervalWidth * 100)}%`} fill={colors[index]} fillOpacity={0.1} stroke="none" legendType="none" />,
            <Line key={`forecast${index}`} dataKey={`forecast${index}`} name={`${disease} · dự báo`} stroke={colors[index]} strokeWidth={2} strokeDasharray="6 4" dot={{ r: 3 }} legendType="none" />,
          ])}
        </ComposedChart>
      </ResponsiveContainer>
    </div>
    <p className="text-xs text-muted-foreground">{mode === "zscore" ? "Mỗi màu là một bệnh. Nét liền: số bài/ngày; nét mờ: trung bình 14 ngày; nét đứt: ngưỡng MA + 2σ; chấm tròn: ngày vượt ngưỡng." : "Mỗi màu là một bệnh. Nét liền: bài thực tế; nét đứt: dự báo; vùng mờ: khoảng dự báo."} Các chuỗi được tính riêng, không cộng dồn.</p>
  </>;
}

export function DiseaseTrendAnalysis() {
  const [activeMode, setActiveMode] = useState<Mode>('zscore');
  const [selectedDiseases, setSelectedDiseases] = useState<string[]>([]);
  const [days, setDays] = useState(30);
  const [intervalWidth, setIntervalWidth] = useState(0.8);
  const [exporting, setExporting] = useState<string | null>(null);
  const { isGuest } = useAuth();
  const { toast } = useToast();
  const analysis = useQuery<AnalysisSnapshot>({
    queryKey: ['interactive-analysis', activeMode, selectedDiseases, days, intervalWidth],
    queryFn: async ({ signal }) => {
      const response = await fetch('/api/report/interactive-data', {
        method: 'POST', signal,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ diseases: selectedDiseases, mode: activeMode, days, interval_width: intervalWidth }),
      });
      if (!response.ok) throw new Error('Không tải được dữ liệu. Vui lòng thử lại.');
      return response.json();
    },
    enabled: selectedDiseases.length > 0,
    staleTime: 300_000, refetchOnWindowFocus: false,
  });
  const exportReport = async (mode: Mode) => {
    if (!analysis.data || analysis.isFetching || analysis.isError) return;
    setExporting(mode);
    try {
      const token = localStorage.getItem('token');
      const response = await fetch('/api/report/interactive-export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
        body: JSON.stringify({ diseases: selectedDiseases, mode, days, interval_width: intervalWidth, format: 'docx', snapshot_id: analysis.data.snapshot_id }),
      });
      if (response.status === 410) {
        await analysis.refetch();
        throw new Error('Đã tải lại bản phân tích do dữ liệu cũ hết hạn. Vui lòng kiểm tra kết quả mới rồi xuất Word lại.');
      }
      if (!response.ok) throw new Error(response.status === 401 ? 'Vui lòng đăng nhập để xuất báo cáo.' : 'Không tạo được báo cáo phân tích. Vui lòng thử lại.');
      const url = URL.createObjectURL(await response.blob());
      const link = document.createElement('a');
      link.href = url;
      link.download = `PhanTich_${mode}_${new Date().toISOString().slice(0, 10)}.docx`;
      link.click();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
      toast({ title: 'Đã xuất báo cáo phân tích', description: `${selectedDiseases.length} bệnh, dữ liệu tách riêng theo bệnh.` });
    } catch (error) {
      toast({ title: 'Xuất báo cáo thất bại', description: error instanceof Error ? error.message : 'Vui lòng thử lại.', variant: 'destructive' });
    } finally {
      setExporting(null);
    }
  };

  return <section aria-label="Phân tích riêng từng bệnh">
    <Tabs value={activeMode} onValueChange={value => setActiveMode(value as Mode)} className="space-y-6">
      <TabsList className="grid w-full grid-cols-2"><TabsTrigger value="zscore">Phát hiện Đột biến</TabsTrigger><TabsTrigger value="forecast">Dự báo xu hướng báo chí</TabsTrigger></TabsList>
      {(["zscore", "forecast"] as const).map(mode => <TabsContent key={mode} value={mode} className="space-y-6">
        <Card>
          <CardHeader className="flex flex-col justify-between gap-4 sm:flex-row sm:items-start">
            <div className="space-y-2">
              <CardTitle>{mode === "zscore" ? "Mô hình cảnh báo đột biến" : "Xu hướng sự quan tâm"}</CardTitle>
              <CardDescription>{mode === "zscore" ? "Phát hiện bất thường của lượt bài theo đường nền riêng cho từng bệnh." : "Prophet dự báo lượt bài theo từng bệnh trong 7 ngày tới."} Chọn tối đa 6 bệnh để so sánh.</CardDescription>
              <div className="flex flex-wrap items-center gap-2 pt-2 text-sm"><span>{mode === "zscore" ? "Khoảng quan sát:" : "Khoảng dự báo:"}</span>
                {mode === "zscore" ? [30, 60, 90].map(value => <Button key={value} size="sm" variant={days === value ? "default" : "outline"} onClick={() => setDays(value)}>{value} ngày</Button>) : [0.8, 0.95].map(value => <Button key={value} size="sm" variant={intervalWidth === value ? "default" : "outline"} onClick={() => setIntervalWidth(value)}>{Math.round(value * 100)}%</Button>)}
              </div>
            </div>
            <div className="flex shrink-0 flex-col items-start gap-3 sm:items-end">
              <DiseaseSelectorModal selectedDiseases={selectedDiseases} onChange={values => setSelectedDiseases(values.slice(0, 6))} maxSelect={6} triggerButtonText="Chọn tối đa 6 bệnh" />
              <div className="flex gap-2">
                <Button size="sm" variant="outline" disabled={isGuest || !analysis.data || analysis.isFetching || analysis.isError || exporting !== null} title={isGuest ? 'Đăng nhập để xuất báo cáo' : 'Xuất đúng bản dữ liệu và nhận xét đang hiển thị'} onClick={() => void exportReport(mode)}>{exporting === mode ? 'Đang xuất...' : 'Xuất Word'}</Button>
              </div>
            </div>
          </CardHeader>
          <CardContent><ComparisonChart diseases={selectedDiseases} mode={mode} intervalWidth={intervalWidth} query={analysis} />
            {analysis.data && <p className="mt-2 text-xs text-muted-foreground">Thời điểm tổng hợp: {new Date(analysis.data.generated_at).toLocaleString('vi-VN')} · Word sử dụng đúng bản dữ liệu này. <Button variant="link" size="sm" disabled={analysis.isFetching || exporting !== null} onClick={() => void analysis.refetch()}>Cập nhật dữ liệu</Button></p>}
          </CardContent>
        </Card>
        <div className="grid items-start gap-6 lg:grid-cols-2">{selectedDiseases.map((disease, index) => <DiseasePanel key={`${mode}-${disease}`} disease={disease} mode={mode} days={days} intervalWidth={intervalWidth} section={analysis.data?.sections[index]} query={analysis} />)}</div>
      </TabsContent>)}
    </Tabs>
  </section>;
}
