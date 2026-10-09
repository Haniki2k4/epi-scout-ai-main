import { useSearchParams } from "react-router-dom";
import { Input } from "@/components/ui/input";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { useState, useEffect } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  FileText, Trash2, RefreshCcw, ExternalLink,
  ChevronLeft, ChevronRight,
} from "lucide-react";
import { format } from "date-fns";
import { vi } from "date-fns/locale";

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
import { Badge } from "@/components/ui/badge";

// Types
interface ArticleModel {
  id: number;
  title: string;
  link: string;
  published_date: string;
  source: string;
  keywords_matched: string;
  event_match_score: number | null;
  dedupe_reason: string | null;
  llm_label?: string | null;
  human_label?: string | null;
  details?: {
    summary?: string;
  };
}

interface PaginatedArticles {
  items: ArticleModel[];
  total: number;
  skip: number;
  limit: number;
}

const labelBadge = (label: string | null | undefined) => {
  if (!label) return null;
  const colors: Record<string, string> = {
    relevant: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400",
    noise: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400",
    irrelevant: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-400",
    unsure: "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400",
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${colors[label] || "bg-slate-100 text-slate-700"}`}>
      {label}
    </span>
  );
};

export default function ArticleManagement() {
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const keyword = params.get("keyword") ?? "";
  const includeExcluded = params.get("include_excluded") === "true";
  const [search, setSearch] = useState(keyword);
  useEffect(() => setSearch(keyword), [keyword]);
  const [selected, setSelected] = useState<ArticleModel | null>(null);
  const setPage = (update: (page: number) => number) => setParams(current => {current.set("page", String(update(page)));return current;});
  const LIMIT = 8;

  // Fetch Articles with labels — dùng API lẻ nhẹ hơn thay vì page-data gộp
  const { data: articlesData, isLoading, error, refetch } = useQuery<PaginatedArticles>({
    queryKey: ["admin_articles", page, keyword, includeExcluded],
    queryFn: async () => {
      const res = await fetch(`/api/articles?skip=${(page - 1) * LIMIT}&limit=${LIMIT}&include_label=true&keyword=${encodeURIComponent(keyword)}&include_excluded=${includeExcluded}`);
      if (!res.ok) throw new Error("Failed to fetch articles");
      return res.json();
    },
    placeholderData: (prev) => prev,
  });

  const articles = articlesData?.items || [];
  const total = articlesData?.total || 0;
  const totalPages = Math.ceil(total / LIMIT);

  // Delete Mutation
  const deleteArticleMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/articles/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Xóa bài báo thất bại");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_articles"] });
      queryClient.invalidateQueries({ queryKey: ["page-data"] }); // Sync với trang tin tức
      setSelected(null);
      toast.success("Đã xóa bài báo thành công");
    },
    onError: (e) => toast.error(e.message),
  });

  const handleDelete = (id: number) => {
    if (window.confirm("Cảnh báo: Việc xóa bài báo này sẽ làm mất vĩnh viễn dữ liệu liên quan như thống kê biểu đồ, dữ liệu gán nhãn LLM.\n\nBạn có chắc chắn muốn xóa bài báo này khỏi hệ thống không?")) {
      deleteArticleMutation.mutate(id);
    }
  };

  return (
    <Card className="shadow-sm border-border/50">
      <CardHeader>
        <div>
          <CardTitle>Danh sách Bài báo đã lưu</CardTitle>
          <CardDescription>
            Quản lý toàn bộ dữ liệu tin tức được thu thập bởi hệ thống ({total} bài báo)
          </CardDescription>
        </div>
      </CardHeader>

      <CardContent>
        <form className="mb-4 flex flex-wrap items-end gap-3" onSubmit={event=>{event.preventDefault();setParams(current=>{current.set("keyword",search.trim());current.delete("page");return current;});}}>
          <label className="flex-1 min-w-0 space-y-1 text-sm">Tìm theo từ khóa bệnh<Input value={search} onChange={event=>setSearch(event.target.value)} placeholder="Nhập từ khóa bệnh"/></label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={includeExcluded} onChange={event=>setParams(current=>{current.set("include_excluded",String(event.target.checked));current.delete("page");return current;})}/>Bao gồm bài đã loại</label>
          <Button type="submit">Tìm kiếm</Button>
        </form>
        {error && <div role="alert" className="mb-4 text-destructive">{error.message}<Button variant="outline" onClick={()=>refetch()}>Thử lại</Button></div>}

        <div className="rounded-md border border-border/50 overflow-x-auto">
          {isLoading ? (
            <div className="flex justify-center p-12">
              <RefreshCcw className="h-8 w-8 animate-spin text-primary" />
            </div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead className="w-[35%]">Tiêu đề / Trích đoạn</TableHead>
                  <TableHead>Nguồn / Thời gian</TableHead>
                  <TableHead>Từ khóa</TableHead>
                  <TableHead>Nhãn</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {articles.map((article) => (
                  <TableRow key={article.id}>
                    <TableCell>
                      <div className="font-semibold text-sm leading-tight mb-1 flex items-start gap-1">
                        <FileText className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <a
                          href={article.link}
                          target="_blank"
                          rel="noreferrer"
                          className="hover:underline hover:text-primary transition-colors text-foreground"
                        >
                          {article.title}
                        </a>
                      </div>
                      <p className="text-xs text-muted-foreground line-clamp-2 pl-5">
                        {article.details?.summary || "Không có trích đoạn"}
                      </p>
                    </TableCell>
                    <TableCell className="text-sm">
                      <div className="flex flex-col gap-1">
                        <Badge variant="outline" className="bg-muted/40 font-normal w-fit">
                          {article.source || "Không rõ"}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {article.published_date
                            ? format(new Date(article.published_date), "dd/MM/yyyy HH:mm", { locale: vi })
                            : "N/A"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-[160px]">
                        {article.keywords_matched ? (
                          article.keywords_matched.split(",").map((kw, idx) => (
                            <Badge
                              key={idx}
                              variant="secondary"
                              className="text-xs bg-primary/10 text-primary hover:bg-primary/20"
                            >
                              {kw.trim()}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-col gap-1.5 min-w-[110px]">
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">LLM:</span>
                          {labelBadge(article.llm_label)}
                        </div>
                        <div className="flex items-center gap-1">
                          <span className="text-xs text-muted-foreground">Xác nhận:</span>
                          {article.human_label ? (
                            labelBadge(article.human_label)
                          ) : (
                            <span className="text-xs text-muted-foreground">-</span>
                          )}
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          asChild
                          className="hover:text-blue-700 hover:bg-blue-200"
                        >
                          <a href={article.link} target="_blank" rel="noreferrer" title="Website gốc">
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          onClick={() => setSelected(article)}
                          aria-label="Xem chi tiết bài báo"
                          disabled={deleteArticleMutation.isPending}
                        >
                          <FileText className="h-4 w-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
                {articles.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      Không tìm thấy bài báo nào
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          )}
        </div>

        {/* Pagination */}
        {!isLoading && totalPages > 1 && (
          <div className="mt-4 flex items-center justify-end gap-2">
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => Math.max(1, current - 1))}
              disabled={page === 1}
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              Trước
            </Button>
            <div className="text-sm text-muted-foreground">
              Trang {page} / {totalPages}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              disabled={page >= totalPages}
            >
              Sau
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        )}
        <Sheet open={selected !== null} onOpenChange={open=>{if(!open)setSelected(null);}}><SheetContent className="w-full overflow-y-auto sm:max-w-xl"><SheetHeader><SheetTitle>{selected?.title}</SheetTitle><SheetDescription>Chi tiết bài báo đã lưu</SheetDescription></SheetHeader>{selected&&<div className="mt-6 space-y-4 text-sm"><p>{selected.source} · {selected.published_date ? new Date(selected.published_date).toLocaleString("vi-VN") : "Chưa có ngày"}</p><p>{selected.details?.summary || "Chưa có trích đoạn"}</p><p>Từ khóa: {selected.keywords_matched || "Chưa có"}</p><p>Nhãn LLM: {selected.llm_label || "Chưa có"}</p><p>Nhãn người duyệt: {selected.human_label || "Chưa có"}</p><div className="flex flex-wrap gap-2"><Button asChild><a href={selected.link} target="_blank" rel="noreferrer">Mở bài gốc</a></Button><Button variant="destructive" disabled={deleteArticleMutation.isPending} onClick={()=>handleDelete(selected.id)}>Xóa bài báo</Button></div></div>}</SheetContent></Sheet>
      </CardContent>
    </Card>
  );
}
