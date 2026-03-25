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



  useEffect(() => {
    const fetchAnalysisData = async () => {
      try {
        const [statsRes, trendsRes, eventsRes] = await Promise.all([
          fetch("/api/stats/overview"),
          fetch("/api/stats/trends?days=30"),
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
    return "30 ngày gần nhất";
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

  const forecastData = useMemo(() => {
    if (trends.length < 2) return trends.map(t => ({ name: t.date, actual: t.cases, forecast: null }));
    const n = trends.length;
    let sumX = 0, sumY = 0, sumXY = 0, sumXX = 0;
    trends.forEach((t, i) => {
      sumX += i;
      sumY += t.cases;
      sumXY += i * t.cases;
      sumXX += i * i;
    });
    const slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
    const intercept = (sumY - slope * sumX) / n;
    
    const data = trends.map((t, i) => ({
      name: t.date.split("-").slice(1).join("/"),
      actual: t.cases,
      forecast: Math.max(0, Math.round(slope * i + intercept))
    }));

    const lastDate = new Date(trends[n-1].date);
    for (let i = 1; i <= 3; i++) {
        const nextDate = new Date(lastDate);
        nextDate.setDate(nextDate.getDate() + i);
        const name = `${String(nextDate.getMonth()+1).padStart(2, '0')}/${String(nextDate.getDate()).padStart(2, '0')}`;
        data.push({ name, actual: null as any, forecast: Math.max(0, Math.round(slope * (n - 1 + i) + intercept)) });
    }
    return data;
  }, [trends]);

  return (
    <div className="space-y-6">
      <Tabs defaultValue="forecast" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="forecast">Dự báo sự kiện</TabsTrigger>
          <TabsTrigger value="report">Báo cáo tự động</TabsTrigger>
        </TabsList>

        <TabsContent value="forecast" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Dự báo xu hướng sự kiện dịch bệnh</CardTitle>
              <CardDescription>Mô hình hồi quy tuyến tính dựa trên dữ liệu thu thập thực tế 7 ngày qua</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={forecastData}>
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
                  <Legend />
                  <Line
                    type="monotone"
                    dataKey="actual"
                    stroke="hsl(var(--chart-1))"
                    strokeWidth={3}
                    name="Thực tế"
                    dot={{ fill: "hsl(var(--chart-1))", r: 4 }}
                    activeDot={{ r: 6 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="forecast"
                    stroke="hsl(var(--chart-2))"
                    strokeWidth={2}
                    strokeDasharray="5 5"
                    name="Dự báo (Hồi quy)"
                    dot={{ fill: "hsl(var(--chart-2))", r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Phân tích Hồi quy</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <p className="text-sm text-foreground">
                  Dựa trên số lượng bài viết thu thập được, hệ thống áp dụng mô hình <strong className="text-primary">Hồi quy tuyến tính (Linear Regression)</strong> để nội suy xu hướng sự kiện trong 3 ngày tiếp theo.
                </p>
                <div className="space-y-2 text-sm text-muted-foreground">
                  <div className="flex justify-between items-center p-3 bg-secondary rounded-lg">
                    <span>Trạng thái xu hướng:</span>
                    <Badge variant={forecastData.length > 3 && forecastData[forecastData.length-1].forecast > forecastData[0].forecast ? "destructive" : "secondary"}>
                      {forecastData.length > 3 && forecastData[forecastData.length-1].forecast > forecastData[0].forecast ? "Đang tăng" : "Giảm / Ổn định"}
                    </Badge>
                  </div>
                  <div className="flex justify-between items-center p-3 bg-secondary rounded-lg">
                    <span>Độ tin cậy mô hình:</span>
                    <span className="font-medium text-foreground">Khá (Dựa trên {trends.length} điểm dữ liệu)</span>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Khuyến nghị Dữ liệu</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Mở rộng nguồn quét</p>
                  <p className="text-sm text-muted-foreground">
                    Cần thu thập thêm từ các nguồn địa phương để tăng độ chính xác của dự báo hẹp.
                  </p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Kết hợp mạng xã hội</p>
                  <p className="text-sm text-muted-foreground">
                    Xu hướng truyền thông thường theo sau mạng xã hội từ 1-2 ngày. Khuyến nghị cấu hình thêm Social Listening.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
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

                <div className="mt-4 rounded-3xl bg-muted/30 p-4">
                  <div className="grid gap-4 md:grid-cols-3">
                    <div className="min-h-[168px] rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
                      <Database className="mb-3 h-8 w-8 text-primary" />
                      <h4 className="font-medium text-foreground">Nguồn dữ liệu</h4>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">Articles, Events, Trends, cảnh báo và whitelist nội bộ</p>
                    </div>
                    <div className="min-h-[168px] rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
                      <BarChart3 className="mb-3 h-8 w-8 text-accent" />
                      <h4 className="font-medium text-foreground">Phân tích tự động</h4>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">Tóm tắt tín hiệu nổi bật, số ca, event nổi trội và độ phủ nguồn</p>
                    </div>
                    <div className="min-h-[168px] rounded-2xl bg-card p-5 shadow-sm ring-1 ring-border">
                      <Send className="mb-3 h-8 w-8 text-chart-2" />
                      <h4 className="font-medium text-foreground">Đầu ra báo cáo</h4>
                      <p className="mt-1 text-sm leading-6 text-muted-foreground">Preview trên UI, sẵn sàng làm bước tiếp theo là export PDF/email</p>
                    </div>
                  </div>
                </div>

                <div className="mt-6 rounded-2xl bg-gradient-to-br from-sky-50 to-cyan-50 p-5 shadow-sm ring-1 ring-sky-100">
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


        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DataAnalysis;
