import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue
} from "@/components/ui/select";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle
} from "@/components/ui/dialog";
import { Clock, Play, RefreshCw, Settings2, CheckCircle2, XCircle, ShieldAlert, Timer } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Article } from "@/types";

interface SchedulerStatus {
  is_enabled: boolean;
  interval_hours: number;
  last_run_at: string | null;
  next_run_at: string | null;
  last_run_saved_count: number;
  scheduler_running: boolean;
}

const ADMIN_SCAN_STATE_KEY = "epi_scout_admin_scan_state";

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const SchedulerConfig = () => {
  const { toast } = useToast();
  const [status, setStatus] = useState<SchedulerStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [running, setRunning] = useState(false);
  const [runNowDialogOpen, setRunNowDialogOpen] = useState(false);

  // Manual Scan Options
  const [scanStartDate, setScanStartDate] = useState("");
  const [scanEndDate, setScanEndDate] = useState("");

  // Timer & Results
  const [scanElapsedTime, setScanElapsedTime] = useState(0);
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const scanTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [showResultModal, setShowResultModal] = useState(false);

  const fetchStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/scheduler/status", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed");
      setStatus(await res.json());
    } catch {
      toast({ title: "Lỗi", description: "Không thể tải trạng thái scheduler", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStatus();
    // Sync scan state from sessionStorage
    const saved = sessionStorage.getItem(ADMIN_SCAN_STATE_KEY);
    if (saved) {
      const state = JSON.parse(saved);
      if (state.isScanning && state.startedAt) {
        setRunning(true);
        setScanStartedAt(state.startedAt);
        setScanElapsedTime(Math.floor((Date.now() - state.startedAt) / 1000));
      }
    }
  }, []);

  useEffect(() => {
    if (running && scanStartedAt) {
      scanTimerRef.current = setInterval(() => {
        setScanElapsedTime(Math.floor((Date.now() - scanStartedAt) / 1000));
      }, 1000);
      sessionStorage.setItem(ADMIN_SCAN_STATE_KEY, JSON.stringify({ isScanning: true, startedAt: scanStartedAt }));
    } else {
      if (scanTimerRef.current) clearInterval(scanTimerRef.current);
      sessionStorage.removeItem(ADMIN_SCAN_STATE_KEY);
    }
    return () => { if (scanTimerRef.current) clearInterval(scanTimerRef.current); };
  }, [running, scanStartedAt]);

  const handleToggleEnabled = async (enabled: boolean) => {
    setSaving(true);
    try {
      const res = await fetch("/api/scheduler/config", {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ is_enabled: enabled }),
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setStatus(data);
      toast({
        title: enabled ? "Đã bật auto-scan" : "Đã tắt auto-scan",
        description: enabled
          ? "Hệ thống sẽ tự động quét theo lịch đã cấu hình"
          : "Hệ thống đã dừng tự động quét",
      });
    } catch {
      toast({ title: "Lỗi", description: "Không thể cập nhật cấu hình", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleIntervalChange = async (hours: string) => {
    setSaving(true);
    try {
      const res = await fetch("/api/scheduler/config", {
        method: "PUT",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({ interval_hours: parseInt(hours) }),
      });
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      setStatus(data);
      toast({ title: "Đã cập nhật", description: `Chu kỳ quét: mỗi ${hours} giờ` });
    } catch {
      toast({ title: "Lỗi", description: "Không thể cập nhật chu kỳ", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleRunNow = async () => {
    setRunning(true);
    setScanStartedAt(Date.now());
    setScanElapsedTime(0);
    setRunNowDialogOpen(false);

    try {
      const res = await fetch("/api/scheduler/run-now", {
        method: "POST",
        headers: { ...authHeaders(), "Content-Type": "application/json" },
        body: JSON.stringify({
          start_date: scanStartDate || null,
          end_date: scanEndDate || null,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed");
      }
      const result = await res.json();

      toast({
        title: "Quét hoàn tất",
        description: `Đã lưu ${result.saved_count} bài báo mới. Thời gian: ${scanElapsedTime}s`,
      });

      fetchStatus();
    } catch (e: unknown) {
      toast({
        title: "Lỗi",
        description: e instanceof Error ? e.message : "Quét thất bại",
        variant: "destructive",
      });
    } finally {
      setRunning(false);
      setScanStartedAt(null);
    }
  };

  const formatDateTime = (dt: string | null) => {
    if (!dt) return "Chưa có";
    return new Date(dt).toLocaleString("vi-VN", {
      day: "2-digit", month: "2-digit", year: "numeric",
      hour: "2-digit", minute: "2-digit",
    });
  };

  if (loading) {
    return <div className="text-center text-muted-foreground py-8">Đang tải...</div>;
  }

  if (!status) return null;

  return (
    <div className="space-y-6">
      {/* Status overview */}
      <div className="grid gap-4 sm:grid-cols-3">
        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              {status.scheduler_running ? (
                <CheckCircle2 className="h-8 w-8 text-green-500 shrink-0" />
              ) : (
                <XCircle className="h-8 w-8 text-destructive shrink-0" />
              )}
              <div>
                <p className="text-xs text-muted-foreground">APScheduler</p>
                <p className="font-semibold text-sm">
                  {status.scheduler_running ? "Đang chạy" : "Đã dừng"}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <Clock className="h-8 w-8 text-primary shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Quét cuối</p>
                <p className="font-semibold text-sm">{formatDateTime(status.last_run_at)}</p>
                {status.last_run_saved_count > 0 && (
                  <p className="text-xs text-muted-foreground">{status.last_run_saved_count} bài đã lưu</p>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-5 pb-4">
            <div className="flex items-center gap-3">
              <RefreshCw className="h-8 w-8 text-accent shrink-0" />
              <div>
                <p className="text-xs text-muted-foreground">Quét tiếp theo</p>
                <p className="font-semibold text-sm">{formatDateTime(status.next_run_at)}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Config card */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Settings2 className="h-5 w-5 text-primary" />
            Cấu hình Auto Crawler
          </CardTitle>
          <CardDescription>
            Hệ thống sẽ tự động quét bài báo theo chu kỳ, sử dụng toàn bộ từ khóa đang kích hoạt trong DB.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Toggle bật/tắt */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label htmlFor="scheduler-toggle" className="text-sm font-medium">Tự động quét</Label>
              <p className="text-xs text-muted-foreground">
                {status.is_enabled
                  ? `Đang bật — quét mỗi ${status.interval_hours} giờ`
                  : "Đang tắt — không tự động quét"}
              </p>
            </div>
            <Switch
              id="scheduler-toggle"
              checked={status.is_enabled}
              onCheckedChange={handleToggleEnabled}
              disabled={saving}
            />
          </div>

          {/* Chu kỳ */}
          <div className="flex items-center justify-between rounded-lg border p-4">
            <div className="space-y-0.5">
              <Label className="text-sm font-medium">Chu kỳ quét</Label>
              <p className="text-xs text-muted-foreground">Khoảng thời gian giữa các lần quét tự động</p>
            </div>
            <Select
              value={String(status.interval_hours)}
              onValueChange={handleIntervalChange}
              disabled={saving}
            >
              <SelectTrigger className="w-32" id="scheduler-interval">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="2">Mỗi 2 giờ</SelectItem>
                <SelectItem value="4">Mỗi 4 giờ</SelectItem>
                <SelectItem value="6">Mỗi 6 giờ</SelectItem>
                <SelectItem value="8">Mỗi 8 giờ</SelectItem>
                <SelectItem value="12">Mỗi 12 giờ</SelectItem>
                <SelectItem value="24">Mỗi 24 giờ</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {/* Manual Scan Section */}
          <div className="space-y-4 rounded-lg border p-4 bg-muted/20">
            <div className="flex items-center justify-between">
              <div className="space-y-0.5">
                <Label className="text-sm font-medium">Quét thủ công nâng cao</Label>
                <p className="text-xs text-muted-foreground">Tùy chỉnh khoảng thời gian và phạm vi quét</p>
              </div>
              {running && (
                <Badge variant="secondary" className="animate-pulse flex gap-1 items-center">
                  <Timer className="h-3 w-3" /> {scanElapsedTime}s
                </Badge>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Từ ngày</Label>
                <Input
                  type="date"
                  value={scanStartDate}
                  onChange={(e) => setScanStartDate(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Đến ngày</Label>
                <Input
                  type="date"
                  value={scanEndDate}
                  onChange={(e) => setScanEndDate(e.target.value)}
                  className="h-8 text-xs"
                />
              </div>
            </div>

            <div className="flex items-center justify-end pt-2 border-t">
              <Button
                variant="default"
                size="sm"
                className="gap-2"
                onClick={() => setRunNowDialogOpen(true)}
                disabled={running}
              >
                {running ? (
                  <RefreshCw className="h-3 w-3 animate-spin" />
                ) : (
                  <Play className="h-3 w-3" />
                )}
                {running ? "Đang quét..." : "Bắt đầu quét"}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Confirm dialog */}
      <Dialog open={runNowDialogOpen} onOpenChange={setRunNowDialogOpen}>
        <DialogContent className="sm:max-w-sm">
          <DialogHeader>
            <DialogTitle>Xác nhận quét thủ công</DialogTitle>
            <DialogDescription>
              Hệ thống sẽ quét tất cả từ khóa đang kích hoạt, từ{" "}
              <strong>{scanStartDate || formatDateTime(status.last_run_at)}</strong> đến{" "}
              <strong>{scanEndDate || "Hiện tại"}</strong>.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" onClick={() => setRunNowDialogOpen(false)}>Hủy</Button>
            <Button onClick={handleRunNow} className="gap-2">
              <Play className="h-4 w-4" /> Bắt đầu ngay
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default SchedulerConfig;
