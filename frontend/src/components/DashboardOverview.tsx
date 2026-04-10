import { useEffect, useState, useCallback } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Globe, Activity, Info, MapPin, Component } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import {
  BarChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Bar,
  Legend,
} from "recharts";

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

const MONTH_OPTIONS = [1, 2, 3, 6, 12];
const BOW_DAYS_OPTIONS = [7, 30, 90];
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
  const [selectedMonths, setSelectedMonths] = useState(1);
  const [loadingTopDiseases, setLoadingTopDiseases] = useState(false);

  // Location heatmap
  const [locationData, setLocationData] = useState<LocationItem[]>([]);
  const [hoveredLocation, setHoveredLocation] = useState<LocationItem | null>(null);
  const [locationFilterIdx, setLocationFilterIdx] = useState(0);

  // BoW
  const [bowData, setBowData] = useState<{ word: string; value: number }[]>([]);
  const [bowDays, setBowDays] = useState(30);

  // Stacked bar
  const [stackedResult, setStackedResult] = useState<StackedResult | null>(null);
  const [stackedDays, setStackedDays] = useState(30);

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
        const res = await fetch(`/api/stats/top-diseases?months=${selectedMonths}`);
        if (res.ok) setTopDiseases(await res.json());
      } catch { } finally { setLoadingTopDiseases(false); }
    };
    fetchTopDiseases();
  }, [selectedMonths]);

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
    const fetchBow = async () => {
      try {
        const res = await fetch(`/api/stats/bow?days=${bowDays}`);
        if (res.ok) setBowData(await res.json());
      } catch { }
    };
    fetchBow();
  }, [bowDays]);

  useEffect(() => {
    const fetchStacked = async () => {
      try {
        const res = await fetch(`/api/stats/stacked-trends?days=${stackedDays}`);
        if (res.ok) {
          const data = await res.json();
          if (data && data.diseases) setStackedResult(data);
        }
      } catch { }
    };
    fetchStacked();
  }, [stackedDays]);

  // ── Derived ──────────────────────────────────────────────────────────────────

  const maxMentions = locationData.length > 0 ? locationData[0].total_mentions : 1;
  const maxBowValue = Math.max(...bowData.map((d) => d.value), 1);

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
          </CardHeader>
          <CardContent>
            {(!stackedResult || stackedResult.diseases.length === 0) ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
                Chưa có dữ liệu
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={stackedChartData} margin={{ top: 4, right: 8, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 10 }} />
                  <YAxis stroke="hsl(var(--muted-foreground))" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                      fontSize: 12,
                    }}
                  />
                  <Legend wrapperStyle={{ fontSize: 11 }} />
                  {stackedResult.diseases.map((disease, i) => (
                    <Bar
                      key={disease}
                      dataKey={disease}
                      stackId="a"
                      fill={DISEASE_COLORS[i % DISEASE_COLORS.length]}
                      radius={i === stackedResult.diseases.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]}
                    />
                  ))}
                </BarChart>
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
                  value={selectedMonths}
                  onChange={(e) => setSelectedMonths(Number(e.target.value))}
                  className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
                >
                  {MONTH_OPTIONS.map((m) => (
                    <option key={m} value={m}>{m} tháng</option>
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
          <CardContent>
            {locationData.length === 0 ? (
              <div className="flex items-center justify-center h-[300px] text-sm text-muted-foreground">
                Chưa có dữ liệu địa danh cụ thể trong khoảng thời gian này
              </div>
            ) : (
              <div className="relative space-y-2 max-h-[300px] overflow-y-auto pr-2 custom-scrollbar">
                {locationData.map((loc, i) => {
                  const ratio = loc.total_mentions / maxMentions;
                  return (
                    <div
                      key={loc.location}
                      className="group relative"
                      onMouseEnter={() => setHoveredLocation(loc)}
                      onMouseLeave={() => setHoveredLocation(null)}
                    >
                      <div className="flex items-center gap-2 cursor-pointer">
                        <span className="w-5 text-xs text-muted-foreground shrink-0 text-right">{i + 1}</span>
                        <span className="w-32 shrink-0 text-sm font-medium truncate" title={loc.location}>{loc.location}</span>
                        <div className="flex-1 bg-secondary rounded-full h-5 overflow-hidden">
                          <div
                            className={`h-full rounded-full transition-all duration-300 ${getBarColor(loc.total_mentions)}`}
                            style={{ width: `${(ratio * 100).toFixed(1)}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground shrink-0 w-8 text-right">{loc.total_mentions}</span>
                      </div>

                      {/* Tooltip khi hover */}
                      {hoveredLocation?.location === loc.location && (
                        <div className="absolute left-36 top-1 z-50 bg-card border border-border rounded-lg shadow-lg p-3 w-56 text-sm pointer-events-none">
                          <p className="font-semibold text-foreground mb-1">📍 {loc.location}</p>
                          <p className="text-muted-foreground text-xs mb-2">
                            {loc.total_mentions} lượt nhắc · {loc.total_cases.toLocaleString()} ca
                          </p>
                          <div className="space-y-1">
                            {loc.diseases.map((d) => (
                              <div key={d.disease_name} className="flex justify-between text-xs">
                                <span className="truncate text-foreground">{d.disease_name}</span>
                                <span className="text-muted-foreground shrink-0 ml-2">{d.mentions} bài</span>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
            {/* Legend màu */}
            <div className="flex items-center gap-2 text-[10px] text-muted-foreground mt-4 justify-end">
              <span>Ít</span>
              <div className="w-3 h-3 rounded-full bg-emerald-400" />
              <div className="w-3 h-3 rounded-full bg-yellow-400" />
              <div className="w-3 h-3 rounded-full bg-orange-400" />
              <div className="w-3 h-3 rounded-full bg-red-500" />
              <span>Nhiều</span>
            </div>
          </CardContent>
        </Card>

        {/* Bag of Words - Word Cloud */}
        <Card className="border-t-4 border-t-emerald-500">
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <Component className="w-5 h-5 text-emerald-500" />
                  Word Cloud (Từ khóa trọng tâm)
                </CardTitle>
                <CardDescription>Tần suất từ khóa dịch bệnh - Word Cloud</CardDescription>
              </div>
              <select
                value={bowDays}
                onChange={(e) => setBowDays(Number(e.target.value))}
                className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
              >
                {BOW_DAYS_OPTIONS.map((d) => <option key={d} value={d}>{d} ngày</option>)}
              </select>
            </div>
          </CardHeader>
          <CardContent>
            <div className="relative flex flex-wrap items-center justify-center content-center gap-x-4 gap-y-2 h-[350px] overflow-hidden p-6 rounded-xl bg-gradient-to-br from-secondary/20 to-secondary/5 border border-emerald-500/10 shadow-inner">
              {bowData.length === 0 ? (
                <div className="text-sm text-muted-foreground">Chưa đủ dữ liệu biểu diễn</div>
              ) : (
                bowData.map((w, idx) => {
                  const ratio = w.value / maxBowValue;
                  // Font size phân cấp mạnh từ 12px đến 48px
                  const fontSize = Math.floor(12 + Math.pow(ratio, 1.5) * 48);

                  // Palette màu sắc đa dạng giống ảnh mẫu (Purple, Teal, Green, Orange, Blue)
                  const cloudColors = [
                    "text-purple-600 dark:text-purple-400",
                    "text-emerald-600 dark:text-emerald-400",
                    "text-blue-600 dark:text-blue-400",
                    "text-amber-600 dark:text-amber-400",
                    "text-rose-600 dark:text-rose-400",
                    "text-indigo-600 dark:text-indigo-400",
                    "text-cyan-600 dark:text-cyan-400"
                  ];
                  const colorClass = cloudColors[idx % cloudColors.length];

                  // Tạo độ xoay nhẹ ngẫu nhiên (-5 đến 5 độ) để trông tự nhiên
                  const rotation = (idx % 3 === 0) ? (idx % 2 === 0 ? "rotate-2" : "-rotate-2") : "";

                  return (
                    <span
                      key={w.word + idx}
                      title={`${w.word}: ${w.value} bài`}
                      style={{
                        fontSize: `${fontSize}px`,
                        fontWeight: ratio > 0.5 ? 800 : ratio > 0.2 ? 600 : 400,
                        opacity: 0.5 + ratio * 0.5,
                      }}
                      className={`
                        inline-block transition-all duration-500 cursor-default
                        hover:scale-125 hover:z-10 hover:drop-shadow-md
                        ${colorClass} ${rotation}
                        leading-tight font-sans tracking-tight
                      `}
                    >
                      {w.word}
                    </span>
                  );
                })
              )}

              {/* Overlay trang trí để tạo cảm giác chuyên nghiệp */}
              <div className="absolute inset-0 pointer-events-none border border-emerald-500/5 rounded-xl"></div>
            </div>
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
