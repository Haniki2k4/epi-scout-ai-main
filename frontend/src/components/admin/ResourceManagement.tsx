import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus, Tag, Rss, RefreshCcw, Link as LinkIcon, RadioReceiver, Power, Edit } from "lucide-react";

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
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// Types
interface KeywordModel {
  id: number;
  text: string;
  is_active: boolean;
}

interface RssSourceModel {
  id: number;
  url: string;
  label: string | null;
  category: string | null;
  is_active: boolean;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem("token");
  return token ? {
    "Authorization": `Bearer ${token}`,
    "Content-Type": "application/json"
  } : { "Content-Type": "application/json" };
}

export default function ResourceManagement() {
  const queryClient = useQueryClient();

  // Keyword states
  const [newKeyword, setNewKeyword] = useState("");
  const [kwSearch, setKwSearch] = useState("");
  const [isEditKwModalOpen, setIsEditKwModalOpen] = useState(false);
  const [editKwItem, setEditKwItem] = useState<KeywordModel | null>(null);
  const [editKwText, setEditKwText] = useState("");

  // RSS states
  const [newRssUrl, setNewRssUrl] = useState("");
  const [newRssLabel, setNewRssLabel] = useState("");
  const [newRssCategory, setNewRssCategory] = useState("the-gioi");
  const [rssSearch, setRssSearch] = useState("");

  // Fetch Keywords
  const { data: keywords = [], isLoading: loadKw } = useQuery<KeywordModel[]>({
    queryKey: ["admin_keywords"],
    queryFn: async () => {
      const res = await fetch("/api/keywords?limit=1000&only_active=false", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed to fetch keywords");
      return res.json();
    },
  });

  // Fetch RSS Sources
  const { data: rssSources = [], isLoading: loadRss } = useQuery<RssSourceModel[]>({
    queryKey: ["admin_rss"],
    queryFn: async () => {
      const res = await fetch("/api/rss-sources", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed to fetch RSS sources");
      return res.json();
    },
  });

  // ============ KEYWORD MUTATIONS ============
  const createKwMutation = useMutation({
    mutationFn: async (text: string) => {
      const res = await fetch("/api/keywords", {
        method: "POST",
        headers: authHeaders(),
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
      const res = await fetch(`/api/keywords/${id}`, {
        method: "DELETE",
        headers: authHeaders()
      });
      if (!res.ok) throw new Error("Xóa từ khóa thất bại");
      return res.json();
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
        headers: authHeaders(),
        body: JSON.stringify({ text }),
      });
      if (!res.ok) throw new Error("Cập nhật thất bại");
      return res.json();
    },
    onSuccess: () => {
      setIsEditKwModalOpen(false);
      queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
      toast.success("Đã cập nhật từ khóa");
    },
    onError: (e) => toast.error(e.message),
  });

  const toggleKwMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await fetch(`/api/keywords/${id}/toggle`, {
        method: "PATCH",
        headers: authHeaders(),
        body: JSON.stringify({ is_active }),
      });
      if (!res.ok) throw new Error("Cập nhật thất bại");
      return res.json();
    },
    onSuccess: (_, { is_active }) => {
      queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
      toast.success(is_active ? "Đã bật từ khóa" : "Đã tắt từ khóa");
    },
    onError: (e) => toast.error(e.message),
  });

  // ============ RSS MUTATIONS ============
  const createRssMutation = useMutation({
    mutationFn: async (data: Partial<RssSourceModel>) => {
      const res = await fetch("/api/rss-sources", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("Không thể thêm nguồn RSS");
      return res.json();
    },
    onSuccess: () => {
      setNewRssUrl("");
      setNewRssLabel("");
      queryClient.invalidateQueries({ queryKey: ["admin_rss"] });
      toast.success("Thêm nguồn RSS thành công");
    },
    onError: (e) => toast.error(e.message),
  });

  const deleteRssMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/rss-sources/${id}`, {
        method: "DELETE",
        headers: authHeaders()
      });
      if (!res.ok) throw new Error("Xóa nguồn RSS thất bại");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_rss"] });
      toast.success("Đã xóa nguồn RSS");
    },
    onError: (e) => toast.error(e.message),
  });

  const toggleRssMutation = useMutation({
    mutationFn: async ({ id, is_active }: { id: number; is_active: boolean }) => {
      const res = await fetch(`/api/rss-sources/${id}/toggle`, {
        method: "PATCH",
        headers: authHeaders(),
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

  const filteredKeywords = keywords.filter(kw => kw.text.toLowerCase().includes(kwSearch.toLowerCase()));
  const kwActiveCount = keywords.filter(k => k.is_active).length;

  const filteredRss = rssSources.filter(src => 
    src.url.toLowerCase().includes(rssSearch.toLowerCase()) || 
    (src.label && src.label.toLowerCase().includes(rssSearch.toLowerCase()))
  );
  const rssActiveCount = rssSources.filter(r => r.is_active).length;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      {/* ---------------- KEYWORD BLOCK ---------------- */}
      <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" />
            <CardTitle>Từ Khóa Giám Sát</CardTitle>
          </div>
          <CardDescription>Các từ khóa hệ thống dùng để quét tin tức. Tắt để tạm dừng quét từ khóa đó.</CardDescription>
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

          <div className="flex items-center justify-between mb-4">
            <Input
              placeholder="Tìm kiếm từ khóa..."
              value={kwSearch}
              onChange={(e) => setKwSearch(e.target.value)}
              className="max-w-[200px]"
            />
            <Badge variant="secondary">
              Tổng: {keywords.length} | Bật: {kwActiveCount}
            </Badge>
          </div>

          <div className="rounded-md border border-border/50 overflow-auto h-[400px]">
            {loadKw ? (
              <div className="flex justify-center p-8"><RefreshCcw className="h-6 w-6 animate-spin text-primary" /></div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0 z-10">
                  <TableRow>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Từ khóa (Keyword)</TableHead>
                    <TableHead className="w-[100px] text-right">Thao tác</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredKeywords.map(kw => (
                    <TableRow key={kw.id} className={!kw.is_active ? "opacity-50" : ""}>
                      <TableCell className="w-[80px]">
                        <Switch
                          checked={kw.is_active}
                          onCheckedChange={(val) => toggleKwMutation.mutate({ id: kw.id, is_active: val })}
                          disabled={toggleKwMutation.isPending}
                        />
                      </TableCell>
                      <TableCell className="font-medium align-middle">
                        <Badge variant={kw.is_active ? "outline" : "secondary"} className="text-sm bg-background">
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
                            className="hover:text-destructive hover:bg-destructive/10"
                            disabled={deleteKwMutation.isPending}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* ---------------- RSS SOURCE BLOCK ---------------- */}
      <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-primary" />
            <CardTitle>Nguồn RSS Whitelist</CardTitle>
          </div>
          <CardDescription>Các nguồn tin được tin tưởng để lấy dữ liệu tự động.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddRss} className="space-y-3 mb-6 p-4 rounded-lg border bg-muted/20">
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label className="text-xs">URL RSS</Label>
                <Input
                  placeholder="https://vnexpress.net/rss/suc-khoe.rss"
                  value={newRssUrl}
                  onChange={(e) => setNewRssUrl(e.target.value)}
                  className="bg-background"
                />
              </div>
              <div className="space-y-1">
                <Label className="text-xs">Tên nhãn (Label)</Label>
                <Input
                  placeholder="VnExpress Sức Khỏe"
                  value={newRssLabel}
                  onChange={(e) => setNewRssLabel(e.target.value)}
                  className="bg-background"
                />
              </div>
            </div>
            <div className="flex items-end gap-3">
              <div className="flex-1 space-y-1">
                <Label className="text-xs">Phân loại (Category)</Label>
                <select
                  value={newRssCategory}
                  onChange={(e) => setNewRssCategory(e.target.value)}
                  className="w-full h-10 px-3 rounded-md border border-input bg-background text-sm ring-offset-background focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2"
                >
                  <option value="thoi-su">Thời sự</option>
                  <option value="suc-khoe">Sức khỏe</option>
                  <option value="the-gioi">Thế giới</option>
                  <option value="global">Quốc tế (English)</option>
                </select>
              </div>
              <Button type="submit" disabled={createRssMutation.isPending} className="whitespace-nowrap">
                {createRssMutation.isPending ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4 mr-1" />} Thêm nguồn
              </Button>
            </div>
          </form>

          <div className="flex items-center justify-between mb-4">
            <Input
              placeholder="Tìm kiếm RSS..."
              value={rssSearch}
              onChange={(e) => setRssSearch(e.target.value)}
              className="max-w-[200px]"
            />
            <Badge variant="secondary">
              Tổng: {rssSources.length} | Bật: {rssActiveCount}
            </Badge>
          </div>

          <div className="rounded-md border border-border/50 overflow-auto h-[350px]">
            {loadRss ? (
              <div className="flex justify-center p-8"><RefreshCcw className="h-6 w-6 animate-spin text-primary" /></div>
            ) : (
              <Table>
                <TableHeader className="bg-muted/50 sticky top-0 z-10">
                  <TableRow>
                    <TableHead>Trạng thái</TableHead>
                    <TableHead>Nguồn tin</TableHead>
                    <TableHead className="w-[80px] text-right">Xóa</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filteredRss.map(src => (
                    <TableRow key={src.id} className={!src.is_active ? "opacity-50" : ""}>
                      <TableCell className="w-[80px]">
                        <Switch
                          checked={src.is_active}
                          onCheckedChange={(val) => toggleRssMutation.mutate({ id: src.id, is_active: val })}
                          disabled={toggleRssMutation.isPending}
                        />
                      </TableCell>
                      <TableCell className="align-middle">
                        <div className="flex flex-col">
                          <span className="font-medium text-sm">{src.label || "Nguồn không tên"}</span>
                          <span className="text-[10px] text-muted-foreground flex items-center gap-1">
                            <LinkIcon className="h-3 w-3" /> {src.url.substring(0, 40)}...
                          </span>
                          <Badge variant="secondary" className="w-fit text-[10px] h-4 mt-1 px-1">
                            {src.category}
                          </Badge>
                        </div>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => deleteRssMutation.mutate(src.id)}
                          className="hover:text-destructive hover:bg-destructive/10"
                          disabled={deleteRssMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Edit Keyword Modal */}
      <Dialog open={isEditKwModalOpen} onOpenChange={setIsEditKwModalOpen}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Sửa từ khóa</DialogTitle>
            <DialogDescription>
              Thay đổi nội dung từ khóa giám sát.
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleEditKwSubmit}>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="edit-kw-text" className="text-right">Nội dung</Label>
                <Input
                  id="edit-kw-text"
                  value={editKwText}
                  onChange={(e) => setEditKwText(e.target.value)}
                  className="col-span-3"
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" disabled={updateKwMutation.isPending}>
                {updateKwMutation.isPending && <RefreshCcw className="h-4 w-4 animate-spin mr-2" />}
                Lưu thay đổi
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  );
}
