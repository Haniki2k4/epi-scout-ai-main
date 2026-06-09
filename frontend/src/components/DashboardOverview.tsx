import { useEffect, useState, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Globe, Activity, Info, MapPin, Component } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  BarChart,
  Bar,
  Legend,
} from "recharts";
import { MapShell, MapShellRef } from "./map/MapShell";
import { createProvinceDotLayers, prepareLocationData, MappedLocation } from "./map/ProvinceDotLayer";
import { DiseaseSelectorModal } from "./DiseaseSelectorModal";
import { AISummaryCard } from "./AISummaryCard";

// ── Types ────────────────────────────────────────────────────────────────────

interface TopDisease { disease_name: string; article_count: number }
interface LocationItem {
  location: string;
  total_mentions: number;
  total_cases: number;
  diseases: { disease_name: string; mentions: number; cases: number }[];
}
interface StackedTrend { date: string;[disease: string]: number | string }
interface StackedResult { dates: string[]; diseases: string[]; data: StackedTrend[] }

// ── Constants ─────────────────────────────────────────────────────────────────

type MonthOption = { label: string; months?: number; days?: number };
const MONTH_OPTIONS: MonthOption[] = [
  { label: "1 tuần", days: 7 },
  { label: "2 tuần", days: 14 },
  { label: "1 tháng", months: 1 },
  { label: "3 tháng", months: 3 },
  { label: "6 tháng", months: 6 },
  { label: "12 tháng", months: 12 },
];
const BOW_DAYS_OPTIONS = [7, 14, 30, 90];
const LOCATION_FILTER_OPTIONS = [
  { label: "30 ngày gần nhất", days: 30, month: null, year: null },
];
const now = new Date();
for (let i = 0; i < 6; i++) {
  const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
  const m = d.getMonth() + 1;
  const y = d.getFullYear();
  LOCATION_FILTER_OPTIONS.push({ label: `Tháng ${m}/${y}`, days: 30, month: m, year: y });
}

const DASHBOARD_KW_KEY = "epi-scout-dashboard-keywords";

function loadSavedKeywords(): { stacked: string[]; interest: string[] } {
  try {
    const raw = localStorage.getItem(DASHBOARD_KW_KEY);
    if (!raw) return { stacked: [], interest: [] };
    return JSON.parse(raw);
  } catch {
    return { stacked: [], interest: [] };
  }
}

const DISEASE_COLORS = [
  "#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ec4899",
  "#eab308", "#06b6d4", "#ef4444", "#84cc16", "#64748b",
];

// ── Component ─────────────────────────────────────────────────────────────────

// ── Fetch helpers ──────────────────────────────────────────────────────────

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

// ── Component ─────────────────────────────────────────────────────────────────

