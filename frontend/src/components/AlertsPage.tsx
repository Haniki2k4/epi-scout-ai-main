import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import {
  Dialog, DialogContent, DialogDescription, DialogFooter,
  DialogHeader, DialogTitle,
} from "@/components/ui/dialog";
import { Bell, Plus, Trash2, ChevronRight, Edit2, ToggleLeft, ToggleRight, Newspaper } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Article } from "@/types";

// ---- Types ----
interface UserAlert {
  id: number;
  name: string;
  keywords: string[];
  location_filter: string | null;
  is_active: boolean;
  created_at: string;
}

interface AlertFeed {
  alert_id: number;
  alert_name: string;
  total: number;
  items: Article[];
}

const API = {
  getAlerts: () => fetch("/api/alerts", { headers: authHeaders() }).then(r => r.json()),
  createAlert: (body: object) => fetch("/api/alerts", {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(r => r.json()),
  updateAlert: (id: number, body: object) => fetch(`/api/alerts/${id}`, {
    method: "PUT",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify(body),
  }).then(r => r.json()),
  deleteAlert: (id: number) => fetch(`/api/alerts/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  }).then(r => r.json()),
  getAlertFeed: (id: number, skip = 0, limit = 20) =>
    fetch(`/api/alerts/${id}/feed?skip=${skip}&limit=${limit}`, {
      headers: authHeaders(),
    }).then(r => r.json()),
};

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---- Component ----
const AlertsPage = () => {
  const { toast } = useToast();
  const [alerts, setAlerts] = useState<UserAlert[]>([]);
  const [selectedAlert, setSelectedAlert] = useState<UserAlert | null>(null);
  const [feed, setFeed] = useState<AlertFeed | null>(null);
  const [loadingFeed, setLoadingFeed] = useState(false);
  const [loadingAlerts, setLoadingAlerts] = useState(true);

  // Dialog tạo/chỉnh sửa
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingAlert, setEditingAlert] = useState<UserAlert | null>(null);
  const [formName, setFormName] = useState("");
  const [formKeywords, setFormKeywords] = useState(""); // comma-separated
  const [formLocation, setFormLocation] = useState("");
  const [saving, setSaving] = useState(false);

  // Load alerts
  useEffect(() => {
    fetchAlerts();
  }, []);

  const fetchAlerts = async () => {
    setLoadingAlerts(true);
    try {
      const data = await API.getAlerts();
      setAlerts(Array.isArray(data) ? data : []);
    } catch {
      toast({ title: "Lỗi", description: "Không thể tải danh sách cảnh báo", variant: "destructive" });
    } finally {
      setLoadingAlerts(false);
    }
  };

  const openCreateDialog = () => {
    setEditingAlert(null);
    setFormName("");
    setFormKeywords("");
    setFormLocation("");
    setDialogOpen(true);
  };

  const openEditDialog = (alert: UserAlert) => {
    setEditingAlert(alert);
    setFormName(alert.name);
    setFormKeywords(alert.keywords.join(", "));
    setFormLocation(alert.location_filter || "");
    setDialogOpen(true);
  };

  const handleSaveAlert = async () => {
    const kwList = formKeywords
      .split(",")
      .map(k => k.trim())
      .filter(k => k.length > 0);

    if (!formName.trim() || kwList.length === 0) {
      toast({ title: "Thiếu thông tin", description: "Vui lòng nhập tên và ít nhất 1 từ khóa", variant: "destructive" });
      return;
    }

    setSaving(true);
    try {
      const body = {
        name: formName.trim(),
        keywords: kwList,
        location_filter: formLocation.trim() || null,
      };

      if (editingAlert) {
        const updated = await API.updateAlert(editingAlert.id, body);
        setAlerts(prev => prev.map(a => a.id === editingAlert.id ? updated : a));
        toast({ title: "Đã cập nhật", description: `Bộ lọc "${formName}" đã được cập nhật` });
      } else {
        const created = await API.createAlert(body);
        setAlerts(prev => [created, ...prev]);
        toast({ title: "Đã tạo", description: `Bộ lọc "${formName}" đã được tạo` });
      }
      setDialogOpen(false);
    } catch {
      toast({ title: "Lỗi", description: "Không thể lưu bộ lọc", variant: "destructive" });
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteAlert = async (alert: UserAlert) => {
    if (!confirm(`Xóa bộ lọc "${alert.name}"?`)) return;
    try {
      await API.deleteAlert(alert.id);
      setAlerts(prev => prev.filter(a => a.id !== alert.id));
      if (selectedAlert?.id === alert.id) {
        setSelectedAlert(null);
        setFeed(null);
      }
      toast({ title: "Đã xóa", description: `Bộ lọc "${alert.name}" đã được xóa` });
    } catch {
      toast({ title: "Lỗi", description: "Không thể xóa bộ lọc", variant: "destructive" });
    }
  };

  const handleToggleAlert = async (alert: UserAlert) => {
    try {
      const updated = await API.updateAlert(alert.id, { is_active: !alert.is_active });
      setAlerts(prev => prev.map(a => a.id === alert.id ? updated : a));
    } catch {
      toast({ title: "Lỗi", description: "Không thể cập nhật trạng thái", variant: "destructive" });
    }
  };

  const handleViewFeed = async (alert: UserAlert) => {
    setSelectedAlert(alert);
    setLoadingFeed(true);
    setFeed(null);
    try {
      const data = await API.getAlertFeed(alert.id);
      setFeed(data);
    } catch {
      toast({ title: "Lỗi", description: "Không thể tải feed bài báo", variant: "destructive" });
    } finally {
      setLoadingFeed(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-foreground flex items-center gap-2">
            <Bell className="h-6 w-6 text-primary" />
            Cảnh Báo Cá Nhân
          </h2>
          <p className="text-muted-foreground mt-1 text-sm">
            Tạo bộ lọc từ khóa riêng để theo dõi tình hình dịch bệnh theo nhu cầu cá nhân.
          </p>
        </div>
        <Button onClick={openCreateDialog} className="gap-2">
          <Plus className="h-4 w-4" />
          Tạo bộ lọc mới
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[360px_1fr]">
        {/* Danh sách bộ lọc */}
        <div className="space-y-3">
          {loadingAlerts ? (
            <div className="text-center text-muted-foreground py-8">Đang tải...</div>
          ) : alerts.length === 0 ? (
            <Card className="border-dashed">
              <CardContent className="flex flex-col items-center justify-center py-12 text-center">
                <Bell className="h-10 w-10 text-muted-foreground mb-4 opacity-40" />
                <p className="text-sm text-muted-foreground">
                  Chưa có bộ lọc nào.<br />Bấm "Tạo bộ lọc mới" để bắt đầu.
                </p>
              </CardContent>
            </Card>
          ) : (
            alerts.map(alert => (
              <Card
                key={alert.id}
                className={`cursor-pointer transition-all hover:shadow-md ${
                  selectedAlert?.id === alert.id ? "ring-2 ring-primary" : ""
                } ${!alert.is_active ? "opacity-60" : ""}`}
              >
                <CardHeader className="pb-2 pt-4 px-4">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <CardTitle className="text-sm font-semibold truncate">{alert.name}</CardTitle>
                      {alert.location_filter && (
                        <CardDescription className="text-xs mt-0.5">📍 {alert.location_filter}</CardDescription>
                      )}
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7"
                        onClick={(e) => { e.stopPropagation(); handleToggleAlert(alert); }}
                        title={alert.is_active ? "Tắt" : "Bật"}
                      >
                        {alert.is_active
                          ? <ToggleRight className="h-4 w-4 text-primary" />
                          : <ToggleLeft className="h-4 w-4 text-muted-foreground" />
                        }
                      </Button>
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7"
                        onClick={(e) => { e.stopPropagation(); openEditDialog(alert); }}
                      >
                        <Edit2 className="h-3.5 w-3.5" />
                      </Button>
                      <Button
                        variant="ghost" size="icon" className="h-7 w-7 text-destructive hover:bg-destructive/10"
                        onClick={(e) => { e.stopPropagation(); handleDeleteAlert(alert); }}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  </div>
                </CardHeader>
                <CardContent className="px-4 pb-3">
                  <div className="flex flex-wrap gap-1 mb-3">
                    {alert.keywords.map(kw => (
                      <Badge key={kw} variant="secondary" className="text-xs">{kw}</Badge>
                    ))}
                  </div>
                  <Button
                    variant="outline" size="sm" className="w-full gap-2 text-xs h-7"
                    onClick={() => handleViewFeed(alert)}
                  >
                    <Newspaper className="h-3.5 w-3.5" />
                    Xem bài báo
                    <ChevronRight className="h-3.5 w-3.5 ml-auto" />
                  </Button>
                </CardContent>
              </Card>
            ))
          )}
        </div>

        {/* Feed bài báo */}
        <div>
          {!selectedAlert ? (
            <Card className="border-dashed h-full flex items-center justify-center min-h-[300px]">
              <CardContent className="text-center text-muted-foreground">
                <Bell className="h-10 w-10 mx-auto mb-3 opacity-30" />
                <p className="text-sm">Chọn một bộ lọc để xem danh sách bài báo phù hợp</p>
              </CardContent>
            </Card>
          ) : loadingFeed ? (
            <Card className="min-h-[300px] flex items-center justify-center">
              <CardContent className="text-center text-muted-foreground">Đang tải bài báo...</CardContent>
            </Card>
          ) : feed ? (
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-base">{feed.alert_name}</CardTitle>
                    <CardDescription>{feed.total} bài báo phù hợp trong cơ sở dữ liệu</CardDescription>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {feed.items.length === 0 ? (
                  <div className="text-center py-8 text-muted-foreground text-sm">
                    Chưa có bài báo nào khớp với bộ lọc này.
                  </div>
                ) : (
                  <div className="space-y-3">
                    {feed.items.map(article => (
                      <div key={article.id} className="rounded-lg border p-3 hover:bg-muted/40 transition-colors">
                        <a
                          href={article.link}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-medium text-sm text-foreground hover:text-primary transition-colors line-clamp-2"
                        >
                          {article.title || "Không có tiêu đề"}
                        </a>
                        <div className="flex items-center gap-3 mt-1.5 text-xs text-muted-foreground">
                          {article.source && <span className="truncate">{article.source}</span>}
                          {article.published_date && (
                            <span>
                              {new Date(article.published_date).toLocaleDateString("vi-VN")}
                            </span>
                          )}
                          {article.keywords_matched && (
                            <Badge variant="outline" className="text-xs shrink-0">
                              {article.keywords_matched.split(",")[0]?.trim()}
                            </Badge>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          ) : null}
        </div>
      </div>

      {/* Dialog tạo/chỉnh sửa */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader>
            <DialogTitle>{editingAlert ? "Chỉnh sửa bộ lọc" : "Tạo bộ lọc cảnh báo mới"}</DialogTitle>
            <DialogDescription>
              Hệ thống sẽ lọc bài báo từ cơ sở dữ liệu theo từ khóa và địa bàn bạn chọn.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <div className="space-y-2">
              <Label htmlFor="alert-name">Tên bộ lọc</Label>
              <Input
                id="alert-name"
                placeholder="VD: Theo dõi Sởi - Hà Nội"
                value={formName}
                onChange={e => setFormName(e.target.value)}
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="alert-keywords">Từ khóa theo dõi</Label>
              <Input
                id="alert-keywords"
                placeholder="VD: Sởi, sởi bùng phát, sởi Hà Nội"
                value={formKeywords}
                onChange={e => setFormKeywords(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Ngăn cách bằng dấu phẩy. Bài báo chứa BẤT KỲ từ khóa nào đều được lọc ra.</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="alert-location">Địa bàn (tùy chọn)</Label>
              <Input
                id="alert-location"
                placeholder="VD: Hà Nội, TP.HCM, Đà Nẵng..."
                value={formLocation}
                onChange={e => setFormLocation(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">Bộ lọc thêm theo địa bàn. Để trống nếu muốn xem toàn quốc.</p>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>Hủy</Button>
            <Button onClick={handleSaveAlert} disabled={saving}>
              {saving ? "Đang lưu..." : editingAlert ? "Cập nhật" : "Tạo bộ lọc"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default AlertsPage;
