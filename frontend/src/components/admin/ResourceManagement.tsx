import { useSearchParams } from "react-router-dom";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus, ListPlus, Search, Tag, Rss, RefreshCcw, Link as LinkIcon, RadioReceiver, Power, Edit } from "lucide-react";

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
import { Checkbox } from "@/components/ui/checkbox";
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

interface KeywordSuggestion {
  text: string;
  canonical_name: string;
  aliases: string[];
  groups: string[];
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

export default function ResourceManagement({ section }: { section?: "keywords" | "rss" }) {
  const queryClient = useQueryClient();
  const [params,setParams]=useSearchParams();
  const updateSearch=(key:string,value:string)=>setParams(current=>{if(value)current.set(key,value);else current.delete(key);return current;},{replace:true});

  // Keyword states
  const [newKeyword, setNewKeyword] = useState("");
  const kwSearch=params.get("keyword_search") ?? "";
  const setKwSearch=(value:string)=>updateSearch("keyword_search",value);
  const [isEditKwModalOpen, setIsEditKwModalOpen] = useState(false);
  const [editKwItem, setEditKwItem] = useState<KeywordModel | null>(null);
  const [editKwText, setEditKwText] = useState("");
  const [deleteKwItem, setDeleteKwItem] = useState<KeywordModel | null>(null);
  const [suggestionsOpen, setSuggestionsOpen] = useState(false);
  const [selectedSuggestions, setSelectedSuggestions] = useState<string[]>([]);

  // RSS states
  const [newRssUrl, setNewRssUrl] = useState("");
  const [newRssLabel, setNewRssLabel] = useState("");
  const [newRssCategory, setNewRssCategory] = useState("the-gioi");
  const rssSearch=params.get("rss_search") ?? "";
  const setRssSearch=(value:string)=>updateSearch("rss_search",value);

  // Fetch Keywords
  const { data: keywords = [], isLoading: loadKw, error: kwError, refetch: refetchKw } = useQuery<KeywordModel[]>({
    queryKey: ["admin_keywords"],
    enabled: section !== "rss",
    queryFn: async () => {
      const res = await fetch("/api/keywords?limit=1000&only_active=false", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed to fetch keywords");
      return res.json();
    },
  });

  // Fetch RSS Sources
  const { data: rssSources = [], isLoading: loadRss, error: rssError, refetch: refetchRss } = useQuery<RssSourceModel[]>({
    queryKey: ["admin_rss"],
    enabled: section !== "keywords",
    queryFn: async () => {
      const res = await fetch("/api/rss-sources", { headers: authHeaders() });
      if (!res.ok) throw new Error("Failed to fetch RSS sources");
      return res.json();
    },
  });

  // ============ KEYWORD MUTATIONS ============
  const refreshKeywords = () => {
    void queryClient.invalidateQueries({ queryKey: ["admin_keywords"] });
    void queryClient.invalidateQueries({ queryKey: ["keyword_suggestions"] });
    void queryClient.invalidateQueries({ queryKey: ["disease-cause-breakdown"] });
  };

  const { data: suggestions = [], isLoading: loadingSuggestions, error: suggestionsError, refetch: refetchSuggestions } = useQuery<KeywordSuggestion[]>({
    queryKey: ["keyword_suggestions"],
    enabled: suggestionsOpen,
    queryFn: async () => {
      const response = await fetch("/api/keywords/suggestions", { headers: authHeaders() });
      if (!response.ok) throw new Error("Không tải được từ khóa gợi ý");
      return response.json();
    },
  });

  const importSuggestions = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/keywords/import-suggestions", {
        method: "POST", headers: authHeaders(), body: JSON.stringify({ keywords: selectedSuggestions }),
      });
      if (!response.ok) {
        const body = await response.json();
        throw new Error(body.detail || "Không thể bổ sung từ khóa");
      }
      return response.json() as Promise<{ added_count: number; skipped_count: number }>;
    },
    onSuccess: (result) => {
      refreshKeywords();
      setSelectedSuggestions([]);
      setSuggestionsOpen(false);
      toast.success(`Đã thêm ${result.added_count} từ khóa; giữ nguyên các mục đã có`);
    },
    onError: (error) => toast.error(error.message),
  });

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
      refreshKeywords();
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
      setDeleteKwItem(null);
      refreshKeywords();
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
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Cập nhật thất bại");
      }
      return res.json();
    },
    onSuccess: () => {
      setIsEditKwModalOpen(false);
      refreshKeywords();
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
      refreshKeywords();
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
    <div className={section ? "space-y-6" : "grid grid-cols-1 lg:grid-cols-2 gap-6"}>
      {(kwError || rssError) && <div role="alert" className="text-destructive">{kwError?.message || rssError?.message}<Button variant="outline" onClick={()=>{if(section!=="rss")void refetchKw();if(section!=="keywords")void refetchRss();}}>Thử lại</Button></div>}
      {/* ---------------- KEYWORD BLOCK ---------------- */}
      {section !== "rss" && <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Tag className="h-5 w-5 text-primary" />
            <CardTitle>Từ Khóa Giám Sát</CardTitle>
          </div>
          <CardDescription>
            Thêm, sửa, bật/tắt hoặc bỏ từ khóa ngay tại đây. Tắt để dừng giám sát và giữ nguyên danh mục.
            Những thay đổi của bạn được lưu lại sau khi khởi động lại hệ thống.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-5">
          <form onSubmit={handleAddKeyword} className="space-y-3 rounded-lg border bg-muted/20 p-4 sm:p-5">
            <div>
              <Label htmlFor="new-monitoring-keyword" className="text-sm font-semibold">Thêm từ khóa mới</Label>
              <p className="mt-1 text-sm text-muted-foreground">Nhập một từ khóa rồi bấm nút để thêm vào danh sách giám sát.</p>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <Input
                id="new-monitoring-keyword"
                placeholder="Ví dụ: Cúm gia cầm, Cúm A/H5N1, Bạch hầu..."
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                disabled={createKwMutation.isPending}
                className="min-w-0 flex-1 bg-background"
              />
              <Button type="submit" disabled={createKwMutation.isPending || !newKeyword.trim()} className="whitespace-nowrap sm:min-w-36">
                {createKwMutation.isPending ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />} Thêm từ khóa
              </Button>
            </div>
          </form>

          <div className="space-y-3 border-b pb-5">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold">Danh sách từ khóa</h3>
                <p className="mt-1 text-sm text-muted-foreground">Tìm từ khóa hiện có hoặc mở danh mục gợi ý.</p>
              </div>
              <Badge variant="secondary" className="whitespace-nowrap">Tổng {keywords.length} · Đang bật {kwActiveCount}</Badge>
            </div>
            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative min-w-0 flex-1">
                <Search aria-hidden="true" className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Tìm trong danh sách từ khóa..."
                  value={kwSearch}
                  onChange={(e) => setKwSearch(e.target.value)}
                  aria-label="Tìm trong danh sách từ khóa"
                  className="bg-background pl-9"
                />
              </div>
              <Button type="button" variant="outline" className="whitespace-nowrap" onClick={() => { setSelectedSuggestions([]); setSuggestionsOpen(true); }}>
                <ListPlus className="mr-2 h-4 w-4" />Từ khóa gợi ý
              </Button>
            </div>
          </div>

          <div className="rounded-md border border-border/50 overflow-auto max-h-[65svh]">
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
                          aria-label={`Giám sát ${kw.text}`}
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
                            aria-label={`Sửa ${kw.text}`}
                            variant="ghost"
                            size="sm"
                            onClick={() => openEditKwModal(kw)}
                            className="hover:text-blue-700 hover:bg-blue-200"
                          >
                            <Edit className="h-4 w-4" />
                          </Button>
                          <Button
                            aria-label={`Bỏ ${kw.text}`}
                            variant="ghost"
                            size="sm"
                            onClick={() => setDeleteKwItem(kw)}
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
          </div>
        </CardContent>
      </Card>}

      <Dialog open={suggestionsOpen} onOpenChange={(open) => { if (!importSuggestions.isPending) setSuggestionsOpen(open); }}>
        <DialogContent className="max-w-2xl max-h-[85svh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Bổ sung từ khóa giám sát</DialogTitle>
            <DialogDescription>
              Chỉ thêm những mục bạn chọn. Các từ khóa cũ và mục đã tắt được giữ nguyên.
              Tên đồng nghĩa được tính chung một bệnh; phân týp khác nhau được thống kê riêng.
            </DialogDescription>
          </DialogHeader>
          {loadingSuggestions ? <p>Đang tải danh mục...</p> : suggestionsError ? (
            <div role="alert">{suggestionsError.message} <Button variant="outline" onClick={() => void refetchSuggestions()}>Thử lại</Button></div>
          ) : suggestions.length ? <div className="space-y-4">
            <Button variant="outline" onClick={() => setSelectedSuggestions(selectedSuggestions.length === suggestions.length ? [] : suggestions.map(item => item.text))}>
              {selectedSuggestions.length === suggestions.length ? "Bỏ chọn tất cả" : "Chọn tất cả"}
            </Button>
            {suggestions.map((item) => <label key={item.text} className="flex gap-3 rounded-md border p-3 cursor-pointer">
              <Checkbox aria-label={`Thêm ${item.text}`} checked={selectedSuggestions.includes(item.text)} disabled={importSuggestions.isPending}
                onCheckedChange={(checked) => setSelectedSuggestions(current => checked === true ? [...new Set([...current, item.text])] : current.filter(text => text !== item.text))} />
              <div className="space-y-1 text-sm">
                <p className="font-medium">{item.text} {item.groups.map(group => <Badge key={group} variant="secondary" className="ml-1">{group}</Badge>)}</p>
                <p className="text-muted-foreground">Tên thống kê: {item.canonical_name}</p>
                <p className="text-muted-foreground">Tên đồng nghĩa: {item.aliases.join(", ")}</p>
              </div>
            </label>)}
          </div> : <p>Danh mục hiện đã có đầy đủ các bệnh được gợi ý. Bạn vẫn có thể thêm từ khóa khác bằng ô nhập trên trang.</p>}
          <DialogFooter>
            <Button variant="outline" disabled={importSuggestions.isPending} onClick={() => setSuggestionsOpen(false)}>Đóng</Button>
            <Button disabled={!selectedSuggestions.length || importSuggestions.isPending || !!suggestionsError} onClick={() => importSuggestions.mutate()}>
              {importSuggestions.isPending ? "Đang lưu..." : `Thêm ${selectedSuggestions.length} mục đã chọn`}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={deleteKwItem !== null} onOpenChange={(open) => { if (!open && !deleteKwMutation.isPending) setDeleteKwItem(null); }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bỏ từ khóa khỏi danh mục?</DialogTitle>
            <DialogDescription>
              Bỏ “{deleteKwItem?.text}” khỏi danh mục quét. Bài báo và số liệu lịch sử vẫn được giữ nguyên.
              Bạn có thể dùng công tắc tắt nếu chỉ muốn tạm dừng giám sát.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" disabled={deleteKwMutation.isPending} onClick={() => setDeleteKwItem(null)}>Hủy</Button>
            <Button variant="destructive" disabled={deleteKwMutation.isPending} onClick={() => { if (deleteKwItem) deleteKwMutation.mutate(deleteKwItem.id); }}>
              {deleteKwMutation.isPending ? "Đang bỏ..." : "Bỏ từ khóa"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* ---------------- RSS SOURCE BLOCK ---------------- */}
      {section !== "keywords" && <Card className="shadow-sm border-border/50">
        <CardHeader>
          <div className="flex items-center gap-2">
            <Rss className="h-5 w-5 text-primary" />
            <CardTitle>Nguồn RSS Whitelist</CardTitle>
          </div>
          <CardDescription>Các nguồn tin được tin tưởng để lấy dữ liệu tự động.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleAddRss} className="space-y-3 mb-6 p-4 rounded-lg border bg-muted/20">
            <div className="grid gap-3 sm:grid-cols-2">
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
            <div className="flex flex-wrap items-end gap-3">
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

          <div className="rounded-md border border-border/50 overflow-auto max-h-[65svh]">
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
      </Card>}

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
