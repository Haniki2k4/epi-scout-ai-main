import { useEffect, useMemo, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { TrendingUp, Download, FileText, BarChart3, Database, Sparkles, ShieldAlert, Send, CalendarClock, RadioTower, MapPin, AlertTriangle, Table2, Lock } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { NewsEvent } from "@/types";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/use-toast";
import { DiseaseCauseBreakdown } from "@/components/DiseaseCauseBreakdown";
import { ArticleDetailList } from "@/components/ArticleDetailList";
import { DiseaseTrendAnalysis } from "@/components/DiseaseTrendAnalysis";
import { AnalysisReportSummary } from "@/components/AnalysisReportSummary";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/contexts/AuthContext";


interface DataAnalysisProps {
  showOnlyReport?: boolean;
}

const DataAnalysis = ({ showOnlyReport = false }: DataAnalysisProps) => {
  const { toast } = useToast();
  const { isGuest } = useAuth();
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [reportScope, setReportScope] = useState("weekly");
  const [reportType, setReportType] = useState<"signal" | "verified">("signal");
  // State báo cáo
  const [exportingWord, setExportingWord] = useState(false);
  const [exportingExcel, setExportingExcel] = useState(false);
  const [emailDialogOpen, setEmailDialogOpen] = useState(false);
  const [sendingEmail, setSendingEmail] = useState(false);
  const [emailAttachWord, setEmailAttachWord] = useState(true);
  const [emailAttachExcel, setEmailAttachExcel] = useState(true);



  useEffect(() => {
    fetch("/api/events?limit=100")
      .then((response) => response.ok ? response.json() : Promise.reject(new Error("Không tải được sự kiện")))
      .then((data: NewsEvent[]) => setEvents(data))
      .catch((error) => console.error("Failed to fetch report preview", error));
  }, []);
  // --- Report scope to hours mapping ---
  const scopeHours = useMemo(() => {
    if (reportScope === "daily") return 24;
    if (reportScope === "weekly") return 72;
    return 720; // monthly ~30 days
  }, [reportScope]);

  const previewEvents = useMemo(() => events.filter((event) =>
    (reportType === "signal" || event.status === "verified_event") &&
    new Date(event.event_date).getTime() >= Date.now() - scopeHours * 60 * 60 * 1000
  ), [events, reportType, scopeHours]);
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
        body: JSON.stringify({ scope_hours: scopeHours, report_type: reportType }),
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
        body: JSON.stringify({ scope_hours: scopeHours, report_type: reportType }),
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
          report_type: reportType,
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



  const reportTabContent = (
    <div className="report-layout">
      <div className="report-heading flex flex-wrap items-start justify-between gap-4">
        <div>
          <h3 className="text-lg font-semibold text-foreground">Cấu hình tham số</h3>
          <p className="text-sm text-muted-foreground">Chọn đối tượng và khung thời gian cho báo cáo tự động.</p>
        </div>
        <div className="flex flex-wrap gap-2">
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

      <div className="report-config space-y-5">
        <div className="space-y-2">
          <Label>Loại báo cáo</Label>
          <Select value={reportType} onValueChange={(value) => setReportType(value as "signal" | "verified")}>
            <SelectTrigger><SelectValue /></SelectTrigger>
            <SelectContent>
              <SelectItem value="signal">Tín hiệu và sự kiện (trừ bác bỏ)</SelectItem>
              <SelectItem value="verified">Chỉ sự kiện đã xác minh</SelectItem>
            </SelectContent>
          </Select>
        </div>
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

      </div>

      <div className="report-preview min-w-0">
        <Card className="overflow-hidden">
          <CardHeader>
            <CardTitle>Xem nhanh sự kiện</CardTitle>
            <CardDescription>Lọc theo loại và kỳ báo cáo; file xuất có thêm các mục chi tiết.</CardDescription>
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
                  {previewEvents.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-center py-6 text-muted-foreground">
                        Không có sự kiện phù hợp loại và kỳ báo cáo.
                      </TableCell>
                    </TableRow>
                  ) : (
                    previewEvents.slice(0, 5).map((event, idx) => (
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
                          {event.case_count != null && event.case_count > 0 ? (
                            <Badge variant="destructive">{event.case_count} ca đã xác minh</Badge>
                          ) : "Chưa có số ca xác minh"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={event.status === "verified_event" ? "default" : "secondary"}>
                            {event.status === "verified_event" ? "Đã xác minh" : "Tín hiệu"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>
            </div>
            <div className="p-4 border-t text-sm text-muted-foreground text-center bg-secondary/20">
              Hiển thị tối đa 5 sự kiện. File xuất được tạo từ dữ liệu mới nhất.
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
                Loại: <strong>{reportType === "verified" ? "Sự kiện đã xác minh" : "Tín hiệu và sự kiện"}</strong> · Khoảng thời gian: <strong>{scopeHours} giờ gần nhất</strong>
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
      <AnalysisReportSummary />
      <ArticleDetailList />
      <details className="rounded-lg border p-4">
        <summary className="cursor-pointer font-medium">Thống kê theo bệnh và tác nhân</summary>
        <div className="pt-4"><DiseaseCauseBreakdown /></div>
      </details>
      <DiseaseTrendAnalysis />


    </div>
  );
};

export default DataAnalysis;
