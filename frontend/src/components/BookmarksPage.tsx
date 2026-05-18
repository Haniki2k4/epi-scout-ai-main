import { useEffect, useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Bookmark, BookmarkX, ExternalLink, ChevronLeft, ChevronRight, Loader2 } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Article } from "@/types";
import { isDomestic } from "@/lib/utils";
import { useAuth } from "@/contexts/AuthContext";

const PAGE_SIZE = 10;

const BookmarksPage = () => {
  const { toast } = useToast();
  const { isGuest } = useAuth();
  const [bookmarks, setBookmarks] = useState<Article[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);

  const fetchBookmarks = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/bookmarks");
      if (res.ok) {
        const data = await res.json();
        setBookmarks(data);
      } else if (res.status === 401) {
        toast({ title: "Chưa đăng nhập", description: "Vui lòng đăng nhập để xem danh sách bookmark.", variant: "destructive" });
      }
    } catch {
      toast({ title: "Lỗi", description: "Không thể tải danh sách bookmark.", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (isGuest) {
      setLoading(false);
      return;
    }
    fetchBookmarks();
  }, [isGuest]);

  const handleRemove = async (articleId: number) => {
    try {
      const res = await fetch(`/api/bookmarks/${articleId}`, { method: "DELETE" });
      if (res.ok) {
        setBookmarks(prev => prev.filter(a => a.id !== articleId));
        toast({ title: "Đã xóa bookmark" });
      }
    } catch {
      toast({ title: "Lỗi", description: "Không thể xóa bookmark.", variant: "destructive" });
    }
  };

  const totalPages = Math.max(1, Math.ceil(bookmarks.length / PAGE_SIZE));
  const paginated = bookmarks.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <div className="h-10 w-10 rounded-lg bg-primary/10 flex items-center justify-center">
          <Bookmark className="h-5 w-5 text-primary" />
        </div>
        <div>
          <h2 className="text-xl font-bold text-foreground">Bookmark đã lưu</h2>
          <p className="text-sm text-muted-foreground">Danh sách bài viết bạn đã đánh dấu để đọc sau</p>
        </div>
      </div>

      {isGuest ? (
        <Card>
          <CardContent className="flex flex-col items-center justify-center gap-3 py-12 text-center">
            <Bookmark className="h-12 w-12 text-muted-foreground/30" />
            <div>
              <h3 className="font-semibold text-foreground">Vui long dang nhap de luu bai bao</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Che do khach co the xem toan bo danh sach bai bao, nhung can dang nhap de tao va quan ly bookmark.
              </p>
            </div>
          </CardContent>
        </Card>
      ) : (

      <Card>
        <CardHeader className="pb-3">
          <div className="flex items-center justify-between">
            <CardTitle>Bài viết đã lưu</CardTitle>
            <Badge variant="secondary">{bookmarks.length} bài</Badge>
          </div>
          <CardDescription>Nhấn nút xóa để bỏ đánh dấu bài viết</CardDescription>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="flex items-center justify-center h-48 text-muted-foreground gap-2">
              <Loader2 className="h-5 w-5 animate-spin" />
              <span>Đang tải...</span>
            </div>
          ) : bookmarks.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-48 text-muted-foreground gap-3">
              <Bookmark className="h-12 w-12 opacity-20" />
              <p className="text-sm">Chưa có bài viết nào được bookmark.</p>
              <p className="text-xs">Hãy vào tab <strong>Quét từ khóa</strong> và nhấn icon bookmark trên mỗi bài viết.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {paginated.map((article) => (
                <div
                  key={article.id}
                  className="flex items-start justify-between gap-4 p-4 border border-border rounded-lg hover:bg-secondary/40 transition-colors"
                >
                  <div className="flex-1 min-w-0 space-y-1">
                    <a
                      href={article.link}
                      target="_blank"
                      rel="noreferrer"
                      className="font-medium text-foreground hover:text-primary hover:underline flex items-center gap-1 line-clamp-2"
                    >
                      {article.title}
                      <ExternalLink className="h-3 w-3 shrink-0 opacity-60" />
                    </a>
                    <div className="text-sm text-muted-foreground flex flex-wrap gap-2 items-center">
                      <span className="font-medium text-foreground">{article.source || "Nguồn không xác định"}</span>
                      <span>•</span>
                      <span>{new Date(article.published_date).toLocaleDateString("vi-VN")}</span>
                      <span>•</span>
                      {isDomestic(article.link, article.source) ? (
                        <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-200 bg-blue-50/50">Trong nước</Badge>
                      ) : (
                        <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-200 bg-emerald-50/50">Quốc tế</Badge>
                      )}
                    </div>
                    {article.keywords_matched && (
                      <div className="flex flex-wrap gap-1 pt-1">
                        {article.keywords_matched.split(",").filter(Boolean).map((kw, i) => (
                          <Badge key={i} variant="outline" className="text-xs py-0">
                            {kw.trim()}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => article.id && handleRemove(article.id)}
                    className="text-muted-foreground hover:text-destructive shrink-0"
                    title="Xóa bookmark"
                  >
                    <BookmarkX className="h-5 w-5" />
                  </Button>
                </div>
              ))}

              {bookmarks.length > PAGE_SIZE && (
                <div className="flex items-center justify-end gap-2 pt-2">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.max(1, p - 1))}
                    disabled={page === 1}
                  >
                    <ChevronLeft className="h-4 w-4 mr-1" /> Trước
                  </Button>
                  <span className="text-sm text-muted-foreground">
                    Trang {page} / {totalPages}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setPage(p => Math.min(totalPages, p + 1))}
                    disabled={page === totalPages}
                  >
                    Sau <ChevronRight className="h-4 w-4 ml-1" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
      )}
    </div>
  );
};

export default BookmarksPage;
