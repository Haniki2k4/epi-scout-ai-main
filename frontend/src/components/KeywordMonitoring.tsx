import { useState, useEffect, useRef, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Plus, X, Play, Pause, Download, Settings, Trash2, CheckSquare, Square, ChevronLeft, ChevronRight, Bookmark, BookmarkCheck, Check, ChevronsUpDown } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { cn, isDomestic } from "@/lib/utils";
import { Article, Keyword, NewsEvent, NewsEventDetail } from "@/types";

const SCAN_STATE_KEY = "epi_scout_scan_state";

const severityConfig: Record<string, { color: string; label: string }> = {
  critical: { color: "bg-red-100 text-red-700 border-red-200 dark:bg-red-950 dark:text-red-300 dark:border-red-800", label: "Nguy kịch" },
  high: { color: "bg-orange-100 text-orange-700 border-orange-200 dark:bg-orange-950 dark:text-orange-300 dark:border-orange-800", label: "Cao" },
  medium: { color: "bg-yellow-100 text-yellow-700 border-yellow-200 dark:bg-yellow-950 dark:text-yellow-300 dark:border-yellow-800", label: "Trung bình" },
  low: { color: "bg-slate-100 text-slate-600 border-slate-200 dark:bg-slate-800 dark:text-slate-400 dark:border-slate-700", label: "Thấp" },
};

// ── Fetch helper ──────────────────────────────────────────────────────────────

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

