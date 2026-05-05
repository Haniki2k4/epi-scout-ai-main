import { useState, useEffect } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { useToast } from "@/components/ui/use-toast";
import { Settings, Save, Mail, Send, Filter, Clock } from "lucide-react";

interface UserProfile {
  username: string;
  role: string;
  email: string | null;
  report_schedule_type: string;
  report_schedule_time: string | null;
  report_schedule_day: number | null;
  report_filter_id: number | null;
}

interface UserAlert {
  id: number;
  name: string;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export const UserSettingsModal = ({ children }: { children: React.ReactNode }) => {
  const { toast } = useToast();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sendingNow, setSendingNow] = useState(false);

  const [alerts, setAlerts] = useState<UserAlert[]>([]);

  // Form state
  const [email, setEmail] = useState("");
  const [scheduleType, setScheduleType] = useState("none"); // none, daily, weekly
  const [scheduleTime, setScheduleTime] = useState("08:00");
  const [scheduleDay, setScheduleDay] = useState("0");
  const [filterId, setFilterId] = useState("none");

  useEffect(() => {
    if (open) {
      fetchData();
    }
  }, [open]);

  const fetchData = async () => {
    setLoading(true);
    try {
      // Lấy danh sách alert
      const resAlerts = await fetch("/api/alerts", { headers: authHeaders() });
      if (resAlerts.ok) {
        const data = await resAlerts.json();
        setAlerts(data);
      }

      // Lấy hồ sơ user
      const res = await fetch("/api/auth/me", { headers: authHeaders() });
      if (!res.ok) throw new Error("Lỗi xác thực");
      const data: UserProfile = await res.json();
      
      setEmail(data.email || "");
      setScheduleType(data.report_schedule_type || "none");
      if (data.report_schedule_time) setScheduleTime(data.report_schedule_time);
      if (data.report_schedule_day !== null) setScheduleDay(data.report_schedule_day.toString());
      if (data.report_filter_id) setFilterId(data.report_filter_id.toString());
    } catch {
      toast({ title: "Lỗi", description: "Không thể lấy dữ liệu", variant: "destructive" });
      setOpen(false);
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    setSaving(true);
    try {
      const body: Record<string, any> = {
        email: email.trim() || null,
        report_schedule_type: scheduleType,
        report_schedule_time: scheduleTime,
        report_schedule_day: scheduleType === "weekly" ? parseInt(scheduleDay) : null,
        report_filter_id: filterId === "none" ? null : parseInt(filterId),
      };

      const res = await fetch("/api/auth/me", {
        method: "PUT",
        headers: {
          ...authHeaders(),
          "Content-Type": "application/json",
        },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Không thể cập nhật");
      }

      toast({ title: "Thành công", description: "Đã cập nhật cấu hình gửi báo cáo" });
      setOpen(false);
    } catch (e: any) {
      toast({ title: "Lỗi", description: e.message, variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleSendNow = async () => {
    setSendingNow(true);
    try {
      // Phải save trước hoặc dùng api /send-report-now
      const res = await fetch("/api/auth/me/send-report-now", {
        method: "POST",
        headers: authHeaders(),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Lỗi gửi báo cáo");
      
      toast({ title: "Đang gửi", description: data.message });
    } catch (e: any) {
      toast({ title: "Lỗi", description: e.message, variant: "destructive" });
    } finally {
      setSendingNow(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>{children}</DialogTrigger>
      <DialogContent className="sm:max-w-[480px] max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-primary" />
            Cài đặt báo cáo
          </DialogTitle>
          <DialogDescription>
            Quản lý địa chỉ nhận và tùy chỉnh lịch gửi báo cáo dịch tễ cá nhân hóa.
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="py-8 text-center text-sm text-muted-foreground">Đang tải...</div>
        ) : (
          <div className="grid gap-5 py-4">
            <div className="space-y-2">
              <Label htmlFor="user-email">Email nhận báo cáo</Label>
              <div className="flex relative">
                <Mail className="w-4 h-4 absolute left-3 top-3 text-muted-foreground" />
                <Input
                  id="user-email"
                  type="email"
                  placeholder="ví dụ: canbo@cdc.gov.vn"
                  className="pl-9"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>
            </div>

            <div className="space-y-4 rounded-lg border p-4 bg-muted/20">
              <div className="flex items-center justify-between mb-2">
                <Label className="text-sm font-semibold flex items-center gap-2">
                  <Filter className="w-4 h-4 text-primary" />
                  Nội dung báo cáo
                </Label>
              </div>
              
              <div className="space-y-2">
                <Select value={filterId} onValueChange={setFilterId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Chọn nội dung báo cáo" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">Toàn bộ hệ thống</SelectItem>
                    {alerts.map(a => (
                      <SelectItem key={a.id} value={a.id.toString()}>
                        Bộ lọc: {a.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <p className="text-[11px] text-muted-foreground leading-tight">
                  Chọn "Toàn bộ hệ thống" để nhận tin tổng hợp toàn diện. Hoặc chọn "Bộ lọc" để nhận báo cáo tập trung theo từ khóa/địa bàn bạn quan tâm.
                </p>
              </div>
            </div>

            <div className="space-y-4 rounded-lg border p-4 bg-muted/20">
              <Label className="text-sm font-semibold flex items-center gap-2">
                <Clock className="w-4 h-4 text-primary" />
                Lịch gửi tự động
              </Label>
              
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label className="text-xs">Chu kỳ lặp</Label>
                  <Select value={scheduleType} onValueChange={setScheduleType}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="none">Không tự động gửi</SelectItem>
                      <SelectItem value="hourly">Hàng giờ</SelectItem>
                      <SelectItem value="daily">Hàng ngày</SelectItem>
                      <SelectItem value="weekly">Hàng tuần</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                {scheduleType !== "none" && (
                  <div className="space-y-2">
                    <Label className="text-xs">
                      {scheduleType === "hourly" ? "Phút gửi (chỉ dùng phút)" : "Thời gian gửi"}
                    </Label>
                    <Input 
                      type="time" 
                      value={scheduleTime} 
                      onChange={e => setScheduleTime(e.target.value)} 
                    />
                  </div>
                )}
              </div>

              {scheduleType === "weekly" && (
                <div className="space-y-2">
                  <Label className="text-xs">Gửi vào Thứ</Label>
                  <Select value={scheduleDay} onValueChange={setScheduleDay}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="0">Thứ Hai</SelectItem>
                      <SelectItem value="1">Thứ Ba</SelectItem>
                      <SelectItem value="2">Thứ Tư</SelectItem>
                      <SelectItem value="3">Thứ Năm</SelectItem>
                      <SelectItem value="4">Thứ Sáu</SelectItem>
                      <SelectItem value="5">Thứ Bảy</SelectItem>
                      <SelectItem value="6">Chủ Nhật</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              )}

              <div className="pt-2">
                <Button 
                  variant="secondary" 
                  className="w-full text-xs h-8"
                  onClick={handleSendNow}
                  disabled={sendingNow || !email}
                >
                  <Send className="w-3 h-3 mr-2" />
                  {sendingNow ? "Đang gửi..." : "Thử nghiệm: Gửi báo cáo ngay bây giờ"}
                </Button>
                {!email && <p className="text-[10px] text-destructive mt-1 text-center">Vui lòng nhập Email và Lưu để gửi</p>}
              </div>
            </div>

          </div>
        )}

        <div className="flex justify-end gap-3 pt-2">
          <Button variant="outline" onClick={() => setOpen(false)}>Đóng</Button>
          <Button onClick={handleSave} disabled={saving || loading}>
            <Save className="w-4 h-4 mr-2" />
            {saving ? "Đang lưu..." : "Lưu thay đổi"}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
