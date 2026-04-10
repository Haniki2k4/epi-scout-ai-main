import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus, Tag, Rss, RefreshCcw, Link as LinkIcon, RadioReceiver, Power } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Edit } from "lucide-react";

// Types
interface KeywordModel {
  id: number;
  text: string;
}

interface RssSourceModel {
  id: number;
  url: string;
  label: string | null;
  category: string | null;
  is_active: boolean;
}

export default function ResourceManagement() {
  const queryClient = useQueryClient();

  // Keyword states
  const [newKeyword, setNewKeyword] = useState("");
  const [isEditKwModalOpen, setIsEditKwModalOpen] = useState(false);
  const [editKwItem, setEditKwItem] = useState<KeywordModel | null>(null);
  const [editKwText, setEditKwText] = useState("");

  // RSS states
  const [newRssUrl, setNewRssUrl] = useState("");
  const [newRssLabel, setNewRssLabel] = useState("");
  const [newRssCategory, setNewRssCategory] = useState("the-gioi");

  // Fetch Keywords
  const { data: keywords = [], isLoading: loadKw } = useQuery<KeywordModel[]>({
    queryKey: ["admin_keywords"],
    queryFn: async () => {
      const res = await fetch("/api/keywords?limit=1000");
      if (!res.ok) throw new Error("Failed to fetch keywords");
      return res.json();
    },
  });

  // Fetch RSS Sources
  const { data: rssSources = [], isLoading: loadRss } = useQuery<RssSourceModel[]>({
    queryKey: ["admin_rss"],
    queryFn: async () => {
      const res = await fetch("/api/rss-sources");
      if (!res.ok) throw new Error("Failed to fetch RSS sources");
      return res.json();
    },
  });

  // ============ KEYWORD MUTATIONS ============
  const createKwMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await fetch("/api/keywords", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Không thể thêm từ khóa");
      }
      return res.json();
    },
    onSuccess: () => {
      setNewKeyword("");
      queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
      toast.success("Thêm từ khóa thành công");
    },
    onError: (e) => toast.error(e.message),
  });

  const deleteKwMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/keywords/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Xóa thất bại");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
      toast.success("Đã xóa từ khóa");
    },
    onError: (e) => toast.error(e.message),
  });

  const updateKwMutation = useMutation({
    mutationFn: async ({ id, text }: { id: number; text: string }) => {
      const res = await fetch(`/api/keywords/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Cập nhật từ khóa thất bại");
      }
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
      toast.success("Đã cập nhật từ khóa");
      setIsEditKwModalOpen(false);
    },
    onError: (e) => toast.error(e.message),
  });

  // ============ RSS MUTATIONS ============
  const createRssMutation = useMutation({
    mutationFn: async (data: { url: string, label: string, category: string }) => {
      const res = await fetch("/api/rss-sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Không thể thêm RSS");
      }
      return res.json();
    },
    onSuccess: () => {
      setNewRssUrl("");
      setNewRssLabel("");
      queryClient.invalidateQueries({ queryKey: ["admin_rss"] });
      toast.success("Thêm RSS Source thành công");
    },
    onError: (e) => toast.error(e.message),
  });

  const toggleRssMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await fetch(`/api/rss-sources/${id}/toggle`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ is_active }),
      });
      if (!res.ok) throw new Error("Cập nhật thất bại");
      return res.json();
    },
    onSuccess: (_, { is_active }) => {
      queryClient.invalidateQueries({ queryKey: ["admin_rss"] });
      toast.success(is_active ? "Đã bật nguồn RSS" : "Đã tắt nguồn RSS");
    },
    onError: (e) => toast.error(e.message),
  });

  // ============ HANDLERS ============
  const handleAddKeyword = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyword.trim()) return;
    createKwMutation.mutate(newKeyword);
  };

  const handleEditKwSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editKwItem || !editKwText.trim()) return;
    updateKwMutation.mutate({ id: editKwItem.id, text: editKwText.trim() });
  };

  const openEditKwModal = (kw: KeywordModel) => {
    setEditKwItem(kw);
    setEditKwText(kw.text);
    setIsEditKwModalOpen(true);
  };

  const handleAddRss = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newRssUrl.trim()) return;
    createRssMutation.mutate({
      url: newRssUrl,
      label: newRssLabel || "Custom Source",
      category: newRssCategory,
    });
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ---------------- KEYWORD BLOCK ---------------- */}
      <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" />
            <CardTitle>Từ Khóa Giám Sát</CardTitle>
          </div>
          <CardDescription>Các từ khóa hệ thống dùng để chấm điểm bản tin dịch bệnh.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddKeyword} className="flex gap-2 mb-4">
            <Input
              placeholder="Ví dụ: Cúm gia cầm, Cúm A/H5N1, Bạch hầu..."
              value={newKeyword}
              onChange={(e) => setNewKeyword(e.target.value)}
              disabled={createKwMutation.isPending}
            />
            <Button type="submit" disabled={createKwMutation.isPending} className="whitespace-nowrap">
              {createKwMutation.isPending ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />} Thêm
            </Button>
          </form>

          <div className="rounded-md border border-border/50 overflow-auto h-[400px]">
            {loadKw ? (
              <div className="flex justify-center p-8"><RefreshCcw className="h-6 w-6 animate-spin text-primary" /></div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0">
                  <TableRow>
                    <TableHead>Từ khóa (Keyword)</TableHead>
                    <TableHead className="w-[80px] text-right">Xóa</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {keywords.map(kw => (
                    <TableRow key={kw.id}>
                      <TableCell className="font-medium align-middle">
                        <Badge variant="outline" className="text-sm bg-background">
                          {kw.text}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditKwModal(kw)}
                            className="hover:text-blue-700 hover:bg-blue-200"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => deleteKwMutation.mutate(kw.id)}
                            className="text-destructive hover:text-destructive hover:bg-destructive/10"
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                  {keywords.length === 0 && (
                    <TableRow><TableCell colSpan={2} className="text-center py-4 text-muted-foreground">Chưa có từ khóa</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ---------------- RSS BLOCK ---------------- */}
      <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-orange-500" />
            <CardTitle>Nguồn RSS Báo Chí</CardTitle>
          </div>
          <CardDescription>Cấu hình các luồng RSS để Bot tự động thu thập bài báo.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddRss} className="mb-4 bg-muted/40 p-4 rounded-lg border border-border/50 space-y-3">
            <div className="space-y-2">
              <label className="text-xs font-medium">Đường dẫn RSS (URL) *</label>
              <div className="relative">
                <LinkIcon className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                <Input
                  className="pl-9 bg-background"
                  placeholder="https://vnexpress.net/rss/the-gioi.rss"
                  value={newRssUrl}
                  onChange={(e) => setNewRssUrl(e.target.value)}
                  disabled={createRssMutation.isPending}
                  required
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-xs font-medium">Nhãn hiển thị (Tự chọn)</label>
                <div className="relative">
                  <RadioReceiver className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9 bg-background"
                    placeholder="VnExpress Thể giới"
                    value={newRssLabel}
                    onChange={(e) => setNewRssLabel(e.target.value)}
                    disabled={createRssMutation.isPending}
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-xs font-medium">Phân loại</label>
                <select
                  className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background disabled:opacity-50"
                  value={newRssCategory}
                  onChange={(e) => setNewRssCategory(e.target.value)}
                >
                  <option value="the-gioi">Thế Giới</option>
                  <option value="suc-khoe">Sức Khỏe / Y Tế</option>
                  <option value="trong-nuoc">Trong Nước</option>
                  <option value="global">Toàn Cầu (Global)</option>
                </select>
              </div>
            </div>
            <Button type="submit" disabled={createRssMutation.isPending} className="w-full">
              {createRssMutation.isPending ? <RefreshCcw className="h-4 w-4 animate-spin mr-2" /> : <Plus className="h-4 w-4 mr-2" />}
              Thêm Nguồn RSS
            </Button>
          </form>

          <div className="rounded-md border border-border/50 overflow-auto h-[255px]">
            {loadRss ? (
              <div className="flex justify-center p-8"><RefreshCcw className="h-6 w-6 animate-spin text-primary" /></div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0">
                  <TableRow>
                    <TableHead>Tên Nguồn / Phân Loại</TableHead>
                    <TableHead className="w-[100px] text-right">Trạng thái</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {rssSources.map(rss => (
                    <TableRow key={rss.id}>
                      <TableCell className="align-middle">
                        <div className="font-semibold text-sm">{rss.label || "N/A"}</div>
                        <div className="text-xs text-muted-foreground truncate max-w-[200px] xl:max-w-[300px]" title={rss.url}>{rss.url}</div>
                        <Badge className="mt-1 text-[10px]" variant="secondary">{rss.category}</Badge>
                      </TableCell>
                      <TableCell className="text-right align-middle">
                        <button
                          type="button"
                          onClick={() => toggleRssMutation.mutate({ id: rss.id, is_active: !rss.is_active })}
                          disabled={toggleRssMutation.isPending}
                          title={rss.is_active ? "Nhấn để tắt nguồn này" : "Nhấn để bật nguồn này"}
                          className={`inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-semibold border transition-colors ${rss.is_active
                              ? "bg-green-100 text-green-700 border-green-200 hover:bg-red-100 hover:text-red-600 hover:border-red-200"
                              : "bg-muted text-muted-foreground border-border hover:bg-green-100 hover:text-green-700 hover:border-green-200"
                            }`}
                        >
                          <Power className="h-3 w-3" />
                          {rss.is_active ? "Bật" : "Tắt"}
                        </button>
                      </TableCell>
                    </TableRow>
                  ))}
                  {rssSources.length === 0 && (
                    <TableRow><TableCell colSpan={2} className="text-center py-4 text-muted-foreground">Chưa có nguồn RSS</TableCell></TableRow>
                  )}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Edit Keyword Modal */}
      <Dialog open={isEditKwModalOpen} onOpenChange={setIsEditKwModalOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleEditKwSubmit}>
            <DialogHeader>
              <DialogTitle>Sửa từ khóa</DialogTitle>
              <DialogDescription>
                Thay đổi nội dung từ khóa tự định nghĩa.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Từ khóa mới</label>
                <div className="relative">
                  <Tag className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    value={editKwText}
                    onChange={(e) => setEditKwText(e.target.value)}
                    required
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setIsEditKwModalOpen(false)}>
                Hủy
              </Button>
              <Button type="submit" disabled={updateKwMutation.isPending}>
                {updateKwMutation.isPending && <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />}
                Lưu Thay Đổi
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
