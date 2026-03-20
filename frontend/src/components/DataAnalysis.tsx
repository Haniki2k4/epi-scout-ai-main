import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { TrendingUp, Download, FileText, BarChart3, Database, Sparkles, ShieldAlert, Send, CalendarClock, RadioTower, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NewsEvent } from "@/types";

type OverviewStats = {
  total_articles: number;
  total_cases: number;
  alert_count: number;
};

const DataAnalysis = () => {
  const [stats, setStats] = useState<OverviewStats>({
    total_articles: 0,
    total_cases: 0,
    alert_count: 0,
  });
  const [trends, setTrends] = useState<{ date: string; cases: number }[]>([]);
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [reportScope, setReportScope] = useState("weekly");
  const [reportAudience, setReportAudience] = useState("cdc");
  const [reportRegion, setReportRegion] = useState("all");
  const [reportTitle, setReportTitle] = useState("Báo cáo giám sát dịch bệnh tuần");

  // Seasonal flu data (monthly)
  const fluData = [
    { month: "T1", vietnam: 234, global: 45000 },
    { month: "T2", vietnam: 189, global: 38000 },
    { month: "T3", vietnam: 267, global: 52000 },
    { month: "T4", vietnam: 312, global: 61000 },
    { month: "T5", vietnam: 289, global: 55000 },
    { month: "T6", vietnam: 245, global: 48000 },
    { month: "T7", vietnam: 198, global: 39000 },
    { month: "T8", vietnam: 223, global: 43000 },
    { month: "T9", vietnam: 276, global: 54000 },
    { month: "T10", vietnam: 334, global: 68000 },
    { month: "T11", vietnam: 298, global: 59000 },
    { month: "T12", vietnam: 256, global: 51000 },
  ];

  // Comparison data
  const comparisonData = [
    { source: "Google Alerts", articles: 3420, relevant: 2145, accuracy: 62.7, speed: 15 },
    { source: "In-house Script", articles: 5678, relevant: 4892, accuracy: 86.2, speed: 8 },
  ];

  useEffect(() => {
    const fetchAnalysisData = async () => {
      try {
        const [statsRes, trendsRes, eventsRes] = await Promise.all([
          fetch("/api/stats/overview"),
          fetch("/api/stats/trends?days=7"),
          fetch("/api/events?limit=6"),
        ]);

        if (statsRes.ok) {
          setStats(await statsRes.json());
        }
        if (trendsRes.ok) {
          setTrends(await trendsRes.json());
        }
        if (eventsRes.ok) {
          setEvents(await eventsRes.json());
        }
      } catch (e) {
        console.error("Failed to fetch analysis data", e);
      }
    };

    fetchAnalysisData();
  }, []);

  const reportWindowLabel = useMemo(() => {
    if (reportScope === "daily") return "24 giờ gần nhất";
    if (reportScope === "monthly") return "30 ngày gần nhất";
    return "7 ngày gần nhất";
  }, [reportScope]);

  const topSignals = useMemo(() => {
    return events.slice(0, 3).map((event, index) => ({
      id: event.id,
      title: event.canonical_title,
      level: index === 0 ? "Ưu tiên cao" : index === 1 ? "Theo dõi sát" : "Theo dõi",
      sourceCount: event.source_count,
      articleCount: event.article_count,
      location: event.location || "Chưa rõ địa bàn",
    }));
  }, [events]);

  const reportSections = useMemo(() => {
    const peakTrend = trends.reduce<{ date: string; cases: number } | null>(
      (current, item) => {
        if (!current || item.cases > current.cases) {
          return item;
        }
        return current;
      },
      null
    );

    return [
      `Tổng hợp ${stats.total_articles} bài viết, ${stats.total_cases} ca ghi nhận và ${stats.alert_count} tín hiệu cảnh báo trong ${reportWindowLabel}.`,
      peakTrend
        ? `Ngày có tín hiệu mạnh nhất là ${peakTrend.date} với ${peakTrend.cases} ca được báo chí ghi nhận.`
        : "Chưa có dữ liệu xu hướng đủ mạnh để kết luận ngày đỉnh tín hiệu.",
      topSignals.length > 0
        ? `Sự kiện cần chú ý nhất: ${topSignals[0].title}, đã xuất hiện trên ${topSignals[0].sourceCount} nguồn khác nhau.`
        : "Chưa có sự kiện nổi bật được gom nhóm để đưa vào báo cáo.",
    ];
  }, [reportWindowLabel, stats, topSignals, trends]);

  const weeklyData = trends.map((t) => ({ name: t.date.split("-").slice(1).join("/"), cases: t.cases }));

  return (
    <div className="space-y-6">
      <Tabs defaultValue="flu" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="flu">Phân tích cúm mùa</TabsTrigger>
          <TabsTrigger value="comparison">So sánh công cụ</TabsTrigger>
          <TabsTrigger value="report">Báo cáo tự động</TabsTrigger>
        </TabsList>

        <TabsContent value="flu" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Xu hướng cúm mùa theo tháng</CardTitle>
              <CardDescription>So sánh dữ liệu Việt Nam và toàn cầu (52,000 bản ghi)</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={fluData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" />
                  <YAxis yAxisId="left" stroke="hsl(var(--chart-1))" />
                  <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--chart-2))" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                    }}
                  />
                  <Legend />
                  <Line
                    yAxisId="left"
                    type="monotone"
                    dataKey="vietnam"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={2}
                    name="Việt Nam"
                    dot={{ fill: "hsl(var(--chart-1))", r: 4 }}
                  />
                  <Line
                    yAxisId="right"
                    type="monotone"
                    dataKey="global"
                    stroke="hsl(var(--chart-2))"
                    strokeWidth={2}
                    name="Toàn cầu"
                    dot={{ fill: "hsl(var(--chart-2))", r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Nhận xét chính</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="mt-2 h-2 w-2 rounded-full bg-chart-1"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Đỉnh dịch:</strong> Ca bệnh tăng cao vào tháng 10-11, trùng với mùa lạnh ở Việt Nam.
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-2 h-2 w-2 rounded-full bg-chart-2"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Xu hướng toàn cầu:</strong> Phù hợp với mô hình Bắc bán cầu, đỉnh dịch vào mùa đông.
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="mt-2 h-2 w-2 rounded-full bg-chart-3"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Sự khác biệt:</strong> Việt Nam có biên độ dao động nhỏ hơn do khí hậu nhiệt đới.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Đề xuất giải pháp</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Chuẩn hóa báo cáo</p>
                  <p className="text-sm text-muted-foreground">
                    Thống nhất format dữ liệu theo chuẩn WHO ICD-10 để dễ so sánh quốc tế.
                  </p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Tích hợp DHIS2</p>
                  <p className="text-sm text-muted-foreground">
                    Sử dụng DHIS2 làm nền tảng tổng hợp dữ liệu từ nhiều nguồn.
                  </p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Mô hình dự báo</p>
                  <p className="text-sm text-muted-foreground">
                    Áp dụng ARIMA/SARIMA để dự báo xu hướng dịch theo mùa.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="comparison" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>So sánh hiệu suất công cụ tìm kiếm</CardTitle>
              <CardDescription>Google Alerts vs Scripts tự phát triển</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={comparisonData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="source" stroke="hsl(var(--muted-foreground))" />
                  <YAxis stroke="hsl(var(--muted-foreground))" />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)",
                    }}
                  />
                  <Legend />
                  <Bar dataKey="articles" fill="hsl(var(--chart-1))" name="Tổng bài viết" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="relevant" fill="hsl(var(--chart-2))" name="Bài viết liên quan" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            {comparisonData.map((tool, index) => (
              <Card key={index} className={index === 1 ? "border-l-4 border-l-accent" : ""}>
                <CardHeader>
                  <CardTitle>{tool.source}</CardTitle>
                  {index === 1 && <Badge className="w-fit bg-accent text-accent-foreground">Được đề xuất</Badge>}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Tổng bài viết</p>
                      <p className="text-2xl font-bold text-foreground">{tool.articles.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Liên quan</p>
                      <p className="text-2xl font-bold text-foreground">{tool.relevant.toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Độ chính xác</span>
                      <span className="font-medium text-foreground">{tool.accuracy}%</span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-secondary">
                      <div className="h-full bg-primary transition-all" style={{ width: `${tool.accuracy}%` }}></div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between rounded-lg bg-secondary p-3">
                    <span className="text-sm text-muted-foreground">Thời gian quét</span>
                    <span className="text-sm font-medium text-foreground">{tool.speed} phút</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-l-4 border-l-chart-2">
            <CardHeader>
              <CardTitle>Kết luận & Đề xuất</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="text-muted-foreground">
                <strong className="text-foreground">Scripts tự phát triển</strong> cho kết quả vượt trội với:
              </p>
              <ul className="ml-4 space-y-2">
                <li className="flex items-start gap-2">
                  <TrendingUp className="mt-0.5 h-4 w-4 text-accent" />
                  <span className="text-muted-foreground">
                    Độ chính xác cao hơn <strong className="text-foreground">37.5%</strong> (86.2% vs 62.7%)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <TrendingUp className="mt-0.5 h-4 w-4 text-accent" />
                  <span className="text-muted-foreground">
                    Thu thập nhiều hơn <strong className="text-foreground">66%</strong> bài viết (5,678 vs 3,420)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <TrendingUp className="mt-0.5 h-4 w-4 text-accent" />
                  <span className="text-muted-foreground">
                    Tốc độ nhanh hơn gần <strong className="text-foreground">2 lần</strong> (8 phút vs 15 phút)
                  </span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="report" className="space-y-6">
          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <Card className="border-l-4 border-l-primary">
              <CardHeader>
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <CardTitle>{reportTitle}</CardTitle>
                    <CardDescription>Biến phần mô tả tĩnh thành một bộ khung báo cáo có thể vận hành được</CardDescription>
                  </div>
                  <Badge className="bg-primary/10 text-primary hover:bg-primary/10">
                    <Sparkles className="mr-1 h-3.5 w-3.5" />
                    AI-assisted
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-5">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="report-title">Tên báo cáo</Label>
                    <Input
                      id="report-title"
                      value={reportTitle}
                      onChange={(e) => setReportTitle(e.target.value)}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Chu kỳ</Label>
                    <Select value={reportScope} onValueChange={setReportScope}>
                      <SelectTrigger>
                        <SelectValue placeholder="Chọn chu kỳ" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="daily">Hàng ngày</SelectItem>
                        <SelectItem value="weekly">Hàng tuần</SelectItem>
                        <SelectItem value="monthly">Hàng tháng</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Đối tượng nhận</Label>
                    <Select value={reportAudience} onValueChange={setReportAudience}>
                      <SelectTrigger>
                        <SelectValue placeholder="Chọn đối tượng nhận" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="cdc">CDC tỉnh/thành</SelectItem>
                        <SelectItem value="moh">Bộ Y tế</SelectItem>
                        <SelectItem value="hospital">Bệnh viện tuyến tỉnh</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Phạm vi</Label>
                    <Select value={reportRegion} onValueChange={setReportRegion}>
                      <SelectTrigger>
                        <SelectValue placeholder="Chọn phạm vi" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">Toàn quốc</SelectItem>
                        <SelectItem value="north">Miền Bắc</SelectItem>
                        <SelectItem value="central">Miền Trung</SelectItem>
                        <SelectItem value="south">Miền Nam</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-xl border bg-card p-4">
                    <Database className="mb-3 h-8 w-8 text-primary" />
                    <h4 className="font-medium text-foreground">Nguồn dữ liệu</h4>
                    <p className="mt-1 text-sm text-muted-foreground">Articles, Events, Trends, cảnh báo và whitelist nội bộ</p>
                  </div>
                  <div className="rounded-xl border bg-card p-4">
                    <BarChart3 className="mb-3 h-8 w-8 text-accent" />
                    <h4 className="font-medium text-foreground">Phân tích tự động</h4>
                    <p className="mt-1 text-sm text-muted-foreground">Tóm tắt tín hiệu nổi bật, số ca, event nổi trội và độ phủ nguồn</p>
                  </div>
                  <div className="rounded-xl border bg-card p-4">
                    <Send className="mb-3 h-8 w-8 text-chart-2" />
                    <h4 className="font-medium text-foreground">Đầu ra báo cáo</h4>
                    <p className="mt-1 text-sm text-muted-foreground">Preview trên UI, sẵn sàng làm bước tiếp theo là export PDF/email</p>
                  </div>
                </div>

                <div className="rounded-2xl bg-gradient-to-br from-sky-50 to-cyan-50 p-5 ring-1 ring-sky-100">
                  <div className="flex items-center gap-2 text-sm font-medium text-sky-800">
                    <CalendarClock className="h-4 w-4" />
                    Khung thời gian báo cáo: {reportWindowLabel}
                  </div>
                  <div className="mt-4 space-y-3">
                    {reportSections.map((section) => (
                      <div key={section} className="flex items-start gap-3 text-sm text-slate-700">
                        <div className="mt-1.5 h-2 w-2 rounded-full bg-sky-500"></div>
                        <span>{section}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="flex flex-wrap gap-3">
                  <Button size="lg">
                    <Download className="mr-2 h-4 w-4" />
                    Tải preview báo cáo
                  </Button>
                  <Button size="lg" variant="outline">
                    <Send className="mr-2 h-4 w-4" />
                    Mô phỏng gửi email
                  </Button>
                </div>
              </CardContent>
            </Card>

            <div className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Preview báo cáo tuần</CardTitle>
                  <CardDescription>Snapshot được tạo từ dữ liệu đang có trong hệ thống</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="rounded-xl border bg-secondary/40 p-4">
                    <div className="text-xs uppercase tracking-[0.2em] text-muted-foreground">Bản xem trước</div>
                    <div className="mt-2 text-lg font-semibold text-foreground">{reportTitle}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {reportAudience === "cdc" ? "CDC tỉnh/thành" : reportAudience === "moh" ? "Bộ Y tế" : "Bệnh viện tuyến tỉnh"}
                      {" • "}
                      {reportRegion === "all" ? "Toàn quốc" : reportRegion === "north" ? "Miền Bắc" : reportRegion === "central" ? "Miền Trung" : "Miền Nam"}
                    </div>
                  </div>
                  <div className="space-y-3">
                    <div className="rounded-lg border p-4">
                      <div className="text-sm font-medium text-foreground">Tóm tắt điều hành</div>
                      <p className="mt-2 text-sm text-muted-foreground">
                        Trong {reportWindowLabel}, hệ thống ghi nhận {stats.total_articles} bài viết, {stats.total_cases} ca và {stats.alert_count} tín hiệu cảnh báo.
                        Dữ liệu cho thấy cụm sự kiện nổi bật tập trung ở các chủ đề có độ phủ nguồn cao, phù hợp để đưa vào báo cáo nhanh.
                      </p>
                    </div>
                    <div className="rounded-lg border p-4">
                      <div className="text-sm font-medium text-foreground">Tín hiệu nổi bật cần chú ý</div>
                      <div className="mt-3 space-y-3">
                        {topSignals.length === 0 ? (
                          <div className="text-sm text-muted-foreground">Chưa có event nổi bật để hiển thị.</div>
                        ) : (
                          topSignals.map((signal) => (
                            <div key={signal.id} className="rounded-lg bg-secondary/60 p-3">
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <div className="font-medium text-foreground">{signal.title}</div>
                                  <div className="mt-1 text-sm text-muted-foreground">
                                    {signal.location} • {signal.articleCount} bài • {signal.sourceCount} nguồn
                                  </div>
                                </div>
                                <Badge variant={signal.level === "Ưu tiên cao" ? "default" : "secondary"}>{signal.level}</Badge>
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Tín hiệu rủi ro</CardTitle>
                  <CardDescription>Các khối cần xuất hiện trong báo cáo tự động</CardDescription>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="flex items-start gap-3 rounded-lg border p-3">
                    <ShieldAlert className="mt-0.5 h-5 w-5 text-destructive" />
                    <div>
                      <div className="font-medium text-foreground">Cảnh báo tăng đột biến</div>
                      <div className="text-sm text-muted-foreground">{stats.alert_count} tín hiệu cảnh báo đang tồn tại trong hệ thống.</div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 rounded-lg border p-3">
                    <RadioTower className="mt-0.5 h-5 w-5 text-primary" />
                    <div>
                      <div className="font-medium text-foreground">Độ phủ truyền thông</div>
                      <div className="text-sm text-muted-foreground">
                        {events[0] ? `${events[0].source_count} nguồn đang cùng đề cập event mạnh nhất.` : "Chưa đủ dữ liệu để đánh giá độ phủ nguồn."}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-start gap-3 rounded-lg border p-3">
                    <MapPin className="mt-0.5 h-5 w-5 text-chart-2" />
                    <div>
                      <div className="font-medium text-foreground">Điểm nóng địa bàn</div>
                      <div className="text-sm text-muted-foreground">
                        {events.find((event) => event.location)?.location || "Chưa rõ"} đang là địa bàn có tín hiệu xuất hiện sớm nhất trong nhóm event hiện tại.
                      </div>
                    </div>
                  </div>
                </CardContent>
              </Card>

              <Card className="border-l-4 border-l-primary">
                <CardHeader>
                  <CardTitle>Giải pháp DHIS2 Integration</CardTitle>
                  <CardDescription>Giữ phần hiện có, nhưng gắn chặt hơn với bài toán báo cáo thực tế</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <div>
                      <h4 className="mb-2 font-medium text-foreground">Ưu điểm</h4>
                      <ul className="space-y-2 text-sm text-muted-foreground">
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-accent"></div>
                          <span>Tích hợp nhiều nguồn dữ liệu vào cùng một pipeline báo cáo</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-accent"></div>
                          <span>Dễ nối báo cáo event-based thay vì chỉ đếm bài báo</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-accent"></div>
                          <span>Mở đường cho export, email schedule và dashboard theo tuyến</span>
                        </li>
                      </ul>
                    </div>
                    <div>
                      <h4 className="mb-2 font-medium text-foreground">Thách thức</h4>
                      <ul className="space-y-2 text-sm text-muted-foreground">
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-destructive"></div>
                          <span>Cần đồng bộ taxonomy bệnh và địa bàn giữa crawler với DHIS2</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-destructive"></div>
                          <span>Cần cơ chế duyệt trước khi gửi báo cáo chính thức</span>
                        </li>
                        <li className="flex items-start gap-2">
                          <div className="mt-1.5 h-1.5 w-1.5 rounded-full bg-destructive"></div>
                          <span>Cần mapping event sang chỉ số nghiệp vụ để không đếm trùng nguồn báo</span>
                        </li>
                      </ul>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Xu hướng 7 ngày gần nhất</CardTitle>
              <CardDescription>Dùng trực tiếp dữ liệu trend hiện có để làm nền cho báo cáo tự động</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={280}>
                <BarChart data={weeklyData.length > 0 ? weeklyData : [{ name: "Chưa có data", cases: 0 }]}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="name" stroke="hsl(var(--muted-foreground))" />
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
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DataAnalysis;
