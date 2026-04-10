import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, Trash2, ArrowUpRight, RefreshCcw, ExternalLink, ChevronLeft, ChevronRight } from "lucide-react";
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
  details?: {
    summary?: string;
  };
}

export default function ArticleManagement() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const LIMIT = 8;

  // Fetch Articles
  const { data: articles = [], isLoading } = useQuery<ArticleModel[]>({
    queryKey: ["admin_articles", page],
    queryFn: async () => {
      const res = await fetch(`/api/articles?skip=${(page - 1) * LIMIT}&limit=${LIMIT}`);
      if (!res.ok) throw new Error("Failed to fetch articles");
      return res.json();
    },
  });

  // Delete Mutation
  const deleteArticleMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`/api/articles/${id}`, { method: "DELETE" });
      if (!res.ok) throw new Error("Xóa bài báo thất bại");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["admin_articles"] });
      toast.success("Đã xóa bài báo thành công");
    },
    onError: (e) => toast.error(e.message),
  });

  const handleDelete = (id: number) => {
    if (window.confirm("Bạn có chắc muốn xóa bài báo này khỏi cơ sở dữ liệu không?")) {
      deleteArticleMutation.mutate(id);
    }
  };

  return (
    <Card className="shadow-sm border-border/50">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Danh sách Bài báo đã lưu</CardTitle>
          <CardDescription>Quản lý toàn bộ dữ liệu tin tức được thu thập bởi hệ thống</CardDescription>
        </div>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-border/50 overflow-hidden">
          {isLoading ? (
            <div className="flex justify-center p-12"><RefreshCcw className="h-8 w-8 animate-spin text-primary" /></div>
          ) : (
            <Table>
              <TableHeader className="bg-muted/50">
                <TableRow>
                  <TableHead className="w-[50%]">Tiêu đề / Trích đoạn</TableHead>
                  <TableHead>Nguồn / Thời gian</TableHead>
                  <TableHead>Từ khóa (Keywords)</TableHead>
                  <TableHead className="text-right">Thao tác</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {articles.map((article) => (
                  <TableRow key={article.id}>
                    <TableCell>
                      <div className="font-semibold text-sm leading-tight mb-1 flex items-start gap-1">
                        <FileText className="h-4 w-4 text-primary shrink-0 mt-0.5" />
                        <a href={article.link} target="_blank" rel="noreferrer" className="hover:underline hover:text-primary transition-colors text-foreground">
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
                          {article.source || 'Không rõ'}
                        </Badge>
                        <span className="text-xs text-muted-foreground">
                          {article.published_date ? format(new Date(article.published_date), "dd/MM/yyyy HH:mm", { locale: vi }) : "N/A"}
                        </span>
                      </div>
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-[200px]">
                        {article.keywords_matched ? (
                          article.keywords_matched.split(',').map((kw, idx) => (
                            <Badge key={idx} variant="secondary" className="text-[10px] bg-primary/10 text-primary hover:bg-primary/20">
                              {kw.trim()}
                            </Badge>
                          ))
                        ) : (
                          <span className="text-xs text-muted-foreground">-</span>
                        )}
                      </div>
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" asChild className="hover:text-blue-700 hover:bg-blue-200">
                          <a href={article.link} target="_blank" rel="noreferrer" title="Website gốc">
                            <ExternalLink className="h-4 w-4" />
                          </a>
                        </Button>
                        <Button 
                          variant="ghost" 
                          size="icon" 
                          onClick={() => handleDelete(article.id)}
                          className="hover:bg-destructive/10 hover:text-destructive text-destructive"
                          disabled={deleteArticleMutation.isPending}
                        >
                          <Trash2 className="h-4 w-4" />
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
        
        {/* Pagination Panel */}
        {!isLoading && (
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
              Trang {page}
            </div>
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={() => setPage((current) => current + 1)}
              disabled={articles.length < LIMIT}
            >
              Sau
              <ChevronRight className="ml-1 h-4 w-4" />
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
