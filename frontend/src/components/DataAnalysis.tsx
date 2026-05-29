import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend, Scatter, ReferenceLine } from "recharts";
import { TrendingUp, Download, FileText, BarChart3, Database, Sparkles, ShieldAlert, Send, CalendarClock, RadioTower, MapPin, AlertTriangle, Table2, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NewsEvent, ZScoreSpike, ProphetForecast } from "@/types";
import { ComposedChart, Area } from "recharts";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { DiseaseSelectorModal } from "@/components/DiseaseSelectorModal";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/contexts/AuthContext";


type OverviewStats = {
  total_articles: number;
  total_cases: number;
  alert_count: number;
};

interface DataAnalysisProps {
  showOnlyReport?: boolean;
}

const STORAGE_KEY = "epi-scout-forecast-disease";
const CACHE_KEY_PREFIX = "epi-scout-stats-cache-";
const CACHE_TTL_MS = 5 * 60 * 1000;

interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

function getFromCache<T>(key: string): T | null {
  try {
    const stored = localStorage.getItem(key);
    if (!stored) return null;
    const entry: CacheEntry<T> = JSON.parse(stored);
    if (Date.now() - entry.timestamp > CACHE_TTL_MS) {
      localStorage.removeItem(key);
      return null;
    }
    return entry.data;
  } catch {
    return null;
  }
}

function setToCache<T>(key: string, data: T): void {
  try {
    const entry: CacheEntry<T> = { data, timestamp: Date.now() };
    localStorage.setItem(key, JSON.stringify(entry));
  } catch (e) {
    console.warn("Cache write failed", e);
  }
}

