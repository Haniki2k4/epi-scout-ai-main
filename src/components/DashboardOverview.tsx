import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, AlertCircle, Users, Globe, Activity } from "lucide-react";
import { BarChart, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell, Bar } from "recharts";

const DashboardOverview = () => {
  const [stats, setStats] = useState({
    total_articles: 0,
    total_cases: 0,
    alert_count: 0
  });

  const [trends, setTrends] = useState<{ date: string, cases: number }[]>([]);

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
        const res = await fetch("/api/stats/trends?days=7");
        if (res.ok) {
          const data = await res.json();
          setTrends(data);
        }
      } catch (e) {
        console.error("Failed trends", e);
      }
    }

    fetchStats();
    fetchTrends();
  }, []);

  // Use real trends for weekly chart if available, else empty
  const weeklyData = trends.map(t => ({ name: t.date.split('-').slice(1).join('/'), cases: t.cases }));

  const diseaseData = [
    { name: "Sốt xuất huyết", value: 35, color: "hsl(var(--chart-1))" },
    { name: "Cúm A", value: 28, color: "hsl(var(--chart-2))" },
    { name: "Tay chân miệng", value: 22, color: "hsl(var(--chart-3))" },
    { name: "Khác", value: 15, color: "hsl(var(--chart-4))" },
  ];

  return (
    <div className="space-y-6">
      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
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

        <Card className="border-l-4 border-l-destructive">
          <CardHeader className="pb-3">
            <CardDescription>Cảnh báo dịch</CardDescription>
            <CardTitle className="text-3xl">{stats.alert_count}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <AlertCircle className="h-4 w-4 text-destructive" />
              <span className="text-destructive font-medium">Mức độ cảnh báo</span>
            </div>
          </CardContent>
        </Card>

        <Card className="border-l-4 border-l-chart-2">
          <CardHeader className="pb-3">
            <CardDescription>Tỉnh/thành có ca</CardDescription>
            <CardTitle className="text-3xl">--</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2 text-sm">
              <Users className="h-4 w-4 text-muted-foreground" />
              <span className="text-muted-foreground">Đang cập nhật...</span>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Charts Row */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Xu hướng ca bệnh (7 ngày qua)</CardTitle>
            <CardDescription>Số lượng ca ghi nhận từ tin tức</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <BarChart data={weeklyData.length > 0 ? weeklyData : [{ name: 'Chưa có data', cases: 0 }]}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
                <YAxis stroke="hsl(var(--muted-foreground))" />
                <Tooltip
                  contentStyle={{
                    backgroundColor: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "var(--radius)"
                  }}
                />
                <Bar dataKey="cases" fill="hsl(var(--primary))" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Phân bố dịch bệnh (Mẫu)</CardTitle>
            <CardDescription>Tỷ lệ theo loại bệnh</CardDescription>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <PieChart>
                <Pie
                  data={diseaseData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {diseaseData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default DashboardOverview;
