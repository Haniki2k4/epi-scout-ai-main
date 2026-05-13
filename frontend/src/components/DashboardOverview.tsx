import { useEffect, useState, useCallback, useRef } from "react";
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

const DISEASE_COLORS = [
  "#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ec4899",
  "#eab308", "#06b6d4", "#ef4444", "#84cc16", "#64748b",
];

// ── Component ─────────────────────────────────────────────────────────────────

const DashboardOverview = () => {
  const [stats, setStats] = useState({
    total_events_7d: 0,
    keywords_today: 0,
    keywords_7d: 0,
    top_disease: null as string | null,
    top_disease_mentions: 0,
  });
  const [topDiseases, setTopDiseases] = useState<TopDisease[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<MonthOption>(MONTH_OPTIONS[2]);
  const [loadingTopDiseases, setLoadingTopDiseases] = useState(false);

  const [locationData, setLocationData] = useState<LocationItem[]>([]);
  const [hoveredLocation, setHoveredLocation] = useState<(MappedLocation & { x: number, y: number }) | null>(null);
  const [locationFilterIdx, setLocationFilterIdx] = useState(0);

  const mapRef = useRef<MapShellRef>(null);
  const [geoJsonData, setGeoJsonData] = useState<any>(null);

  useEffect(() => {
    fetch('/vn_map_lite.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error("Could not load map json:", err));
  }, []);

  const [interestResult, setInterestResult] = useState<StackedResult | null>(null);
  const [stackedResult, setStackedResult] = useState<StackedResult | null>(null);
  const [stackedDays, setStackedDays] = useState(30);
  const [interestDays, setInterestDays] = useState(30);
  const [selectedStackedDiseases, setSelectedStackedDiseases] = useState<string[]>([]);
  const [selectedInterestDiseases, setSelectedInterestDiseases] = useState<string[]>([]);

  // ── Fetches ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats/overview");
        if (res.ok) {
          const data = await res.json();
          if (data && typeof data === 'object') setStats(prev => ({ ...prev, ...data }));
        }
      } catch { }
    };
    fetchStats();
  }, []);

  useEffect(() => {
    const fetchTopDiseases = async () => {
      setLoadingTopDiseases(true);
      try {
        const url = selectedPeriod.days
          ? `/api/stats/top-diseases?days=${selectedPeriod.days}`
          : `/api/stats/top-diseases?months=${selectedPeriod.months}`;
        const res = await fetch(url);
        if (res.ok) {
          const data = await res.json();
          setTopDiseases(Array.isArray(data) ? data : []);
        }
      } catch { } finally { setLoadingTopDiseases(false); }
    };
    fetchTopDiseases();
  }, [selectedPeriod]);

  const fetchLocation = useCallback(async (idx: number) => {
    const filter = LOCATION_FILTER_OPTIONS[idx];
    let url = `/api/stats/heatmap?days=${filter.days}`;
    if (filter.month && filter.year) url += `&month=${filter.month}&year=${filter.year}`;
    try {
      const res = await fetch(url);
      if (res.ok) {
        const data = await res.json();
        setLocationData(Array.isArray(data) ? data : []);
      }
    } catch { }
  }, []);

  useEffect(() => { fetchLocation(locationFilterIdx); }, [locationFilterIdx, fetchLocation]);

  useEffect(() => {
    const fetchInterest = async () => {
      try {
        const res = await fetch(`/api/stats/interest-trends?days=${interestDays}`);
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.diseases)) {
            setInterestResult(data);
            setSelectedInterestDiseases(data.diseases.slice(0, 5));
          }
        }
      } catch { }
    };
    fetchInterest();
  }, [interestDays]);

  useEffect(() => {
    const fetchStacked = async () => {
      try {
        const res = await fetch(`/api/stats/stacked-trends?days=${stackedDays}`);
        if (res.ok) {
          const data = await res.json();
          if (data && Array.isArray(data.diseases)) {
            setStackedResult(data);
            setSelectedStackedDiseases(data.diseases.slice(0, 5));
          }
        }
      } catch { }
    };
    fetchStacked();
  }, [stackedDays]);

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
            <CardTitle className="text-3xl">{stats.total_events_7d?.toLocaleString() ?? 0}</CardTitle>
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
            <CardTitle className="text-xl leading-tight truncate" title={stats.top_disease ?? "—"}>
              {stats.top_disease ?? "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-muted-foreground">
                {stats.top_disease_mentions > 0 ? `${stats.top_disease_mentions} bài nhắc đến` : "Chưa có dữ liệu"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-amber-500">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh có tin mới (Hôm nay)</CardDescription>
            <CardTitle className="text-3xl">{stats.keywords_today?.toLocaleString() ?? 0}</CardTitle>
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
            <CardTitle className="text-3xl">{stats.keywords_7d?.toLocaleString() ?? 0}</CardTitle>
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
                <CardDescription>Số ca từng bệnh chồng theo ngày</CardDescription>
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
