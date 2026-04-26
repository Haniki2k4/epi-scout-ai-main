import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Globe, Activity, Info, MapPin, Component } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Bar,
  Legend,
} from "recharts";
import { useRef } from "react";
import { MapShell, MapShellRef } from "./map/MapShell";
import { createProvinceDotLayers, prepareLocationData, MappedLocation } from "./map/ProvinceDotLayer";

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

// label + months value (âm số = tuần): -1 = 1 tuần, -2 = 2 tuần
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
// Thêm 6 tháng trước tháng hiện tại
const now = new Date();
for (let i = 0; i < 6; i++) {
  const d = new Date(now.getFullYear(), now.getMonth() - i, 1);
  const m = d.getMonth() + 1;
  const y = d.getFullYear();
  LOCATION_FILTER_OPTIONS.push({ label: `Tháng ${m}/${y}`, days: 30, month: m, year: y });
}

// 10 màu HSL cố định (dễ in báo cáo)
const DISEASE_COLORS = [
  "#3b82f6", "#f97316", "#22c55e", "#a855f7", "#ec4899",
  "#eab308", "#06b6d4", "#ef4444", "#84cc16", "#64748b",
];

// ── Component ─────────────────────────────────────────────────────────────────

const DashboardOverview = () => {
  const [stats, setStats] = useState({
    total_articles: 0,
    total_cases: 0,
    alert_count: 0,
    top_disease: null as string | null,
    top_disease_mentions: 0,
  });
  const [topDiseases, setTopDiseases] = useState<TopDisease[]>([]);
  const [selectedPeriod, setSelectedPeriod] = useState<MonthOption>(MONTH_OPTIONS[2]); // mặc định 1 tháng
  const [loadingTopDiseases, setLoadingTopDiseases] = useState(false);

  // Location heatmap
  const [locationData, setLocationData] = useState<LocationItem[]>([]);
  const [hoveredLocation, setHoveredLocation] = useState<(MappedLocation & { x: number, y: number }) | null>(null);
  const [locationFilterIdx, setLocationFilterIdx] = useState(0);

  // DeckGL Map state
  const mapRef = useRef<MapShellRef>(null);
  const [geoJsonData, setGeoJsonData] = useState<any>(null);

  useEffect(() => {
    fetch('/vn_map_lite.geojson')
      .then(res => res.json())
      .then(data => setGeoJsonData(data))
      .catch(err => console.error("Could not load map json:", err));
  }, []);

  // Interest Trends
  const [interestResult, setInterestResult] = useState<StackedResult | null>(null);

  // Stacked line
  const [stackedResult, setStackedResult] = useState<StackedResult | null>(null);

  // Dùng state riêng cho 2 biểu đồ xu hướng
  const [stackedDays, setStackedDays] = useState(30);
  const [interestDays, setInterestDays] = useState(30);

  // Bộ lọc từ khóa cho biểu đồ xu hướng
  const [selectedStackedDiseases, setSelectedStackedDiseases] = useState<string[]>([]);
  const [selectedInterestDiseases, setSelectedInterestDiseases] = useState<string[]>([]);

  // Custom dropdown open state
  const [stackedDropdownOpen, setStackedDropdownOpen] = useState(false);
  const [interestDropdownOpen, setInterestDropdownOpen] = useState(false);

  // ── Fetches ─────────────────────────────────────────────────────────────────

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats/overview");
        if (res.ok) setStats(await res.json());
      } catch { }
    };
    fetchStats();
  }, []);

  useEffect(() => {
    const fetchTopDiseases = async () => {
      setLoadingTopDiseases(true);
      try {
        // Nếu có days thì dùng days, ngược lại dùng months
        const url = selectedPeriod.days
          ? `/api/stats/top-diseases?days=${selectedPeriod.days}`
          : `/api/stats/top-diseases?months=${selectedPeriod.months}`;
        const res = await fetch(url);
        if (res.ok) setTopDiseases(await res.json());
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
      if (res.ok) setLocationData(await res.json());
    } catch { }
  }, []);

  useEffect(() => { fetchLocation(locationFilterIdx); }, [locationFilterIdx, fetchLocation]);

  useEffect(() => {
    const fetchInterest = async () => {
      try {
        const res = await fetch(`/api/stats/interest-trends?days=${interestDays}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.diseases) {
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
          if (data && data.diseases) {
            setStackedResult(data);
            setSelectedStackedDiseases(data.diseases.slice(0, 5));
          }
        }
      } catch { }
    };
    fetchStacked();
  }, [stackedDays]);

  // ── Derived ──────────────────────────────────────────────────────────────────

  const maxMentions = locationData.length > 0 ? locationData[0].total_mentions : 1;
  const maxRiskScore = locationData.length > 0 ? (locationData[0] as any).risk_score || locationData[0].total_mentions : 1;

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

  const getBarColor = (mentions: number) => {
    const ratio = mentions / maxMentions;
    if (ratio >= 0.8) return "bg-red-500";
    if (ratio >= 0.5) return "bg-orange-400";
    if (ratio >= 0.25) return "bg-yellow-400";
    return "bg-emerald-400";
  };

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
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-l-4 border-l-primary">
          <CardHeader className="pb-3">
            <CardDescription>Tổng ca bệnh (ghi nhận)</CardDescription>
            <CardTitle className="text-3xl">{stats.total_cases.toLocaleString()}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Activity className="h-4 w-4 text-primary" />
              <span className="text-muted-foreground">Ca mắc mới</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-destructive">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh được nhắc nhiều nhất (30 ngày)</CardDescription>
            <CardTitle className="text-xl leading-tight truncate" title={stats.top_disease ?? "—"}>
              {stats.top_disease ?? "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-muted-foreground">
                {stats.top_disease_mentions > 0 ? `${stats.top_disease_mentions} bài viết nhắc đến` : "Chưa có dữ liệu"}
              </span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-accent">
          <CardHeader className="pb-3">
            <CardDescription>Tin tức đã quét</CardDescription>
            <CardTitle className="text-3xl">{stats.total_articles.toLocaleString()}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Globe className="h-4 w-4 text-accent" />
              <span className="text-muted-foreground">Bài viết</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Row 1: Stacked Bar + Top Diseases */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Stacked Bar Chart */}
        <Card className="border-t-4 border-t-primary">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle>Xu hướng ca bệnh theo loại</CardTitle>
                <CardDescription>Số ca từng bệnh chồng theo ngày</CardDescription>
              </div>
              <div className="flex gap-2">
                {/* Multi-select keywords dropdown */}
                {stackedResult && stackedResult.diseases.length > 0 && (
                  <div className="relative">
                    <div
                      className="text-sm border border-border rounded px-3 py-1.5 bg-background text-foreground cursor-pointer flex items-center justify-between min-w-[120px]"
                      onClick={() => setStackedDropdownOpen(!stackedDropdownOpen)}
                    >
                      <span>Chọn bệnh ({selectedStackedDiseases.length}/5)</span>
                    </div>
                    {stackedDropdownOpen && (
                      <div className="absolute top-full mt-1 right-0 bg-popover border shadow-md rounded-md p-2 z-50 w-64 max-h-60 overflow-y-auto">
                        {stackedResult.diseases.map(d => (
                          <label key={d} className="flex items-center gap-2 py-1 px-2 hover:bg-muted rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedStackedDiseases.includes(d)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  if (selectedStackedDiseases.length >= 5) return;
                                  setSelectedStackedDiseases([...selectedStackedDiseases, d]);
                                } else {
                                  setSelectedStackedDiseases(selectedStackedDiseases.filter(item => item !== d));
                                }
                              }}
                              disabled={!selectedStackedDiseases.includes(d) && selectedStackedDiseases.length >= 5}
                            />
                            <span className="text-sm line-clamp-1">{d}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
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
            {(!stackedResult || stackedResult.diseases.length === 0) ? (
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

        {/* Top 10 bệnh - bar ngang */}
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

      {/* Row 2: Heatmap địa danh + BoW */}
      <div className="grid gap-6 md:grid-cols-2">

        {/* Location Heatmap */}
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

              {/* Thanh cảnh báo nổi (pill) khi không có dữ liệu, nằm giữa không chắn nút Zoom */}
              {locationData.length === 0 && (
                <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-yellow-400/60 backdrop-blur-md text-yellow-950 px-6 py-2 text-center text-sm font-medium z-10 rounded-full border border-yellow-500/30 shadow-md shadow-yellow-500/10 whitespace-nowrap">
                  Chưa có dữ liệu địa danh cụ thể trong khoảng thời gian này
                </div>
              )}

              {/* Tooltip hiển thị khi hover lên chấm bản đồ */}
              {hoveredLocation && locationData.length > 0 && (
                <div
                  className="absolute z-50 bg-card border border-border rounded-lg shadow-lg p-3 w-56 text-sm pointer-events-none"
                  style={{ left: hoveredLocation.x + 15, top: hoveredLocation.y + 15 }}
                >
                  <p className="font-semibold text-foreground mb-1">📍 {hoveredLocation.name}</p>
                  <p className="text-muted-foreground text-xs mb-2">
                    {hoveredLocation.mentions} lượt nhắc · {hoveredLocation.cases.toLocaleString()} ca
                  </p>
                  <div className="space-y-1">
                    {hoveredLocation.diseases.map((d) => (
                      <div key={d.disease_name} className="flex justify-between text-xs">
                        <span className="truncate text-foreground">{d.disease_name}</span>
                        <span className="text-muted-foreground shrink-0 ml-2">{d.mentions} bài</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            {/* Legend màu được đính đè góc Map */}
            {locationData.length > 0 && (
              <div className="absolute bottom-4 right-4 bg-background/80 backdrop-blur-md rounded-md border border-border p-2 flex items-center gap-2 text-[10px] text-muted-foreground shadow-sm">
                <span>Tâm dịch bé</span>
                <div className="w-2 h-2 rounded-full bg-red-400 opacity-50" />
                <div className="w-3 h-3 rounded-full bg-red-500 opacity-80" />
                <div className="w-5 h-5 rounded-full bg-red-600 opacity-100 flex items-center justify-center shadow-red-500/50 shadow-md">
                  <div className="w-2 h-2 rounded-full bg-background" />
                </div>
                <span>Tâm dịch lớn</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sự Quan Tâm - Line Chart thay thế WordCloud */}
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
                {/* Multi-select keywords dropdown */}
                {interestResult && interestResult.diseases.length > 0 && (
                  <div className="relative">
                    <div
                      className="text-sm border border-border rounded px-3 py-1.5 bg-background text-foreground cursor-pointer flex items-center justify-between min-w-[120px]"
                      onClick={() => setInterestDropdownOpen(!interestDropdownOpen)}
                    >
                      <span>Chọn bệnh ({selectedInterestDiseases.length}/5)</span>
                    </div>
                    {interestDropdownOpen && (
                      <div className="absolute top-full mt-1 right-0 bg-popover border shadow-md rounded-md p-2 z-50 w-64 max-h-60 overflow-y-auto">
                        {interestResult.diseases.map(d => (
                          <label key={d} className="flex items-center gap-2 py-1 px-2 hover:bg-muted rounded cursor-pointer">
                            <input
                              type="checkbox"
                              checked={selectedInterestDiseases.includes(d)}
                              onChange={(e) => {
                                if (e.target.checked) {
                                  if (selectedInterestDiseases.length >= 5) return;
                                  setSelectedInterestDiseases([...selectedInterestDiseases, d]);
                                } else {
                                  setSelectedInterestDiseases(selectedInterestDiseases.filter(item => item !== d));
                                }
                              }}
                              disabled={!selectedInterestDiseases.includes(d) && selectedInterestDiseases.length >= 5}
                            />
                            <span className="text-sm line-clamp-1">{d}</span>
                          </label>
                        ))}
                      </div>
                    )}
                  </div>
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
            {(!interestResult || interestResult.diseases.length === 0) ? (
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

      {/* Banner đề xuất */}
      <Card className="border border-dashed border-blue-400 bg-blue-50/10">
        <CardContent className="flex items-start gap-4 pt-5 pb-5">
          <div className="h-10 w-10 flex-shrink-0 rounded-lg bg-blue-500/10 flex items-center justify-center">
            <Globe className="h-5 w-5 text-blue-500" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-foreground mb-1">💡 Đề xuất: Mở rộng giám sát quốc tế</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Hệ thống hiện chỉ theo dõi các nguồn tin trong nước. Có thể tích hợp thêm dữ liệu từ{" "}
              <span className="font-medium text-foreground">WHO Disease Outbreak</span>,{" "}
              <span className="font-medium text-foreground">CDC Global</span>,{" "}
              <span className="font-medium text-foreground">ProMED-mail</span>,{" "}
              <span className="font-medium text-foreground">HealthMap</span> và các RSS feed dịch tễ quốc tế
              để phát hiện sớm các dịch bệnh xuyên biên giới.
            </p>
          </div>
          <div className="flex-shrink-0">
            <span className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-full bg-blue-500/10 text-blue-600 font-medium">
              <Info className="h-3 w-3" /> Đề xuất
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default DashboardOverview;