const DataAnalysis = ({ showOnlyReport = false }: DataAnalysisProps) => {
  const { toast } = useToast();
  const { isGuest } = useAuth();
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
  const [zscoreSpikes, setZscoreSpikes] = useState<ZScoreSpike[]>([]);
  const [prophetForecast, setProphetForecast] = useState<ProphetForecast[]>([]);
  const [prophetMetrics, setProphetMetrics] = useState<{ mae: number | null, rmse: number | null, eval_method: string } | null>(null);
  const [forecastDisease, setForecastDisease] = useState<string | null>(() => {
    return localStorage.getItem(STORAGE_KEY);
  });
  const [isLoadingInitialDisease, setIsLoadingInitialDisease] = useState(false);
  const [loadingZscore, setLoadingZscore] = useState(false);
  const [loadingForecast, setLoadingForecast] = useState(false);

  // State báo cáo
  const [exportingWord, setExportingWord] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailAttachWord, setEmailAttachWord] = useState(true);
  const [emailAttachExcel, setEmailAttachExcel] = useState(true);



  useEffect(() => {
    const initializeDisease = async () => {
      const storedDisease = localStorage.getItem(STORAGE_KEY);
      if (storedDisease) {
        setForecastDisease(storedDisease);
        return;
      }
      setIsLoadingInitialDisease(true);
      try {
        const topRes = await fetch("/api/stats/top-diseases?months=12");
        if (topRes.ok) {
          const topData = await topRes.json();
          if (topData.length > 0 && topData[0].disease_name) {
            const topDisease = topData[0].disease_name;
            setForecastDisease(topDisease);
            localStorage.setItem(STORAGE_KEY, topDisease);
          } else {
            setForecastDisease("Sởi");
            localStorage.setItem(STORAGE_KEY, "Sởi");
          }
        } else {
          setForecastDisease("Sởi");
          localStorage.setItem(STORAGE_KEY, "Sởi");
        }
      } catch (e) {
        console.error("Failed to fetch top disease", e);
        setForecastDisease("Sởi");
        localStorage.setItem(STORAGE_KEY, "Sởi");
      } finally {
        setIsLoadingInitialDisease(false);
      }
    };
    initializeDisease();
  }, []);

  const handleDiseaseChange = (disease: string) => {
    setForecastDisease(disease);
    localStorage.setItem(STORAGE_KEY, disease);
  };

  useEffect(() => {
    const fetchForecastData = async () => {
      if (!forecastDisease) return;

      const zscoreCacheKey = `${CACHE_KEY_PREFIX}zscore-${forecastDisease}`;
      const forecastCacheKey = `${CACHE_KEY_PREFIX}forecast-${forecastDisease}`;

      const cachedZscore = getFromCache<ZScoreSpike[]>(zscoreCacheKey);
      const cachedForecast = getFromCache<ProphetForecast[]>(forecastCacheKey);

      if (!cachedZscore) {
        setZscoreSpikes([]);
        setLoadingZscore(true);
      } else {
        setZscoreSpikes(cachedZscore);
      }
      if (!cachedForecast) {
        setProphetForecast([]);
        setProphetMetrics(null);
        setLoadingForecast(true);
      } else {
        setProphetForecast(cachedForecast);
      }

      try {
        const [zscoreRes, prophetRes] = await Promise.all([
          cachedZscore ? Promise.resolve(new Response(JSON.stringify(cachedZscore))) : fetch(`/api/stats/zscore?disease=${encodeURIComponent(forecastDisease)}`),
          cachedForecast ? Promise.resolve(new Response(JSON.stringify(cachedForecast))) : fetch(`/api/stats/forecast?disease=${encodeURIComponent(forecastDisease)}`),
        ]);

        if (zscoreRes.ok && !cachedZscore) {
          const zData = await zscoreRes.json();
          const mappedZscore = zData.map((d: any) => ({
            date: d.date,
            cases: d.count,
            rolling_mean: d.ma,
            rolling_std: d.std ?? 0,
            z_score: d.zscore,
            is_spike: d.spike_level === 'danger' || d.spike_level === 'alert',
            threshold: d.std > 0 ? d.ma + 2 * d.std : d.count,
          }));
          setZscoreSpikes(mappedZscore);
          setToCache(zscoreCacheKey, mappedZscore);
        }
        setLoadingZscore(false);
        if (prophetRes.ok && !cachedForecast) {
          const pData = await prophetRes.json();
          const mappedForecast: ProphetForecast[] = [];

          if (pData.historical) {
            pData.historical.forEach((h: any) => {
              mappedForecast.push({
                date: h.ds,
                actual: h.y,
                forecast: h.y,
                forecast_lower: h.y,
                forecast_upper: h.y,
                is_future: false
              });
            });
          }
          if (pData.forecast) {
            pData.forecast.forEach((f: any) => {
              mappedForecast.push({
                date: f.ds,
                actual: null,
                forecast: f.yhat,
                forecast_lower: f.yhat_lower,
                forecast_upper: f.yhat_upper,
                is_future: true
              });
            });
          }
          setProphetForecast(mappedForecast);
          setToCache(forecastCacheKey, mappedForecast);

          if (pData.metrics) {
            setProphetMetrics(pData.metrics);
          } else {
            setProphetMetrics(null);
          }
        }
        setLoadingForecast(false);
      } catch (e) {
        console.error("Failed to fetch forecast data", e);
        setLoadingZscore(false);
        setLoadingForecast(false);
      }
    };
    fetchForecastData();
  }, [forecastDisease]);

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

  // --- Report scope to hours mapping ---
  const scopeHours = useMemo(() => {
    if (reportScope === "daily") return 24;
    if (reportScope === "weekly") return 72;
    return 720; // monthly ~30 days
  }, [reportScope]);

  const reportWindowLabel = useMemo(() => {
    if (reportScope === "daily") return "24 giờ gần nhất";
    if (reportScope === "weekly") return "72 giờ (3 ngày) gần nhất";
    return "30 ngày gần nhất";
  }, [reportScope]);

  // --- Hàm xuất báo cáo Word ---
  const handleExportWord = async () => {
    setExportingWord(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/report/generate", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ scope_hours: scopeHours }),
      });
      if (!res.ok) throw new Error("Tạo báo cáo thất bại");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `BaoCao_DichBenh_${new Date().toISOString().slice(0, 10)}.docx`;
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "Xuất thành công", description: "File Word đã được tải về" });
    } catch (e: unknown) {
      toast({
        title: "Lỗi",
        description: e instanceof Error ? e.message : "Xuất Word thất bại",
        variant: "destructive",
      });
    } finally {
      setExportingWord(false);
    }
  };

  // --- Hàm xuất Excel (Mẫu QĐ 2018) ---
  const handleExportExcel = async () => {
    setExportingExcel(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/report/export-excel", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ scope_hours: scopeHours }),
      });
      if (!res.ok) throw new Error("Xuất Excel thất bại");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `BieuMau_EBS_QD2018_${new Date().toISOString().slice(0, 10)}.xlsx`;
      a.click();
      URL.revokeObjectURL(url);
      toast({ title: "Xuất thành công", description: "File Excel (Mẫu QĐ 2018) đã được tải về" });
    } catch (e: unknown) {
      toast({
        title: "Lỗi",
        description: e instanceof Error ? e.message : "Xuất Excel thất bại",
        variant: "destructive",
      });
    } finally {
      setExportingExcel(false);
    }
  };

  // --- Hàm gửi email ---
  const handleSendEmail = async () => {
    setSendingEmail(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/report/send-email", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          scope_hours: scopeHours,
          attach_docx: emailAttachWord,
          attach_excel: emailAttachExcel,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Gửi email thất bại");
      toast({ title: "Gửi email thành công", description: data.message });
      setEmailDialogOpen(false);
    } catch (e: unknown) {
      toast({
        title: "Lỗi",
        description: e instanceof Error ? e.message : "Gửi email thất bại",
        variant: "destructive",
      });
    } finally {
      setSendingEmail(false);
    }
  };



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

  const reportTabContent = (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Cấu hình tham số</h3>
          <p className="text-sm text-muted-foreground">Chọn đối tượng và khung thời gian cho báo cáo tự động.</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" className="gap-2" onClick={handleExportExcel} disabled={exportingExcel || isGuest} title={isGuest ? "Dang nhap de xuat bao cao" : undefined}>
            {isGuest ? <Lock className="h-4 w-4" /> : <Table2 className="h-4 w-4 text-chart-2" />}
            {exportingExcel ? "Đang xuất báo cáo..." : "Biểu mẫu QĐ 2018"}
          </Button>
          <Button variant="outline" className="gap-2" onClick={handleExportWord} disabled={exportingWord || isGuest} title={isGuest ? "Dang nhap de xuat bao cao" : undefined}>
            {isGuest ? <Lock className="h-4 w-4" /> : <FileText className="h-4 w-4 text-primary" />}
            {exportingWord ? "Đang xuất báo cáo..." : "Báo cáo Word"}
          </Button>
          <Button className="gap-2" onClick={() => setEmailDialogOpen(true)} disabled={isGuest} title={isGuest ? "Dang nhap de gui email" : undefined}>
            {isGuest ? <Lock className="h-4 w-4" /> : <Send className="h-4 w-4" />}
            Gửi Email List
          </Button>
        </div>
      </div>

      <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
        <div className="space-y-2">
          <Label>Khung thời gian</Label>
          <Select value={reportScope} onValueChange={setReportScope}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="daily">24h qua (Báo cáo ngày)</SelectItem>
              <SelectItem value="weekly">72h qua (Báo cáo tuần/cuối tuần)</SelectItem>
              <SelectItem value="monthly">30 ngày qua (Báo cáo tháng)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Đối tượng nhận báo cáo</Label>
          <Select value={reportAudience} onValueChange={setReportAudience}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="cdc">CDC / Trung tâm y tế dự phòng</SelectItem>
              <SelectItem value="moh">Bộ Y tế (Cục Y tế dự phòng)</SelectItem>
              <SelectItem value="hospital">Bệnh viện (Khoa truyền nhiễm)</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-2">
          <Label>Phạm vi địa lý (Mô phỏng)</Label>
          <Select value={reportRegion} onValueChange={setReportRegion}>
            <SelectTrigger>
              <SelectValue />
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

      <Card>
        <CardContent className="pt-6">
          <div className="space-y-2">
            <Label>Tiêu đề báo cáo</Label>
            <Input
              value={reportTitle}
              onChange={e => setReportTitle(e.target.value)}
              className="text-lg font-medium"
            />
            <p className="text-xs text-muted-foreground">Tiêu đề này sẽ được in trong file Word xuất ra.</p>
          </div>
        </CardContent>
      </Card>

      <div className="space-y-6">
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Preview bảng báo cáo</CardTitle>
            <CardDescription>Bản xem trước dữ liệu sẽ được xuất ra trong Phụ lục I</CardDescription>
          </CardHeader>
          <CardContent className="p-0">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-secondary/50">
                    <TableHead className="w-[50px] font-bold">STT</TableHead>
                    <TableHead className="min-w-[120px] font-bold">Ngày ghi nhận</TableHead>
                    <TableHead className="min-w-[150px] font-bold">Địa điểm</TableHead>
                    <TableHead className="min-w-[250px] font-bold">Mô tả dấu hiệu cảnh báo</TableHead>
                    <TableHead className="min-w-[150px] font-bold">Nguồn tin</TableHead>
                    <TableHead className="min-w-[100px] font-bold">Số ca</TableHead>
                    <TableHead className="min-w-[120px] font-bold">Đánh giá</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {events.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-6 text-muted-foreground">
                        Không có dữ liệu sự kiện để hiển thị.
                      </TableCell>
                    </TableRow>
                  ) : (
                    events.slice(0, 5).map((event, idx) => (
                      <TableRow key={event.id}>
                        <TableCell className="font-medium">{idx + 1}</TableCell>
                        <TableCell>{new Date(event.event_date).toLocaleDateString("vi-VN")}</TableCell>
                        <TableCell>{event.location || "Chưa rõ"}</TableCell>
                        <TableCell>
                          <div className="font-medium line-clamp-2" title={event.canonical_title}>
                            {event.canonical_title}
                          </div>
                        </TableCell>
                        <TableCell>
                          <div className="flex flex-wrap gap-1">
                            {event.sources_preview.slice(0, 2).map((s, i) => (
                              <Badge key={i} variant="outline" className="text-[10px] whitespace-nowrap">
                                {s}
                              </Badge>
                            ))}
                            {event.sources_preview.length > 2 && (
                              <Badge variant="outline" className="text-[10px] whitespace-nowrap">+{event.sources_preview.length - 2}</Badge>
                            )}
                          </div>
                        </TableCell>
                        <TableCell>
                          {event.case_count > 0 ? (
                            <Badge variant="destructive">{event.case_count} ca</Badge>
                          ) : "Chưa rõ"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={idx === 0 ? "default" : "secondary"}>
                            {idx === 0 ? "Cảnh báo" : "Theo dõi"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
            <div className="p-4 border-t text-sm text-muted-foreground text-center bg-secondary/20">
              Chỉ hiển thị tối đa 5 sự kiện nổi bật nhất. Hãy xuất file Excel hoặc Word để xem toàn bộ danh sách.
            </div>
          </CardContent>
        </Card>
      </div>

      <Dialog open={emailDialogOpen} onOpenChange={setEmailDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Send className="h-5 w-5 text-primary" />
              Gửi báo cáo qua Email
            </DialogTitle>
            <DialogDescription>
              Hệ thống sẽ tạo báo cáo và gửi đến danh sách email đã cấu hình bởi Admin.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="rounded-lg border p-3 text-sm space-y-2">
              <p className="font-medium text-foreground">Thông tin báo cáo</p>
              <p className="text-muted-foreground">
                Khoảng thời gian: <strong>{scopeHours} giờ gần nhất</strong>
              </p>
            </div>

            <div className="space-y-3">
              <Label className="text-sm font-medium">File đính kèm</Label>
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="attach-word-3"
                    checked={emailAttachWord}
                    onChange={e => setEmailAttachWord(e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="attach-word-3" className="text-sm cursor-pointer">
                    Báo cáo Word (.docx) — Tóm tắt dịch bệnh
                  </Label>
                </div>
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="attach-excel-3"
                    checked={emailAttachExcel}
                    onChange={e => setEmailAttachExcel(e.target.checked)}
                    className="rounded"
                  />
                  <Label htmlFor="attach-excel-3" className="text-sm cursor-pointer">
                    Biểu mẫu Excel (.xlsx) — Phụ lục I QĐ 2018/QĐ-BYT
                  </Label>
                </div>
              </div>
            </div>
          </div>

          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setEmailDialogOpen(false)}>Hủy</Button>
            <Button
              onClick={handleSendEmail}
              disabled={sendingEmail || (!emailAttachWord && !emailAttachExcel)}
              className="gap-2"
            >
              <Send className="h-4 w-4" />
              {sendingEmail ? "Đang gửi..." : "Gửi ngay"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );

  if (showOnlyReport) {
    return reportTabContent;
  }

  return (
    <div className="space-y-6">
      <Tabs defaultValue="forecast" className="space-y-6">
        <TabsList className="grid w-full grid-cols-2">
          <TabsTrigger value="zscore">Phát hiện Đột biến</TabsTrigger>
          <TabsTrigger value="forecast">Dự báo sự kiện</TabsTrigger>
        </TabsList>

        <TabsContent value="zscore" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="space-y-1">
                <CardTitle>Mô hình cảnh báo đột biến</CardTitle>
                <CardDescription>Phát hiện bất thường dựa trên độ lệch chuẩn của <strong>số lượng bài báo</strong> nhắc đến bệnh theo ngày</CardDescription>
              </div>
              <DiseaseSelectorModal
                selectedDiseases={[forecastDisease || ""]}
                onChange={(vals) => { if (vals.length > 0) handleDiseaseChange(vals[0]) }}
                maxSelect={1}
                triggerButtonText={isLoadingInitialDisease ? "Đang tải..." : (forecastDisease || "Chọn bệnh")}
                disabled={isLoadingInitialDisease}
              />
            </CardHeader>
            <CardContent>
              <div className="h-[400px] mt-4 relative">
                {loadingZscore && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/60 backdrop-blur-sm rounded-lg">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                      <span className="text-sm text-muted-foreground">Đang tính toán...</span>
                    </div>
                  </div>
                )}
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart data={zscoreSpikes.map(s => ({ ...s, spike_value: s.is_spike ? s.cases : null }))} margin={{ top: 20, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                    <XAxis dataKey="date" stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 12 }} minTickGap={30} />
                    <YAxis stroke="hsl(var(--muted-foreground))" tick={{ fontSize: 12 }} />
                    <Tooltip
                      contentStyle={{ backgroundColor: "hsl(var(--card))", border: "1px solid hsl(var(--border))", borderRadius: "8px" }}
                      itemStyle={{ color: "hsl(var(--foreground))" }}
                    />
                    <Legend />
                    <Bar dataKey="cases" name="Số bài báo nhắc đến" fill="hsl(var(--chart-1))" radius={[4, 4, 0, 0]} maxBarSize={40} />
                    <Line type="monotone" dataKey="rolling_mean" name="Trung bình trượt (14 ngày)" stroke="hsl(var(--chart-2))" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="spike_value" name="Cảnh báo đột biến" stroke="transparent" connectNulls={false}
                      dot={{ r: 6, fill: "hsl(var(--destructive))", strokeWidth: 2, stroke: "hsl(var(--background))" }}
                      activeDot={false} legendType="circle" />
                    <Line type="monotone" dataKey="threshold" name="Ngưỡng bất thường (MA+2σ)" stroke="hsl(var(--destructive))" strokeWidth={1.5} strokeDasharray="6 3" dot={false} />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle className="text-destructive flex items-center gap-2">
                  <AlertTriangle className="h-5 w-5" />
                  Điểm Nóng Bất Thường
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {zscoreSpikes.filter(s => s.is_spike).reverse().map((spike, i) => (
                    <div key={i} className="flex justify-between items-center p-3 rounded-lg bg-destructive/10 border border-destructive/20">
                      <div>
                        <div className="font-medium text-destructive">{spike.date}</div>
                        <div className="text-sm text-muted-foreground">Z-Score: <span className="font-semibold">{spike.z_score.toFixed(2)}</span></div>
                      </div>
                      <div className="text-right">
                        <div className="font-bold text-foreground">{spike.cases} bài báo</div>
                        <div className="text-xs text-muted-foreground">+{(spike.cases - spike.rolling_mean).toFixed(1)} so với TB</div>
                      </div>
                    </div>
                  ))}
                  {zscoreSpikes.filter(s => s.is_spike).length === 0 && (
                    <div className="p-4 text-center text-sm text-muted-foreground bg-muted/50 rounded-lg">
                      Không phát hiện điểm bất thường nào trong chu kỳ quan trắc hiện tại.
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Khuyến nghị Giám sát</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Kích hoạt đáp ứng nhanh</p>
                  <p className="text-sm text-muted-foreground">
                    Các điểm cảnh báo đỏ cho thấy số ca mắc vượt quá 2 độ lệch chuẩn so với chu kỳ 14 ngày. Cần xem xét điều tra dịch tễ học lập tức.
                  </p>
                </div>
                <div className="rounded-lg bg-secondary p-3">
                  <p className="mb-1 text-sm font-medium text-foreground">Xác minh nguồn tin</p>
                  <p className="text-sm text-muted-foreground">
                    Đẩy mạnh rà soát các nguồn báo chí địa phương xung quanh ngày có cảnh báo để đối chiếu ổ dịch.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        <TabsContent value="forecast" className="space-y-6">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <div className="space-y-1">
                <CardTitle>Xu hướng Sự quan tâm</CardTitle>
                <CardDescription>Mô hình dự báo số lượng bài báo được viết về bệnh trong tương lai (Prophet AI - khoảng tin cậy 80%)</CardDescription>
              </div>
              <DiseaseSelectorModal
                selectedDiseases={[forecastDisease || ""]}
                onChange={(vals) => { if (vals.length > 0) handleDiseaseChange(vals[0]) }}
                maxSelect={1}
                triggerButtonText={isLoadingInitialDisease ? "Đang tải..." : (forecastDisease || "Chọn bệnh")}
                disabled={isLoadingInitialDisease}
              />
            </CardHeader>
            <CardContent>
              <div className="h-[460px] mt-4 relative">
                {loadingForecast && (
                  <div className="absolute inset-0 z-10 flex items-center justify-center bg-card/60 backdrop-blur-sm rounded-lg">
                    <div className="flex flex-col items-center gap-2">
                      <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
                      <span className="text-sm text-muted-foreground">Đang tính toán...</span>
                    </div>
                  </div>
                )}
                <ResponsiveContainer width="100%" height="100%">
                  <ComposedChart
                    data={prophetForecast}
                    margin={{ top: 20, right: 30, left: 0, bottom: 30 }}
                  >
                    <defs>
                      <linearGradient id="confidenceBand" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="5%" stopColor="#2196F3" stopOpacity={0.3} />
                        <stop offset="95%" stopColor="#2196F3" stopOpacity={0.05} />
                      </linearGradient>
                    </defs>

                    <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />

                    <XAxis
                      dataKey="date"
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                      label={{ value: "ds", position: "insideBottom", offset: -15, fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                      tickLine={false}
                      minTickGap={30}
                      interval="preserveStartEnd"
                    />

                    <YAxis
                      stroke="hsl(var(--muted-foreground))"
                      tick={{ fontSize: 11, fill: "hsl(var(--muted-foreground))" }}
                      label={{ value: "y", angle: -90, position: "insideLeft", offset: 10, fill: "hsl(var(--muted-foreground))", fontSize: 12 }}
                      tickLine={false}
                      axisLine={false}
                    />

                    <Tooltip
                      contentStyle={{
                        backgroundColor: "hsl(var(--card))",
                        border: "1px solid hsl(var(--border))",
                        borderRadius: "8px",
                        fontSize: "12px",
                      }}
                      formatter={(value: any, name: string) => {
                        if (name === "actual_point") return [value, "Thực tế"];
                        if (name === "forecast") return [value?.toFixed(1), "Dự báo"];
                        if (name === "forecast_upper") return [value?.toFixed(1), "Giới hạn trên"];
                        if (name === "forecast_lower") return [value?.toFixed(1), "Giới hạn dưới"];
                        return [value, name];
                      }}
                    />

                    <Legend
                      verticalAlign="top"
                      align="right"
                      iconSize={10}
                      formatter={(value) => {
                        const map: Record<string, string> = {
                          forecast_upper: "Khoảng tin cậy",
                          forecast: "Đường dự báo",
                          actual_point: "Dữ liệu thực tế",
                        };
                        return map[value] || value;
                      }}
                    />

                    {/* Confidence band: vùng mờ xanh giữa upper và lower */}
                    <Area
                      type="monotone"
                      dataKey="forecast_upper"
                      fill="url(#confidenceBand)"
                      fillOpacity={1}
                      stroke="#2196F3"
                      strokeOpacity={0.2}
                      strokeWidth={1}
                      name="forecast_upper"
                      legendType="none"
                      activeDot={false}
                    />
                    <Area
                      type="monotone"
                      dataKey="forecast_lower"
                      fill="hsl(var(--background))"
                      fillOpacity={1}
                      stroke="#2196F3"
                      strokeOpacity={0.2}
                      strokeWidth={1}
                      name="forecast_lower"
                      legendType="none"
                      activeDot={false}
                    />

                    {/* Đường dự báo chính: xanh dương liền */}
                    <Line
                      type="monotone"
                      dataKey="forecast"
                      name="forecast"
                      stroke="#1565C0"
                      strokeWidth={2}
                      dot={false}
                      activeDot={{ r: 4, fill: "#1565C0" }}
                      connectNulls
                    />

                    {/* Dữ liệu thực tế: chấm đen rải rác */}
                    <Scatter
                      dataKey="actual"
                      name="actual_point"
                      fill="#201f1fff"
                      opacity={0.8}
                      r={3}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              </div>

              {prophetForecast.length > 0 && prophetForecast[prophetForecast.length - 1].is_future && (
                <div className="mt-4 flex flex-col gap-3">
                  <div className="flex items-center gap-3 rounded-lg border border-blue-500/20 bg-blue-500/5 p-3">
                    <div className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
                    <p className="text-sm text-muted-foreground">
                      Dự báo trong <span className="font-semibold text-foreground">{prophetForecast.filter(d => d.is_future).length} ngày</span> tiếp theo dựa trên lịch sử tự động thu thập.
                    </p>
                  </div>

                  {prophetMetrics && prophetMetrics.rmse !== null && (
                    <div className="grid grid-cols-2 md:grid-cols-3 gap-4 pt-2">
                      <div className="rounded-lg border bg-muted/20 p-3">
                        <div className="text-xs text-muted-foreground mb-1">Sai số RMSE</div>
                        <div className="text-lg font-bold text-foreground">{prophetMetrics.rmse}</div>
                      </div>
                      <div className="rounded-lg border bg-muted/20 p-3">
                        <div className="text-xs text-muted-foreground mb-1">Sai số MAE</div>
                        <div className="text-lg font-bold text-foreground">{prophetMetrics.mae}</div>
                      </div>
                      <div className="col-span-2 md:col-span-1 rounded-lg border bg-muted/20 p-3 flex flex-col justify-center">
                        <div className="text-xs text-muted-foreground">Phương pháp Test:</div>
                        <div className="text-sm font-medium">{prophetMetrics.eval_method}</div>
                      </div>
                    </div>
                  )}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>


      </Tabs>


    </div>
  );
};

export default DataAnalysis;
