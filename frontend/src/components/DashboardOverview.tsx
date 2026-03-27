import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, Globe, Activity, Info } from "lucide-react";
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
} from "recharts";

interface TopDisease {
  disease_name: string;
  article_count: number;
}

const MONTH_OPTIONS = [1, 2, 3, 6, 12];

const DashboardOverview = () => {
  const [stats, setStats] = useState({
    total_articles: 0,
    total_cases: 0,
    alert_count: 0,
    top_disease: null as string | null,
    top_disease_mentions: 0,
  });

  const [trends, setTrends] = useState<{ date: string; cases: number }[]>([]);
  const [topDiseases, setTopDiseases] = useState<TopDisease[]>([]);
  const [selectedMonths, setSelectedMonths] = useState(1);
  const [loadingTopDiseases, setLoadingTopDiseases] = useState(false);

  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch("/api/stats/overview");
        if (res.ok) {
          const data = await res.json();
          setStats(data);
        }
      } catch (e) {
        console.error("Failed to fetch stats", e);
      }
    };

    const fetchTrends = async () => {
      try {
        const res = await fetch("/api/stats/trends?days=30");
        if (res.ok) {
          const data = await res.json();
          setTrends(data);
        }
      } catch (e) {
        console.error("Failed trends", e);
      }
    };

    fetchStats();
    fetchTrends();
  }, []);

  useEffect(() => {
    const fetchTopDiseases = async () => {
      setLoadingTopDiseases(true);
      try {
        const res = await fetch(`/api/stats/top-diseases?months=${selectedMonths}`);
        if (res.ok) {
          const data = await res.json();
          setTopDiseases(data);
        }
      } catch (e) {
        console.error("Failed top diseases", e);
      } finally {
        setLoadingTopDiseases(false);
      }
    };

    fetchTopDiseases();
  }, [selectedMonths]);

  // Biểu đồ xu hướng 30 ngày
  const weeklyData = trends.map((t) => ({
    name: t.date.split("-").slice(1).join("/"),
    cases: t.cases,
  }));

  // Dữ liệu cho biểu đồ ngang top 10 - giảm dần (recharts layout=vertical: phần tử đầu ở trên cùng)
  const horizontalData = topDiseases;

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

        {/* Card bệnh được nhắc đến nhiều nhất */}
        <Card className="border-l-4 border-l-destructive">
          <CardHeader className="pb-3">
            <CardDescription>Bệnh được nhắc nhiều nhất (trong 30 ngày)</CardDescription>
            <CardTitle className="text-xl leading-tight truncate" title={stats.top_disease ?? "—"}>
              {stats.top_disease ?? "—"}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-muted-foreground">
                {stats.top_disease_mentions > 0
                  ? `${stats.top_disease_mentions} bài viết nhắc đến`
                  : "Chưa có dữ liệu"}
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

      {/* Charts Row */}
      <div className="grid gap-6 md:grid-cols-2">
        {/* Xu hướng 30 ngày */}
        <Card>
          <CardHeader>
            <CardTitle>Xu hướng ca bệnh (30 ngày qua)</CardTitle>
            <CardDescription>Số lượng ca ghi nhận từ tin tức</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart
                data={
                  weeklyData.length > 0 ? weeklyData : [{ name: "Chưa có data", cases: 0 }]
                }
              >
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 11 }} />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)",
                  }}
                />
                <Bar dataKey="cases" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Top 10 bệnh dịch - biểu đồ cột ngang */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between flex-wrap gap-2">
              <div>
                <CardTitle>Top 10 bệnh dịch được nhắc đến nhiều nhất</CardTitle>
                <CardDescription>
                  Đếm số bài viết nhắc đến từng bệnh
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <label htmlFor="month-select" className="text-sm text-muted-foreground whitespace-nowrap">
                  Trong:
                </label>
                <select
                  id="month-select"
                  value={selectedMonths}
                  onChange={(e) => setSelectedMonths(Number(e.target.value))}
                  className="text-sm border border-border rounded px-2 py-1 bg-background text-foreground cursor-pointer"
                >
                  {MONTH_OPTIONS.map((m) => (
                    <option key={m} value={m}>
                      {m} tháng
                    </option>
                  ))}
                </select>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {loadingTopDiseases ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
                Đang tải...
              </div>
            ) : horizontalData.length === 0 ? (
              <div className="flex items-center justify-center h-[300px] text-muted-foreground text-sm">
                Chưa có dữ liệu trong khoảng thời gian này
              </div>
            ) : (
              <ResponsiveContainer width="100%" height={300}>
                <BarChart
                  layout="vertical"
                  data={horizontalData}
                  margin={{ top: 0, right: 20, left: 0, bottom: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" horizontal={false} />
                  <XAxis
                    type="number"
                    stroke="hsl(var(--muted-foreground))"
                    allowDecimals={false}
                  />
                  <YAxis
                    type="category"
                    dataKey="disease_name"
                    stroke="hsl(var(--muted-foreground))"
                    tick={{ fontSize: 12 }}
                    width={130}
                  />
                  <Tooltip
                    formatter={(value: number) => [`${value} bài viết`, "Số lần nhắc đến"]}
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                    }}
                  />
                  <Bar
                    dataKey="article_count"
                    fill="hsl(var(--chart-2))"
                    radius={[0, 6, 6, 0]}
                    label={{ position: "right", fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                  />
                </BarChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Banner đề xuất tìm kiếm quốc tế */}
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