const DashboardOverview = () => {
  const [selectedPeriod, setSelectedPeriod] = useState<MonthOption>(MONTH_OPTIONS[2]);

  const [hoveredLocation, setHoveredLocation] = useState<(MappedLocation & { x: number, y: number }) | null>(null);
  const [locationFilterIdx, setLocationFilterIdx] = useState(0);

  const mapRef = useRef<MapShellRef>(null);

  const { data: geoJsonData } = useQuery({
    queryKey: ['geo-json'],
    queryFn: () => fetchJson<any>('/vn_map_lite.geojson'),
    staleTime: Infinity, // GeoJSON không bao giờ thay đổi
  });

  const [stackedDays, setStackedDays] = useState(30);
  const [interestDays, setInterestDays] = useState(30);
  const [selectedStackedDiseases, setSelectedStackedDiseases] = useState<string[]>(() => loadSavedKeywords().stacked);
  const [selectedInterestDiseases, setSelectedInterestDiseases] = useState<string[]>(() => loadSavedKeywords().interest);

  useEffect(() => {
    localStorage.setItem(DASHBOARD_KW_KEY, JSON.stringify({
      stacked: selectedStackedDiseases,
      interest: selectedInterestDiseases,
    }));
  }, [selectedStackedDiseases, selectedInterestDiseases]);

  // ── Queries (cached by TanStack Query) ─────────────────────────────────────

  const { data: stats } = useQuery({
    queryKey: ['stats-overview'],
    queryFn: () => fetchJson<{
      total_events_7d: number;
      keywords_today: number;
      keywords_7d: number;
      top_disease: string | null;
      top_disease_mentions: number;
    }>('/api/stats/overview'),
    placeholderData: {
      total_events_7d: 0,
      keywords_today: 0,
      keywords_7d: 0,
      top_disease: null,
      top_disease_mentions: 0,
    },
  });

  const topDiseasesUrl = selectedPeriod.days
    ? `/api/stats/top-diseases?days=${selectedPeriod.days}`
    : `/api/stats/top-diseases?months=${selectedPeriod.months}`;

  const { data: topDiseases = [], isLoading: loadingTopDiseases } = useQuery({
    queryKey: ['top-diseases', selectedPeriod.label],
    queryFn: () => fetchJson<TopDisease[]>(topDiseasesUrl),
  });

  const locationFilter = LOCATION_FILTER_OPTIONS[locationFilterIdx];
  const locationUrl = locationFilter.month && locationFilter.year
    ? `/api/stats/heatmap?days=${locationFilter.days}&month=${locationFilter.month}&year=${locationFilter.year}`
    : `/api/stats/heatmap?days=${locationFilter.days}`;

  const { data: locationData = [] } = useQuery({
    queryKey: ['heatmap', locationFilterIdx],
    queryFn: () => fetchJson<LocationItem[]>(locationUrl),
  });

  const { data: interestResult } = useQuery({
    queryKey: ['interest-trends', interestDays],
    queryFn: () => fetchJson<StackedResult>(`/api/stats/interest-trends?days=${interestDays}`),
  });

  // Auto-select top 5 diseases khi data interest mới về và chưa có lựa chọn
  useEffect(() => {
    if (!interestResult || !Array.isArray(interestResult.diseases)) return;
    setSelectedInterestDiseases(prev => {
      if (prev.length) return prev;
      const seen = new Set<string>();
      return interestResult.diseases.filter((d: string) => {
        const key = d.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, 5);
    });
  }, [interestResult]);

  const { data: stackedResult } = useQuery({
    queryKey: ['stacked-trends', stackedDays],
    queryFn: () => fetchJson<StackedResult>(`/api/stats/stacked-trends?days=${stackedDays}`),
  });

  // Auto-select top 5 diseases khi data stacked mới về và chưa có lựa chọn
  useEffect(() => {
    if (!stackedResult || !Array.isArray(stackedResult.diseases)) return;
    setSelectedStackedDiseases(prev => {
      if (prev.length) return prev;
      const seen = new Set<string>();
      return stackedResult.diseases.filter((d: string) => {
        const key = d.toLowerCase();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      }).slice(0, 5);
    });
  }, [stackedResult]);

  // ── Derived ──────────────────────────────────────────────────────────────────

  const maxRiskScore = (Array.isArray(locationData) && locationData.length > 0)
    ? ((locationData[0] as any).risk_score || locationData[0].total_mentions) : 1;

  useEffect(() => {
    if (mapRef.current) {
      const mappedData = prepareLocationData(locationData);
      const layers = createProvinceDotLayers(geoJsonData, mappedData, maxRiskScore, (info) => {
        if (info.object && info.x !== undefined && info.y !== undefined) {
          setHoveredLocation({ ...info.object, x: info.x, y: info.y });
        } else {
          setHoveredLocation(null);
        }
      });
      mapRef.current.setLayers(layers);
    }
  }, [locationData, geoJsonData, maxRiskScore]);

  const stackedChartData = stackedResult?.data.map((row) => ({
    ...row,
    name: row.date.split("-").slice(1).join("/"),
  })) ?? [];

  const interestChartData = interestResult?.data.map((row) => ({
    ...row,
    name: row.date.split("-").slice(1).join("/"),
  })) ?? [];

  // ── Render ───────────────────────────────────────────────────────────────────

  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-4">
        <Card className="border-l-4 border-l-primary">
          <CardHeader className="pb-3">
            <CardDescription>Sự kiện cảnh báo (7 ngày)</CardDescription>
            <CardTitle className="text-3xl">{stats?.total_events_7d?.toLocaleString() ?? 0}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Activity className="h-4 w-4 text-primary" />
              <span className="text-muted-foreground">Sự kiện đang theo dõi</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-destructive">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh được quan tâm nhất (30d)</CardDescription>
            <CardTitle className="text-xl leading-tight truncate" title={stats?.top_disease ?? "—"}>
              {stats?.top_disease ?? "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-muted-foreground">
                {(stats?.top_disease_mentions ?? 0) > 0 ? `${stats?.top_disease_mentions} bài nhắc đến` : "Chưa có dữ liệu"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh có tin mới (Hôm nay)</CardDescription>
            <CardTitle className="text-3xl">{stats?.keywords_today?.toLocaleString() ?? 0}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Component className="h-4 w-4 text-amber-500" />
              <span className="text-muted-foreground">Loại dịch bệnh phát sinh tin</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-emerald-500">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh có tin mới (7 ngày)</CardDescription>
            <CardTitle className="text-3xl">{stats?.keywords_7d?.toLocaleString() ?? 0}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Globe className="h-4 w-4 text-emerald-500" />
              <span className="text-muted-foreground">Tổng số loại bệnh 7 ngày qua</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <AISummaryCard />

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-t-4 border-t-primary">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle>Xu hướng ca bệnh theo loại</CardTitle>
                <CardDescription>Số ca từng bệnh theo ngày</CardDescription>
              </div>
              <div className="flex gap-2">
                {stackedResult && Array.isArray(stackedResult.diseases) && stackedResult.diseases.length > 0 && (
                  <DiseaseSelectorModal
                    selectedDiseases={selectedStackedDiseases}
                    onChange={setSelectedStackedDiseases}
                    maxSelect={5}
                    triggerButtonText={`Chọn bệnh (${selectedStackedDiseases.length}/5)`}
                  />
                )}
                <select
                  value={stackedDays}
                  onChange={(e) => setStackedDays(Number(e.target.value))}
                  className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
                >
                  <option value={7}>7 ngày</option>
                  <option value={14}>14 ngày</option>
                  <option value={30}>30 ngày</option>
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {(!stackedResult || !Array.isArray(stackedResult.diseases) || stackedResult.diseases.length === 0) ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
                Chưa có dữ liệu
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={stackedChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <YAxis stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {selectedStackedDiseases.map((disease, i) => (
                    <Line
                      key={disease}
                      type="monotone"
                      dataKey={disease}
                      stroke={DISEASE_COLORS[i % DISEASE_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle>Top 10 bệnh dịch được nhắc đến</CardTitle>
                <CardDescription>Đếm số bài viết nhắc đến từng bệnh</CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <label className="text-sm text-muted-foreground whitespace-nowrap">Trong:</label>
                <select
                  value={selectedPeriod.label}
                  onChange={(e) => {
                    const opt = MONTH_OPTIONS.find(o => o.label === e.target.value);
                    if (opt) setSelectedPeriod(opt);
                  }}
                  className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
                >
                  {MONTH_OPTIONS.map((opt) => (
                    <option key={opt.label} value={opt.label}>{opt.label}</option>
                  ))}
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loadingTopDiseases ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">Đang tải...</div>
            ) : topDiseases.length === 0 ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">Chưa có dữ liệu</div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart layout="vertical" data={topDiseases} margin={{ top: 0, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis type="number" stroke="hsl(var(--muted-foreground))" allowDecimals={false} />
                  <YAxis type="category" dataKey="disease_name" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 12 }} width={130} />
                  <Tooltip
                    formatter={(value: number) => [`${value} bài viết`, "Số lần nhắc đến"]}
                    contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "var(--radius)" }}
                  />
                  <Bar dataKey="article_count" fill="hsl(var(--chart-2))" radius={[0, 6, 6, 0]}
                    label={{ position: "right", fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 md:grid-cols-2">
        <Card className="border-t-4 border-t-amber-500">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <MapPin className="w-5 h-5 text-amber-500" />
                  Điểm nóng dịch bệnh theo địa danh
                </CardTitle>
                <CardDescription>Hover vào địa danh để xem thống kê bệnh</CardDescription>
              </div>
              <select
                value={locationFilterIdx}
                onChange={(e) => setLocationFilterIdx(Number(e.target.value))}
                className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
              >
                {LOCATION_FILTER_OPTIONS.map((opt, i) => (
                  <option key={i} value={i}>{opt.label}</option>
                ))}
              </select>
            </div>
          </CardHeader>
          <CardContent className="p-0 relative">
            <div className="relative w-full h-[400px]">
              <MapShell ref={mapRef} className="absolute inset-0 rounded-b-xl overflow-hidden" />
              {(Array.isArray(locationData) && locationData.length === 0) && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-yellow-400/60 backdrop-blur-md text-yellow-950 px-6 py-2 text-center text-sm font-medium z-10 rounded-full border border-yellow-500/30 shadow-md shadow-yellow-500/10 whitespace-nowrap">
                  Chưa có dữ liệu địa danh cụ thể trong khoảng thời gian này
                </div>
              )}
              {hoveredLocation && (
                <div
                  className="absolute z-50 bg-card border border-border rounded-lg shadow-lg p-3 w-56 text-sm pointer-events-none"
                  style={{ left: hoveredLocation.x + 15, top: hoveredLocation.y + 15 }}
                >
                  <p className="font-semibold text-foreground mb-1">📍 {hoveredLocation.name}</p>
                  <p className="text-muted-foreground text-xs mb-2">
                    {hoveredLocation.mentions} lượt nhắc · {hoveredLocation.cases.toLocaleString()} ca
                  </p>
                  <div className="space-y-1">
                    {Array.isArray(hoveredLocation.diseases) && hoveredLocation.diseases.map((d) => (
                      <div key={d.disease_name} className="flex justify-between text-xs">
                        <span className="truncate text-foreground">{d.disease_name}</span>
                        <span className="text-muted-foreground shrink-0 ml-2">{d.mentions} bài</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-t-4 border-t-emerald-500">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Component className="w-5 h-5 text-emerald-500" />
                  Sự quan tâm truyền thông
                </CardTitle>
                <CardDescription>Số lượng bài báo nhắc đến top bệnh theo ngày</CardDescription>
              </div>
              <div className="flex gap-2">
                {interestResult && Array.isArray(interestResult.diseases) && interestResult.diseases.length > 0 && (
                  <DiseaseSelectorModal
                    selectedDiseases={selectedInterestDiseases}
                    onChange={setSelectedInterestDiseases}
                    maxSelect={5}
                    triggerButtonText={`Chọn bệnh (${selectedInterestDiseases.length}/5)`}
                  />
                )}
                <select
                  value={interestDays}
                  onChange={(e) => setInterestDays(Number(e.target.value))}
                  className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
                >
                  {BOW_DAYS_OPTIONS.map((d) => <option key={d} value={d}>{d} ngày</option>)}
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {(!interestResult || !Array.isArray(interestResult.diseases) || interestResult.diseases.length === 0) ? (
              <div className="flex items-center justify-center h-[350px] text-muted-foreground text-sm">
                Chưa có dữ liệu biểu diễn
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={350}>
                <LineChart data={interestChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <YAxis stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {selectedInterestDiseases.map((disease, i) => (
                    <Line
                      key={disease}
                      type="monotone"
                      dataKey={disease}
                      stroke={DISEASE_COLORS[(i + 5) % DISEASE_COLORS.length]}
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4 }}
                    />
                  ))}
                </LineChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DashboardOverview;