const KeywordMonitoring = () => {
  const { toast } = useToast();
  const [keywordFilter, setKeywordFilter] = useState("");
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<number[]>([]);

  // Keyword Edit State
  const [editingKeyword, setEditingKeyword] = useState<Keyword | null>(null);
  const [editKeywordText, setEditKeywordText] = useState("");
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  const [selectedEvent, setSelectedEvent] = useState<NewsEventDetail | null>(null);
  const [eventDialogOpen, setEventDialogOpen] = useState(false);
  const [loadingEventId, setLoadingEventId] = useState<number | null>(null);
  const [articleSearch, setArticleSearch] = useState("");
  const [articleSourceFilter, setArticleSourceFilter] = useState("all");
  const [articleKeywordFilter, setArticleKeywordFilter] = useState("all");
  const [articleTrustFilter, setArticleTrustFilter] = useState("all");
  const [articleSort, setArticleSort] = useState("newest");
  const [articlePage, setArticlePage] = useState(1);
  const articlePageSize = 20;
  const [eventPage, setEventPage] = useState(1);
  const eventPageSize = 20;

  // Combobox state
  const [keywordOpen, setKeywordOpen] = useState(false);

  // Bookmarks
  const [bookmarkedArticleIds, setBookmarkedArticleIds] = useState<Set<number>>(new Set());

  // Tooltip State
  const [hoveredArticleId, setHoveredArticleId] = useState<number | null>(null);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Queries (cached by TanStack Query) ─────────────────────────────────────

  const { data: rssSources = [] } = useQuery({
    queryKey: ['rss-sources'],
    queryFn: () => fetchJson<any[]>('/api/rss-sources'),
  });
  const rssSourceCount = useMemo(
    () => rssSources.filter((s: any) => s.is_active !== false).length,
    [rssSources]
  );

  const { data: activeKeywords = [] } = useQuery({
    queryKey: ['keywords'],
    queryFn: () => fetchJson<Keyword[]>('/api/keywords'),
  });

  // Server-side phân trang: chỉ tải articlePageSize bài mỗi lần
  const articleSkip = (articlePage - 1) * articlePageSize;
  const { data: articlesData } = useQuery({
    queryKey: ['articles', articlePage, articlePageSize],
    queryFn: () => fetchJson<{ items: Article[]; total: number }>(
      `/api/articles?skip=${articleSkip}&limit=${articlePageSize}&include_label=true`
    ),
    placeholderData: (prev) => prev, // Giữ data cũ khi chuyển trang (smooth UX)
  });
  const articles = articlesData?.items ?? [];
  const totalArticleCount = articlesData?.total ?? 0;

  const { data: events = [] } = useQuery({
    queryKey: ['events'],
    queryFn: () => fetchJson<NewsEvent[]>('/api/events?limit=20'),
  });





  const handleToggleBookmark = async (articleId: number) => {
    if (!articleId) return;

    const isBookmarked = bookmarkedArticleIds.has(articleId);
    try {
      const method = isBookmarked ? "DELETE" : "POST";
      const res = await fetch(`/api/bookmarks/${articleId}`, { method });

      if (res.ok) {
        setBookmarkedArticleIds(prev => {
          const next = new Set(prev);
          if (isBookmarked) {
            next.delete(articleId);
            toast({ title: "Đã hủy lưu", description: "Đã xóa bài viết khỏi danh sách xem sau." });
          } else {
            next.add(articleId);
            toast({ title: "Đã lưu", description: "Đã thêm bài viết vào danh sách xem sau." });
          }
          return next;
        });
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể thay đổi trạng thái bookmark.", variant: "destructive" });
    }
  };

  const filteredKeywords = activeKeywords.filter((keyword) =>
    keyword.text.toLowerCase().includes(keywordFilter.trim().toLowerCase())
  );

  const filteredKeywordIds = filteredKeywords
    .map((keyword) => keyword.id)
    .filter((id): id is number => id !== undefined);

  const allFilteredSelected =
    filteredKeywordIds.length > 0 && filteredKeywordIds.every((id) => selectedKeywordIds.includes(id));

  const handleOpenEvent = async (eventId: number) => {
    try {
      setLoadingEventId(eventId);
      const res = await fetch(`/api/events/${eventId}`);
      if (res.ok) {
        const data = await res.json();
        setSelectedEvent(data);
        setEventDialogOpen(true);
      } else {
        toast({
          title: "Không tải được sự kiện",
          description: "Chi tiết sự kiện hiện không khả dụng.",
          variant: "destructive",
        });
      }
    } catch (e) {
      toast({
        title: "Lỗi",
        description: "Không thể tải chi tiết sự kiện.",
        variant: "destructive",
      });
    } finally {
      setLoadingEventId(null);
    }
  };

  const articleSources = useMemo(() => Array.from(
    new Set(articles.map((article) => article.source).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b, "vi")), [articles]);

  const articleKeywords = useMemo(() => Array.from(
    new Set(
      articles.flatMap((article) =>
        (article.keywords_matched || "")
          .split(",")
          .map((keyword) => keyword.trim())
          .filter(Boolean)
      )
    )
  ).sort((a, b) => a.localeCompare(b, "vi")), [articles]);

  // Server-side phân trang: articles đã được phân trang từ server
  // Lọc client-side chỉ áp dụng trên trang hiện tại
  const filteredArticles = useMemo(() => [...articles]
    .filter((article) => {
      const normalizedSearch = articleSearch.trim().toLowerCase();
      if (!normalizedSearch) {
        return true;
      }

      const haystack = [
        article.title,
        article.source,
        article.summary,
        article.keywords_matched,
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase();

      return haystack.includes(normalizedSearch);
    })
    .filter((article) => articleSourceFilter === "all" || article.source === articleSourceFilter)
    .filter((article) => {
      if (articleKeywordFilter === "all") {
        return true;
      }

      const articleKeywordList = (article.keywords_matched || "")
        .split(",")
        .map((keyword) => keyword.trim().toLowerCase());
      return articleKeywordList.includes(articleKeywordFilter.toLowerCase());
    })
    .filter((article) => {
      if (articleTrustFilter === "trusted") {
        return article.is_whitelisted;
      }
      if (articleTrustFilter === "manual") {
        return !article.is_whitelisted;
      }
      return true;
    })
    .filter((article) => {
      const hl = article.human_label;
      return hl !== "noise" && hl !== "irrelevant";
    })
    .sort((a, b) => {
      const dateA = new Date(a.published_date).getTime();
      const dateB = new Date(b.published_date).getTime();

      if (articleSort === "oldest") {
        return dateA - dateB;
      }
      if (articleSort === "title-asc") {
        return a.title.localeCompare(b.title, "vi");
      }
      if (articleSort === "title-desc") {
        return b.title.localeCompare(a.title, "vi");
      }
      return dateB - dateA;
    }), [articles, articleSearch, articleSourceFilter, articleKeywordFilter, articleTrustFilter, articleSort]);

  // Server-side phân trang: tổng số trang tính từ total của server
  const totalArticlePages = Math.max(1, Math.ceil(totalArticleCount / articlePageSize));
  // Hiển thị trực tiếp filteredArticles vì server đã phân trang
  const paginatedArticles = filteredArticles;



  const totalEventPages = Math.max(1, Math.ceil(events.length / eventPageSize));
  const paginatedEvents = events.slice(
    (eventPage - 1) * eventPageSize,
    eventPage * eventPageSize
  );

  useEffect(() => {
    if (eventPage > totalEventPages) {
      setEventPage(totalEventPages);
    }
  }, [eventPage, totalEventPages]);

  // Tạo mảng số trang hiển thị (tối đa 7 nút)
  const getPageNumbers = (currentPage: number, totalPages: number): (number | '...')[] => {
    if (totalPages <= 7) return Array.from({ length: totalPages }, (_, i) => i + 1);
    const pages: (number | '...')[] = [];
    if (currentPage <= 4) {
      pages.push(1, 2, 3, 4, 5, '...', totalPages);
    } else if (currentPage >= totalPages - 3) {
      pages.push(1, '...', totalPages - 4, totalPages - 3, totalPages - 2, totalPages - 1, totalPages);
    } else {
      pages.push(1, '...', currentPage - 1, currentPage, currentPage + 1, '...', totalPages);
    }
    return pages;
  };

  return (
    <div className="space-y-6">


      <Dialog open={eventDialogOpen} onOpenChange={setEventDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-3xl overflow-hidden">
          <DialogHeader>
            <DialogTitle>{selectedEvent?.canonical_title || "Chi tiết sự kiện"}</DialogTitle>
            <DialogDescription>
              {selectedEvent?.disease_name}
              {selectedEvent?.location ? ` • ${selectedEvent.location}` : ""}
              {selectedEvent?.event_date ? ` • ${new Date(selectedEvent.event_date).toLocaleString()}` : ""}
              {selectedEvent?.severity && (
                <Badge className={`ml-2 text-[10px] px-1.5 py-0.5 border ${severityConfig[selectedEvent.severity]?.color || severityConfig.low.color}`}>
                  {severityConfig[selectedEvent.severity]?.label || selectedEvent.severity}
                </Badge>
              )}
            </DialogDescription>
          </DialogHeader>
          {selectedEvent && (
            <div className="flex flex-wrap gap-2 pb-2">
              <Badge variant="secondary">{selectedEvent.article_count} bài viết</Badge>
              <Badge variant="secondary">{selectedEvent.source_count} nguồn</Badge>
              {selectedEvent.sources_preview.map((source) => (
                <Badge key={source} variant="outline">{source}</Badge>
              ))}
            </div>
          )}
          <div className="space-y-3 overflow-y-auto pr-2">
            {selectedEvent?.articles.map((article) => (
              <div key={article.id || article.link} className="rounded-lg border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="space-y-1">
                    <a href={article.link} target="_blank" rel="noreferrer" className="font-medium hover:underline">
                      {article.title}
                    </a>
                    <div className="text-sm text-muted-foreground">
                      {article.source} • {new Date(article.published_date).toLocaleString()}
                    </div>
                  </div>
                  <Badge variant="outline">
                    {typeof article.event_match_score === "number" ? `score ${article.event_match_score.toFixed(2)}` : "new event"}
                  </Badge>
                </div>
                {article.dedupe_reason && (
                  <div className="mt-2 text-xs text-muted-foreground">
                    {article.dedupe_reason}
                  </div>
                )}
              </div>
            ))}
            {selectedEvent && selectedEvent.articles.length === 0 && (
              <div className="py-4 text-center text-sm text-muted-foreground">
                Sự kiện này chưa có bài viết nào.
              </div>
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Danh sách từ khóa giám sát (chỉ đọc) */}
      <Card>
        <CardHeader>
          <CardTitle>Từ khóa giám sát</CardTitle>
          <CardDescription>Danh sách các từ khóa hệ thống đang theo dõi. Liên hệ quản trị viên để thay đổi.</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            {activeKeywords.length === 0 ? (
              <div className="text-sm text-muted-foreground">Chưa có từ khóa nào.</div>
            ) : (
              activeKeywords.map((keyword) => (
                <Badge key={keyword.id} variant="secondary" className="px-3 py-1.5 text-sm">
                  {keyword.text}
                </Badge>
              ))
            )}
          </div>
          <div className="mt-3 text-xs text-muted-foreground">
            Tổng cộng {activeKeywords.length} từ khóa đang hoạt động.
          </div>
        </CardContent>
      </Card>

      {/* Recent Articles */}
      <Card>
        <CardHeader>
          <CardTitle>Tin tức đã lưu</CardTitle>
          <CardDescription>Danh sách bài viết trong cơ sở dữ liệu</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="mb-4 space-y-3">
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              <div className="relative md:col-span-2">
                <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  placeholder="Tìm theo tiêu đề, nguồn, keyword..."
                  value={articleSearch}
                  onChange={(e) => setArticleSearch(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={articleSourceFilter} onValueChange={setArticleSourceFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Lọc theo nguồn" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả nguồn</SelectItem>
                  {articleSources.map((source) => (
                    <SelectItem key={source} value={source}>
                      {source}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              
              <Popover open={keywordOpen} onOpenChange={setKeywordOpen}>
                <PopoverTrigger asChild>
                  <Button
                    variant="outline"
                    role="combobox"
                    aria-expanded={keywordOpen}
                    className="w-full justify-between font-normal text-muted-foreground"
                  >
                    {articleKeywordFilter === "all"
                      ? "Lọc theo keyword"
                      : articleKeywordFilter}
                    <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
                  </Button>
                </PopoverTrigger>
                <PopoverContent className="w-full p-0 min-w-[200px]">
                  <Command>
                    <CommandInput placeholder="Tìm kiếm keyword..." />
                    <CommandList>
                      <CommandEmpty>Không tìm thấy keyword.</CommandEmpty>
                      <CommandGroup>
                        <CommandItem
                          onSelect={() => {
                            setArticleKeywordFilter("all");
                            setKeywordOpen(false);
                          }}
                        >
                          <Check
                            className={cn(
                              "mr-2 h-4 w-4",
                              articleKeywordFilter === "all" ? "opacity-100" : "opacity-0"
                            )}
                          />
                          Tất cả keyword
                        </CommandItem>
                        {articleKeywords.map((keyword) => (
                          <CommandItem
                            key={keyword}
                            onSelect={() => {
                              setArticleKeywordFilter(keyword);
                              setKeywordOpen(false);
                            }}
                          >
                            <Check
                              className={cn(
                                "mr-2 h-4 w-4",
                                articleKeywordFilter === keyword ? "opacity-100" : "opacity-0"
                              )}
                            />
                            {keyword}
                          </CommandItem>
                        ))}
                      </CommandGroup>
                    </CommandList>
                  </Command>
                </PopoverContent>
              </Popover>
              <Select value={articleSort} onValueChange={setArticleSort}>
                <SelectTrigger>
                  <SelectValue placeholder="Sắp xếp" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="newest">Mới nhất</SelectItem>
                  <SelectItem value="oldest">Cũ nhất</SelectItem>
                  <SelectItem value="title-asc">Tiêu đề A-Z</SelectItem>
                  <SelectItem value="title-desc">Tiêu đề Z-A</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <div className="flex gap-2">
                <Button
                  type="button"
                  variant={articleTrustFilter === "all" ? "default" : "outline"}
                  onClick={() => setArticleTrustFilter("all")}
                >
                  Tất cả
                </Button>
                <Button
                  type="button"
                  variant={articleTrustFilter === "trusted" ? "default" : "outline"}
                  onClick={() => setArticleTrustFilter("trusted")}
                >
                  Uy tín
                </Button>
                <Button
                  type="button"
                  variant={articleTrustFilter === "manual" ? "default" : "outline"}
                  onClick={() => setArticleTrustFilter("manual")}
                >
                  Thủ công
                </Button>
              </div>
              <div className="text-sm text-muted-foreground flex items-center gap-2">
                <span>
                  Hiển thị {paginatedArticles.length}/{filteredArticles.length} bài viết (trang {articlePage}/{totalArticlePages})
                </span>
              </div>
            </div>
            <div className="space-y-4">
              {articles.length === 0 ? (
                <div className="text-center text-muted-foreground py-4">Chưa có bài viết nào.</div>
              ) : filteredArticles.length === 0 ? (
                <div className="text-center text-muted-foreground py-4">
                  Không có bài viết nào khớp với bộ lọc hiện tại.
                </div>
              ) : (
                paginatedArticles.map((article, index) => (
                  <div
                    key={article.id || index}
                    className="flex items-start justify-between p-4 border border-border rounded-lg hover:bg-secondary/50 transition-colors"
                  >
                    <div className="flex-1 space-y-2">
                      <div className="flex items-start gap-3">
                        <div className="flex-1">
                          <h4
                            className="font-medium text-foreground flex items-center flex-wrap gap-2 relative"
                            onMouseEnter={() => {
                              hoverTimerRef.current = setTimeout(() => {
                                setHoveredArticleId(article.id ?? index);
                              }, 1000);
                            }}
                            onMouseLeave={() => {
                              if (hoverTimerRef.current) clearTimeout(hoverTimerRef.current);
                              setHoveredArticleId(null);
                            }}
                          >
                            <a href={article.link} target="_blank" rel="noreferrer" className="hover:underline line-clamp-1 break-all flex-1">
                              {article.title}
                            </a>

                            {hoveredArticleId === (article.id ?? index) && (
                              <div className="absolute top-full left-0 mt-2 w-96 bg-popover text-popover-foreground border shadow-md rounded-md p-3 z-50 animate-in fade-in zoom-in-95 duration-200">
                                <p className="text-sm line-clamp-5 whitespace-pre-wrap">{article.summary || "Không có tóm tắt..."}</p>
                                <div className="mt-2 text-xs text-muted-foreground flex justify-between">
                                  <span>Nguồn: {article.source}</span>
                                  <span>{new Date(article.published_date).toLocaleDateString('vi-VN')}</span>
                                </div>
                              </div>
                            )}

                            {new Date().getTime() - new Date(article.published_date).getTime() < 14 * 24 * 60 * 60 * 1000 && (
                              <Badge className="bg-blue-100 text-blue-700 hover:bg-blue-200 border-transparent border py-0 px-2 h-5 text-[10px]">
                                Mới
                              </Badge>
                            )}
                          </h4>
                          <p className="text-sm text-muted-foreground mt-1 flex items-center gap-2 flex-wrap">
                            <span className="font-medium text-foreground">{article.source}</span>
                            <span>•</span>
                            <span>{new Date(article.published_date).toLocaleString('vi-VN')}</span>
                            <span>•</span>
                            {isDomestic(article.link, article.source) ? (
                              <Badge variant="outline" className="text-[10px] text-blue-600 border-blue-200 bg-blue-50/50">Trong nước</Badge>
                            ) : (
                              <Badge variant="outline" className="text-[10px] text-emerald-600 border-emerald-200 bg-emerald-50/50">Quốc tế</Badge>
                            )}
                            
                            {article.cases && article.cases.length > 0 && (
                              <span className="ml-2 flex items-center gap-2 flex-wrap">
                                {article.cases.filter(c => c.case_count > 0).map((c, i) => (
                                  <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300 border border-red-200 dark:border-red-800">
                                    {c.disease_name}: {c.case_count.toLocaleString()} ca
                                    {c.location && c.location.toLowerCase() !== "unknown" ? ` (${c.location})` : ''}
                                  </span>
                                ))}
                              </span>
                            )}
                          </p>
                        </div>
                        {article.is_whitelisted && (
                          <Badge variant="secondary" className="bg-green-100 text-green-800 hover:bg-green-100">Uy tín</Badge>
                        )}
                        {!article.is_whitelisted && (
                          <Badge variant="outline">Thủ công</Badge>
                        )}
                      </div>
                      <div className="flex flex-wrap gap-1">
                        {article.keywords_matched?.split(",").map((keyword, i) => (
                          <Badge key={i} variant="outline" className="text-xs">
                            {keyword.trim()}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="pl-4 flex flex-col items-center justify-start gap-2">
                      <Button
                        variant="ghost"
                        size="icon"
                        onClick={() => article.id && handleToggleBookmark(article.id)}
                        className={bookmarkedArticleIds.has(article.id!) ? "text-primary" : "text-muted-foreground"}
                      >
                        {bookmarkedArticleIds.has(article.id!) ? (
                          <BookmarkCheck className="h-5 w-5" />
                        ) : (
                          <Bookmark className="h-5 w-5" />
                        )}
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
            {/* Phân trang dạng số */}
            {filteredArticles.length > 0 && totalArticlePages > 1 && (
              <div className="mt-6 flex items-center justify-center gap-1">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setArticlePage(p => Math.max(1, p - 1))}
                  disabled={articlePage === 1}
                >
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                {getPageNumbers(articlePage, totalArticlePages).map((page, idx) =>
                  page === '...' ? (
                    <span key={`dots-${idx}`} className="px-2 text-sm text-muted-foreground">…</span>
                  ) : (
                    <Button
                      key={page}
                      type="button"
                      variant={articlePage === page ? "default" : "outline"}
                      size="sm"
                      className="min-w-[36px]"
                      onClick={() => setArticlePage(page as number)}
                    >
                      {page}
                    </Button>
                  )
                )}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setArticlePage(p => Math.min(totalArticlePages, p + 1))}
                  disabled={articlePage === totalArticlePages}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Sự kiện đã gom</CardTitle>
          <CardDescription>Mỗi sự kiện có thể gồm nhiều bài viết từ nhiều nguồn khác nhau</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {events.length === 0 ? (
              <div className="py-4 text-center text-muted-foreground">
                Chưa có sự kiện nào được gom.
              </div>
            ) : (
              paginatedEvents.map((event) => (
                <div key={event.id} className="flex items-start justify-between gap-4 rounded-lg border p-4">
                  <div className="space-y-2">
                    <div className="font-medium">{event.canonical_title}</div>
                    <div className="flex flex-wrap gap-2 text-sm text-muted-foreground">
                      {event.severity && (
                        <Badge className={`text-[10px] px-1.5 py-0.5 border ${severityConfig[event.severity]?.color || severityConfig.low.color}`}>
                          {severityConfig[event.severity]?.label || event.severity}
                        </Badge>
                      )}
                      <span>{event.disease_name}</span>
                      {event.location && <span>• {event.location}</span>}
                      <span>• {new Date(event.event_date).toLocaleDateString()}</span>
                      <span>• {event.article_count} bài</span>
                      <span>• {event.source_count} nguồn</span>
                      {event.case_count > 0 && <span>• {event.case_count} ca</span>}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {event.sources_preview.map((source) => (
                        <Badge key={source} variant="outline" className="text-xs">
                          {source}
                        </Badge>
                      ))}
                    </div>
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => void handleOpenEvent(event.id)}
                    disabled={loadingEventId === event.id}
                  >
                    {loadingEventId === event.id ? "Đang tải..." : "Xem bài viết"}
                  </Button>
                </div>
              ))
            )}
          </div>
          {events.length > 0 && (
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEventPage((current) => Math.max(1, current - 1))}
                disabled={eventPage === 1}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Trước
              </Button>
              <div className="text-sm text-muted-foreground">
                Trang {eventPage} / {totalEventPages}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setEventPage((current) => Math.min(totalEventPages, current + 1))}
                disabled={eventPage === totalEventPages}
              >
                Sau
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          )}
        </CardContent>
      </Card>


    </div>
  );
};

export default KeywordMonitoring;
