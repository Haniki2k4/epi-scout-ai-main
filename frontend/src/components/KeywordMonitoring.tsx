import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Search, Plus, X, Play, Pause, Download, Settings, Trash2, CheckSquare, Square, ChevronLeft, ChevronRight } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { ScanResultModal } from "./ScanResultModal";
import { Article, Keyword, NewsEvent, NewsEventDetail } from "@/types";

const SCAN_STATE_KEY = "epi_scout_scan_state";

const KeywordMonitoring = () => {
  const { toast } = useToast();
  const [isScanning, setIsScanning] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const [activeKeywords, setActiveKeywords] = useState<Keyword[]>([]);
  const [lastScanDuration, setLastScanDuration] = useState<number | null>(null);
  const [articles, setArticles] = useState<Article[]>([]);
  const [scanAll, setScanAll] = useState(false);
  const [unknownArticles, setUnknownArticles] = useState<Article[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [keywordFilter, setKeywordFilter] = useState("");
  const [scanStartDate, setScanStartDate] = useState("");
  const [scanEndDate, setScanEndDate] = useState("");
  const [scanDateWarningConfirmed, setScanDateWarningConfirmed] = useState(false);
  const [selectedKeywordIds, setSelectedKeywordIds] = useState<number[]>([]);
  const [rssSourceCount, setRssSourceCount] = useState<number>(0);

  // Keyword Edit State
  const [editingKeyword, setEditingKeyword] = useState<Keyword | null>(null);
  const [editKeywordText, setEditKeywordText] = useState("");
  const [editDialogOpen, setEditDialogOpen] = useState(false);

  // Scan result popup
  const [scanResultPopup, setScanResultPopup] = useState<{
    open: boolean;
    savedCount: number;
    diseaseCounts: Record<string, number>;
    executionTime: number;
    unknownCount: number;
  }>({ open: false, savedCount: 0, diseaseCounts: {}, executionTime: 0, unknownCount: 0 });

  // Timer đang quét (elapsed time)
  const [scanElapsedTime, setScanElapsedTime] = useState(0);
  const [scanStartedAt, setScanStartedAt] = useState<number | null>(null);
  const scanTimerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [events, setEvents] = useState<NewsEvent[]>([]);
  const [selectedEvent, setSelectedEvent] = useState<NewsEventDetail | null>(null);
  const [eventDialogOpen, setEventDialogOpen] = useState(false);
  const [loadingEventId, setLoadingEventId] = useState<number | null>(null);
  const [articleSearch, setArticleSearch] = useState("");
  const [articleSourceFilter, setArticleSourceFilter] = useState("all");
  const [articleKeywordFilter, setArticleKeywordFilter] = useState("all");
  const [articleTrustFilter, setArticleTrustFilter] = useState("all");
  const [articleSort, setArticleSort] = useState("newest");
  const [articlePage, setArticlePage] = useState(1);
  const articlePageSize = 8;
  const [eventPage, setEventPage] = useState(1);
  const eventPageSize = 5;

  // Tooltip State
  const [hoveredArticleId, setHoveredArticleId] = useState<number | null>(null);
  const hoverTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Fetch RSS source count
  const fetchRssSourceCount = async () => {
    try {
      const res = await fetch("/api/rss-sources");
      if (res.ok) {
        const data = await res.json();
        setRssSourceCount(Array.isArray(data) ? data.filter((s: any) => s.is_active !== false).length : 0);
      }
    } catch (e) {
      console.error("Failed to fetch RSS source count", e);
    }
  };

  // Khôi phục trạng thái scan khi component mount lại (ví dụ chuyển tab rồi quay lại)
  useEffect(() => {
    const saved = sessionStorage.getItem(SCAN_STATE_KEY);
    if (saved) {
      try {
        const state = JSON.parse(saved);
        if (state.isScanning && state.startedAt) {
          const now = Date.now();
          const elapsedSeconds = Math.floor((now - state.startedAt) / 1000);
          
          // Nếu đã trôi qua quá 1 tiếng (3600s), coi như scan đã chết hoặc treo, tự xóa
          if (elapsedSeconds > 3600) {
            sessionStorage.removeItem(SCAN_STATE_KEY);
            return;
          }

          setIsScanning(true);
          setScanStartedAt(state.startedAt);
          setScanElapsedTime(elapsedSeconds);
        }
      } catch (e) {
        sessionStorage.removeItem(SCAN_STATE_KEY);
      }
    }
  }, []);

  // Timer chạy dựa trên scanStartedAt
  useEffect(() => {
    if (isScanning && scanStartedAt) {
      scanTimerRef.current = setInterval(() => {
        const elapsed = Math.floor((Date.now() - scanStartedAt) / 1000);
        setScanElapsedTime(elapsed);
      }, 1000);
    } else {
      if (scanTimerRef.current) clearInterval(scanTimerRef.current);
    }

    return () => {
      if (scanTimerRef.current) clearInterval(scanTimerRef.current);
    };
  }, [isScanning, scanStartedAt]);

  // Initial Fetch
  useEffect(() => {
    fetchKeywords();
    fetchArticles();
    fetchEvents();
    fetchRssSourceCount();
  }, []);

  const fetchKeywords = async () => {
    try {
      const res = await fetch("/api/keywords");
      if (res.ok) {
        const data = await res.json();
        setActiveKeywords(data);

        // Tự động chọn các keyword mặc định khi vừa chạy web
        const defaultKeywordTexts = ["cúm a", "cúm b", "cúm mùa", "não mô cầu", "bạch hầu", "ho gà", "viêm não nhật bản"];
        const defaultIds = data
          .filter((k: Keyword) => defaultKeywordTexts.includes(k.text.toLowerCase()))
          .map((k: Keyword) => k.id)
          .filter((id): id is number => id !== undefined);

        setSelectedKeywordIds(defaultIds);
      }
    } catch (e) {
      console.error("Failed to fetch keywords", e);
    }
  };

  const fetchArticles = async () => {
    try {
      const res = await fetch("/api/articles");
      if (res.ok) {
        const data = await res.json();
        setArticles(data);
      }
    } catch (e) {
      console.error("Failed to fetch articles", e);
    }
  };

  const fetchEvents = async () => {
    try {
      const res = await fetch("/api/events?limit=20");
      if (res.ok) {
        const data = await res.json();
        setEvents(data);
      }
    } catch (e) {
      console.error("Failed to fetch events", e);
    }
  };

  const parseKeywordInput = (input: string) => {
    const normalized = input.trim();
    if (!normalized) {
      return [];
    }

    const hasSeparator = normalized.includes(",") || normalized.includes("\n");
    const rawKeywords = hasSeparator ? normalized.split(/[,\n]/) : [normalized];

    return rawKeywords
      .map((keyword) => keyword.trim())
      .filter(Boolean);
  };

  const handleAddKeyword = async () => {
    const keywordsToAdd = parseKeywordInput(newKeyword);
    if (keywordsToAdd.length === 0) {
      return;
    }

    const existingKeywords = new Set(activeKeywords.map((keyword) => keyword.text.toLowerCase()));
    const uniqueKeywords = keywordsToAdd.filter((keyword, index) => {
      const lowerKeyword = keyword.toLowerCase();
      return keywordsToAdd.findIndex((item) => item.toLowerCase() === lowerKeyword) === index
        && !existingKeywords.has(lowerKeyword);
    });

    if (uniqueKeywords.length === 0) {
      toast({
        title: "Không có từ khóa mới",
        description: "Danh sách bạn nhập chỉ chứa các từ khóa đã tồn tại.",
      });
      setNewKeyword("");
      return;
    }

    try {
      const createdKeywords: Keyword[] = [];

      for (const keyword of uniqueKeywords) {
        const res = await fetch("/api/keywords", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: keyword }),
        });

        if (res.ok) {
          const payload = await res.json();
          if (Array.isArray(payload)) {
            createdKeywords.push(...payload);
          } else {
            createdKeywords.push(payload);
          }
        }
      }

      if (createdKeywords.length > 0) {
        setActiveKeywords([...activeKeywords, ...createdKeywords]);
        setNewKeyword("");
        toast({
          title: "Đã thêm từ khóa",
          description: createdKeywords.length === 1
            ? `Từ khóa "${createdKeywords[0].text}" đã được thêm vào hệ thống.`
            : `Đã thêm ${createdKeywords.length} từ khóa vào hệ thống.`,
        });
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể thêm từ khóa.", variant: "destructive" });
    }
  };

  const handleDeleteKeyword = async (id: number) => {
    try {
      const res = await fetch(`/api/keywords/${id}`, {
        method: "DELETE",
      });
      if (res.ok) {
        setActiveKeywords(activeKeywords.filter((k) => k.id !== id));
        toast({
          title: "Đã xóa từ khóa",
          description: "Từ khóa đã được xóa khỏi hệ thống.",
        });
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể xóa từ khóa.", variant: "destructive" });
    }
  };

  const toggleKeywordSelection = (id: number) => {
    setSelectedKeywordIds((current) =>
      current.includes(id) ? current.filter((item) => item !== id) : [...current, id]
    );
  };

  const handleSelectFilteredKeywords = () => {
    const filteredIds = filteredKeywords
      .map((keyword) => keyword.id)
      .filter((id): id is number => id !== undefined);

    const allFilteredSelected = filteredIds.length > 0 && filteredIds.every((id) => selectedKeywordIds.includes(id));
    setSelectedKeywordIds((current) =>
      allFilteredSelected
        ? current.filter((id) => !filteredIds.includes(id))
        : Array.from(new Set([...current, ...filteredIds]))
    );
  };

  const handleDeleteSelectedKeywords = async () => {
    if (selectedKeywordIds.length === 0) {
      toast({
        title: "Chưa chọn từ khóa",
        description: "Hãy chọn ít nhất một từ khóa để xóa hàng loạt.",
      });
      return;
    }

    try {
      const results = await Promise.all(
        selectedKeywordIds.map((id) =>
          fetch(`/api/keywords/${id}`, {
            method: "DELETE",
          })
        )
      );

      const deletedCount = results.filter((result) => result.ok).length;
      if (deletedCount > 0) {
        setActiveKeywords((current) => current.filter((keyword) => !selectedKeywordIds.includes(keyword.id!)));
        setSelectedKeywordIds([]);
        toast({
          title: "Đã xóa từ khóa",
          description: `Đã xóa ${deletedCount} từ khóa khỏi hệ thống.`,
        });
      } else {
        toast({
          title: "Không thể xóa",
          description: "Không có từ khóa nào được xóa.",
          variant: "destructive",
        });
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể xóa hàng loạt từ khóa.", variant: "destructive" });
    }
  };

  const handleEditKeywordOpen = (keyword: Keyword) => {
    setEditingKeyword(keyword);
    setEditKeywordText(keyword.text);
    setEditDialogOpen(true);
  };

  const handleEditKeywordSave = async () => {
    if (!editingKeyword || !editingKeyword.id || !editKeywordText.trim()) return;

    try {
      const res = await fetch(`/api/keywords/${editingKeyword.id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: editKeywordText.trim() }),
      });

      if (res.ok) {
        const payload = await res.json();
        setActiveKeywords(current =>
          current.map(k => (k.id === editingKeyword.id ? { ...k, text: payload.text } : k))
        );
        toast({ title: "Thành công", description: "Đã cập nhật từ khóa." });
        setEditDialogOpen(false);
      } else {
        toast({ title: "Lỗi", description: "Cập nhật từ khóa thất bại.", variant: "destructive" });
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể kết nối đến máy chủ.", variant: "destructive" });
    }
  };

  const scanAbortController = useRef<AbortController | null>(null);

  const handleStartScan = async () => {
    if (activeKeywords.length === 0) {
      toast({
        title: "Chưa có từ khóa giám sát",
        description: newKeyword.trim()
          ? `Bạn đã nhập "${newKeyword.trim()}" nhưng chưa lưu. Nhấn dấu + để thêm từ khóa trước khi quét.`
          : "Hãy thêm ít nhất một từ khóa vào hệ thống trước khi bắt đầu quét.",
        variant: "destructive",
      });
      return;
    }

    // Cảnh báo nếu chưa chọn phạm vi thời gian
    const missingStart = !scanStartDate;
    const missingEnd = !scanEndDate;
    if ((missingStart || missingEnd) && !scanDateWarningConfirmed) {
      const missingFields = [];
      if (missingStart) missingFields.push("ngày bắt đầu");
      if (missingEnd) missingFields.push("ngày kết thúc");
      toast({
        title: "⚠️ Chưa chọn phạm vi thời gian",
        description: `Bạn chưa nhập ${missingFields.join(" và ")}. Hệ thống sẽ tự động lấy tin tức trong 14 ngày gần nhất. Nhấn Bắt đầu quét lần nữa để tiếp tục.`,
        variant: "destructive",
      });
      setScanDateWarningConfirmed(true);
      return;
    }

    setScanDateWarningConfirmed(false);
    setIsScanning(true);
    setScanElapsedTime(0);
    const now = Date.now();
    setScanStartedAt(now);
    sessionStorage.setItem(SCAN_STATE_KEY, JSON.stringify({ isScanning: true, startedAt: now }));
    
    scanAbortController.current = new AbortController();
    toast({
      title: "Đang quét tin tức...",
      description: "Hệ thống đang tìm kiếm tin tức từ nguồn RSS...",
    });

    // Lấy tên các từ thực tế đang được chọn (từ selectedKeywordIds)
    const selectedKwTexts = activeKeywords
      .filter(k => k.id !== undefined && selectedKeywordIds.includes(k.id!))
      .map(k => k.text);

    try {
      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        signal: scanAbortController.current.signal,
        body: JSON.stringify({
          fetch_unknown: scanAll,
          start_date: scanStartDate ? new Date(scanStartDate).toISOString() : null,
          end_date: scanEndDate ? new Date(scanEndDate).toISOString() : null,
          // Gửi keyword đang chọn; nếu chọn hết hoặc trống = gửi null (quét hết DB)
          keywords_to_scan: selectedKwTexts.length > 0 && selectedKwTexts.length < activeKeywords.length
            ? selectedKwTexts
            : null,
        }),
      });

      if (res.ok) {
        const result = await res.json();
        fetchArticles();
        fetchEvents();
        setLastScanDuration(result.execution_time || null);

        // Hiển thị popup thống kê kết quả
        setScanResultPopup({
          open: true,
          savedCount: result.saved_trusted_count ?? 0,
          diseaseCounts: result.disease_counts ?? {},
          executionTime: result.execution_time ?? 0,
          unknownCount: result.unknown_articles?.length ?? 0,
        });

        if (result.unknown_articles && result.unknown_articles.length > 0) {
          setUnknownArticles(result.unknown_articles);
          setShowModal(true);
        }
      }
    } catch (e: any) {
      if (e.name === 'AbortError') {
        toast({
          title: "Đã hủy yêu cầu quét",
          description: "FE đã hủy kết nối. Lưu ý: các bài báo đang xử lý ở BE có thể vẫn được lưu.",
          variant: "destructive",
        });
        return;
      }
      toast({ title: "Lỗi", description: "Quét thất bại.", variant: "destructive" });
    } finally {
      setIsScanning(false);
      setScanStartedAt(null);
      scanAbortController.current = null;
      sessionStorage.removeItem(SCAN_STATE_KEY);
    }
  };

  const handleStopScan = () => {
    if (scanAbortController.current) {
      scanAbortController.current.abort();
    }
    if (scanTimerRef.current) clearInterval(scanTimerRef.current);
    setIsScanning(false);
    sessionStorage.removeItem(SCAN_STATE_KEY);
    toast({
      title: "Đã hủy yêu cầu quét",
      description: "FE đã ngắt kết nối. Lưu ý: các bài báo đang xử lý ở BE vẫn có thể được lưu.",
      variant: "destructive"
    });
  };

  const handleSaveUnknown = async (articlesToSave: Article[]) => {
    try {
      const results = await Promise.all(
        articlesToSave.map((article) =>
          fetch("/api/articles/save", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(article),
          })
        )
      );

      const savedCount = results.filter((result) => result.ok).length;
      if (savedCount > 0) {
        await fetchArticles();
        await fetchEvents();
        toast({
          title: "Thành công",
          description: `Đã lưu ${savedCount}/${articlesToSave.length} bài viết.`,
        });
        return true;
      }

      toast({
        title: "Không thể lưu",
        description: "Không có bài viết nào được lưu.",
        variant: "destructive",
      });
      return false;
    } catch (e) {
      toast({ title: "Lỗi", description: "Lưu thất bại.", variant: "destructive" });
      return false;
    }
  };

  const handleAddWhitelist = async (domain: string) => {
    try {
      // Thêm domain vào rss_sources (thay thế whitelist cũ)
      const res = await fetch("/api/rss-sources", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: `https://${domain}`, label: domain, category: "trusted", is_active: true }),
      });
      if (res.ok) {
        return res.status === 201 ? "created" : "exists";
      }
      return "error";
    } catch (e) {
      console.error(e);
      return "error";
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

  const articleSources = Array.from(
    new Set(articles.map((article) => article.source).filter(Boolean))
  ).sort((a, b) => a.localeCompare(b, "vi"));

  const articleKeywords = Array.from(
    new Set(
      articles.flatMap((article) =>
        (article.keywords_matched || "")
          .split(",")
          .map((keyword) => keyword.trim())
          .filter(Boolean)
      )
    )
  ).sort((a, b) => a.localeCompare(b, "vi"));

  const filteredArticles = [...articles]
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
    });

  const totalArticlePages = Math.max(1, Math.ceil(filteredArticles.length / articlePageSize));
  const paginatedArticles = filteredArticles.slice(
    (articlePage - 1) * articlePageSize,
    articlePage * articlePageSize
  );

  useEffect(() => {
    setArticlePage(1);
  }, [articleSearch, articleSourceFilter, articleKeywordFilter, articleTrustFilter, articleSort]);

  useEffect(() => {
    if (articlePage > totalArticlePages) {
      setArticlePage(totalArticlePages);
    }
  }, [articlePage, totalArticlePages]);

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

  return (
    <div className="space-y-6">
      <ScanResultModal
        open={showModal}
        onOpenChange={setShowModal}
        unknownArticles={unknownArticles}
        onSaveArticles={handleSaveUnknown}
        onAddWhitelist={handleAddWhitelist}
      />

      {/* Popup kết quả scan */}
      <Dialog open={scanResultPopup.open} onOpenChange={(o) => setScanResultPopup(p => ({ ...p, open: o }))}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              ✅ Quét hoàn tất
            </DialogTitle>
            <DialogDescription>
              Thống kê kết quả lần quét vừa xong
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-2">
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="rounded-lg bg-primary/10 p-3 border border-primary/20">
                <div className="text-2xl font-bold text-primary">{scanResultPopup.savedCount}</div>
                <div className="text-xs text-muted-foreground mt-1">Bài đã lưu</div>
              </div>
              <div className="rounded-lg bg-secondary p-3 border border-border/50">
                <div className="text-2xl font-bold">{scanResultPopup.unknownCount}</div>
                <div className="text-xs text-muted-foreground mt-1">Bài chờ duyệt</div>
              </div>
              <div className="rounded-lg bg-muted p-3 border border-border/50">
                <div className="text-2xl font-bold">{scanResultPopup.executionTime.toFixed(1)}s</div>
                <div className="text-xs text-muted-foreground mt-1">Thời gian</div>
              </div>
            </div>

            {Object.keys(scanResultPopup.diseaseCounts).length > 0 && (
              <div>
                <p className="text-sm font-medium mb-2">Phân loại theo bệnh:</p>
                <div className="flex flex-wrap gap-2">
                  {Object.entries(scanResultPopup.diseaseCounts)
                    .sort(([, a], [, b]) => b - a)
                    .map(([disease, count]) => (
                      <div key={disease} className="flex items-center gap-1 bg-primary/10 text-primary border border-primary/20 rounded-full px-3 py-1 text-xs font-medium">
                        <span className="capitalize">{disease}</span>
                        <span className="bg-primary text-primary-foreground rounded-full px-1.5 text-[10px] font-bold">{count}</span>
                      </div>
                    ))}
                </div>
              </div>
            )}

            {scanResultPopup.savedCount === 0 && scanResultPopup.unknownCount === 0 && (
              <p className="text-center text-sm text-muted-foreground">Không tìm thấy bài viết mới phù hợp.</p>
            )}
          </div>
          <div className="flex justify-end">
            <Button onClick={() => setScanResultPopup(p => ({ ...p, open: false }))}>Đóng</Button>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={eventDialogOpen} onOpenChange={setEventDialogOpen}>
        <DialogContent className="max-h-[80vh] max-w-3xl overflow-hidden">
          <DialogHeader>
            <DialogTitle>{selectedEvent?.canonical_title || "Chi tiết sự kiện"}</DialogTitle>
            <DialogDescription>
              {selectedEvent?.disease_name}
              {selectedEvent?.location ? ` • ${selectedEvent.location}` : ""}
              {selectedEvent?.event_date ? ` • ${new Date(selectedEvent.event_date).toLocaleString()}` : ""}
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

      {/* Control Panel */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Quản lý từ khóa</CardTitle>
            <CardDescription>Thêm từ khóa giám sát vào database</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Dialog open={editDialogOpen} onOpenChange={setEditDialogOpen}>
                <DialogContent>
                  <DialogHeader>
                    <DialogTitle>Chỉnh sửa từ khóa</DialogTitle>
                    <DialogDescription>Thay đổi nội dung của từ khóa này.</DialogDescription>
                  </DialogHeader>
                  <div className="py-4">
                    <Input
                      value={editKeywordText}
                      onChange={(e) => setEditKeywordText(e.target.value)}
                      placeholder="Nội dung từ khóa..."
                    />
                  </div>
                  <div className="flex justify-end gap-2">
                    <Button variant="outline" onClick={() => setEditDialogOpen(false)}>Hủy</Button>
                    <Button onClick={handleEditKeywordSave}>Lưu thay đổi</Button>
                  </div>
                </DialogContent>
              </Dialog>

              <Input
                placeholder="Nhập 1 từ khóa hoặc nhiều từ khóa, ngăn cách bằng dấu phẩy..."
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
              />
              <Button onClick={handleAddKeyword} size="icon">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-col gap-3">
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    placeholder="Lọc từ khóa..."
                    value={keywordFilter}
                    onChange={(e) => setKeywordFilter(e.target.value)}
                    className="pl-9"
                  />
                </div>
                <Button type="button" variant="outline" onClick={handleSelectFilteredKeywords} disabled={filteredKeywordIds.length === 0}>
                  {allFilteredSelected ? <Square className="mr-2 h-4 w-4" /> : <CheckSquare className="mr-2 h-4 w-4" />}
                  {allFilteredSelected ? "Bỏ chọn" : "Chọn hết"}
                </Button>
                <Button
                  type="button"
                  variant="destructive"
                  onClick={handleDeleteSelectedKeywords}
                  disabled={selectedKeywordIds.length === 0}
                  className="hover:bg-[#f2645a] hover:text-white transition-colors"
                >
                  <Trash2 className="mr-2 h-4 w-4" />
                  Xóa đã chọn
                </Button>
              </div>
              <div className="text-xs text-muted-foreground">
                Hiển thị {filteredKeywords.length}/{activeKeywords.length} từ khóa. Đã chọn {selectedKeywordIds.length}.
              </div>
            </div>
            <div className="flex flex-wrap gap-2">
              {filteredKeywords.map((keyword) => (
                <Badge
                  key={keyword.id}
                  variant={selectedKeywordIds.includes(keyword.id!) ? "default" : "secondary"}
                  className="px-3 py-1 flex items-center gap-2"
                >
                  <span className="cursor-pointer" onClick={() => toggleKeywordSelection(keyword.id!)}>
                    {keyword.text}
                  </span>
                  <div className="flex gap-1 items-center bg-background/20 rounded px-1 group-hover:opacity-100">
                    <span
                      className="cursor-pointer hover:bg-blue-800/20 rounded px-0.5 transition-colors"
                      onClick={(e) => { e.stopPropagation(); handleEditKeywordOpen(keyword); }}
                      title="Sửa từ khóa"
                    >
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                      </svg>
                    </span>
                    <span
                      className="cursor-pointer hover:text-red-300 transition-colors"
                      onClick={(e) => { e.stopPropagation(); keyword.id && handleDeleteKeyword(keyword.id); }}
                      title="Xóa từ khóa"
                    >
                      <Trash2 className="h-3 w-3" />
                    </span>
                  </div>
                </Badge>
              ))}
              {activeKeywords.length === 0 && (
                <div className="text-sm text-muted-foreground">
                  Chưa có từ khóa nào được lưu. Bạn có thể nhập nhiều từ khóa, ngăn cách bằng dấu phẩy hoặc xuống dòng.
                </div>
              )}
              {activeKeywords.length > 0 && filteredKeywords.length === 0 && (
                <div className="text-sm text-muted-foreground">
                  Không tìm thấy từ khóa nào khớp với bộ lọc hiện tại.
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Điều khiển quét</CardTitle>
            <CardDescription>Bắt đầu quét tin tức từ RSS</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex items-center gap-4">
              <div className="flex items-center space-x-2">
                <Switch id="scan-all" checked={scanAll} onCheckedChange={setScanAll} />
                <Label htmlFor="scan-all">Quét mở rộng (Nguồn chưa xác thực)</Label>
              </div>
            </div>

            <div className="flex flex-col gap-2">
              <Label>Phạm vi thời gian quét (Tùy chọn)</Label>
              <div className="flex gap-2">
                <Input
                  type="date"
                  value={scanStartDate}
                  onChange={(e) => { setScanStartDate(e.target.value); setScanDateWarningConfirmed(false); }}
                  className="w-full"
                />
                <div className="flex items-center">-</div>
                <Input
                  type="date"
                  value={scanEndDate}
                  onChange={(e) => { setScanEndDate(e.target.value); setScanDateWarningConfirmed(false); }}
                  className="w-full"
                />
              </div>
              <div className="flex gap-2">
                <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={() => {
                  const end = new Date();
                  const start = new Date();
                  start.setDate(end.getDate() - 5);
                  setScanStartDate(start.toISOString().split('T')[0]);
                  setScanEndDate(end.toISOString().split('T')[0]);
                }}>5 ngày</Button>
                <Button type="button" variant="outline" size="sm" className="h-7 text-xs" onClick={() => {
                  const end = new Date();
                  const start = new Date();
                  start.setDate(end.getDate() - 15);
                  setScanStartDate(start.toISOString().split('T')[0]);
                  setScanEndDate(end.toISOString().split('T')[0]);
                }}>15 ngày</Button>
                <Button type="button" variant="outline" size="sm" className="h-7 text-xs ml-auto hover:bg-[#f2645a] hover:text-white hover:border-[#f2645a] transition-colors" onClick={() => {
                  setScanStartDate("");
                  setScanEndDate("");
                  setScanDateWarningConfirmed(false);
                }}>Xóa</Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Để trống nếu muốn tự động lấy tin cũ tối đa 14 ngày.
              </p>
              {/* Reset cảnh báo khi người dùng thay đổi ngày */}
              {scanDateWarningConfirmed && (
                <p className="text-xs font-medium text-destructive flex items-center gap-1">
                  ⚠️ Chưa chọn đầy đủ ngày. Nhấn <strong>Bắt đầu quét</strong> lần nữa để tiếp tục mà không lọc ngày.
                </p>
              )}
            </div>

            <div className="flex flex-col gap-2">
              <Button
                onClick={isScanning ? handleStopScan : handleStartScan}
                className={`flex-1 ${isScanning ? "hover:bg-[#f2645a] hover:text-white transition-colors" : ""}`}
                variant={isScanning ? "destructive" : "default"}
              >
                {isScanning ? (
                  <>
                    <Pause className="mr-2 h-4 w-4" />
                    Dừng quét
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Bắt đầu quét
                  </>
                )}
              </Button>
              {/* Timer đang quét */}
              {isScanning && (
                <p className="text-center text-[11px] text-primary font-medium mt-1 animate-pulse">
                  ⏱ Đang quét... {scanElapsedTime}s
                </p>
              )}
              {lastScanDuration !== null && !isScanning && (
                <p className="text-center text-[11px] text-muted-foreground mt-1">
                  Thời gian quét lần gần nhất: <span className="font-medium text-primary">{lastScanDuration.toFixed(1)}s</span>
                </p>
              )}
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="text-center p-3 bg-secondary rounded-lg">
                <div className="text-2xl font-bold text-foreground">{articles.length}</div>
                <div className="text-xs text-muted-foreground">Bài viết đã lưu</div>
              </div>
              <div className="text-center p-3 bg-secondary rounded-lg">
                <div className="text-2xl font-bold text-foreground">{rssSourceCount}</div>
                <div className="text-xs text-muted-foreground">Nguồn tin RSS</div>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

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
              <Select value={articleKeywordFilter} onValueChange={setArticleKeywordFilter}>
                <SelectTrigger>
                  <SelectValue placeholder="Lọc theo keyword" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">Tất cả keyword</SelectItem>
                  {articleKeywords.map((keyword) => (
                    <SelectItem key={keyword} value={keyword}>
                      {keyword}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
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
              <div className="text-sm text-muted-foreground">
                Hiển thị {filteredArticles.length}/{articles.length} bài viết • Trang {articlePage}/{totalArticlePages}
              </div>
            </div>
          </div>
          <div className="space-y-4">
            {articles.length === 0 ? (
              <div className="text-center text-muted-foreground py-4">Chưa có bài viết nào. Hãy thêm từ khóa và quét ngay!</div>
            ) : filteredArticles.length === 0 ? (
              <div className="text-center text-muted-foreground py-4">
                Không có bài viết nào khớp với bộ lọc hiện tại.
              </div>
            ) : (
              paginatedArticles.map((article, index) => (
                <div
                  key={index}
                  className="flex items-start justify-between p-4 border border-border rounded-lg hover:bg-secondary/50 transition-colors"
                >
                  <div className="flex-1 space-y-2">
                    <div className="flex items-start gap-3">
                      <div className="flex-1">
                        <h4 
                          className="font-medium text-foreground flex items-center flex-wrap gap-2 relative"
                          onMouseEnter={() => {
                            hoverTimerRef.current = setTimeout(() => {
                              setHoveredArticleId(index);
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
                          
                          {hoveredArticleId === index && (
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
                          <span>{article.source}</span>
                          <span>•</span>
                          <span>{new Date(article.published_date).toLocaleString('vi-VN')}</span>
                          {article.cases && article.cases.length > 0 && (
                             article.cases.filter(c => c.case_count > 0).map((c, i) => (
                               <span key={i} className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[11px] font-semibold bg-red-100 text-red-700 dark:bg-red-950 dark:text-red-300 border border-red-200 dark:border-red-800">
                                 {c.disease_name}: {c.case_count.toLocaleString()} ca
                                 {c.location ? ` (${c.location})` : ''}
                               </span>
                             ))
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
                </div>
              ))
            )}
          </div>
          {filteredArticles.length > 0 && (
            <div className="mt-4 flex items-center justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setArticlePage((current) => Math.max(1, current - 1))}
                disabled={articlePage === 1}
              >
                <ChevronLeft className="mr-1 h-4 w-4" />
                Trước
              </Button>
              <div className="text-sm text-muted-foreground">
                Trang {articlePage} / {totalArticlePages}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => setArticlePage((current) => Math.min(totalArticlePages, current + 1))}
                disabled={articlePage === totalArticlePages}
              >
                Sau
                <ChevronRight className="ml-1 h-4 w-4" />
              </Button>
            </div>
          )}
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

      {/* Template Helper */}
      <Card>
        <CardHeader>
          <CardTitle>Gợi ý từ khóa</CardTitle>
        </CardHeader>
        <CardContent>
          <Textarea
            className="font-mono text-sm min-h-[200px]"
            defaultValue={`Bại liệt, cúm gia cầm, dịch hạch, đậu mùa, bệnh tả, tay chân miệng, sốt phát ban, sởi, sốt xuất huyết, bạch hầu, ho gà, viêm não nhật bản, viêm não vi rút, thủy đậu, cúm A, cúm B, cúm mùa, não mô cầu, bệnh lạ, viêm phổi nặng, bệnh mới nổi, chưa rõ tác nhân gây bệnh, bùng phát ca bệnh, gia tăng số ca bệnh, gia tăng số lượng người nhập viện, hàng loạt ca bệnh, ổ dịch, vụ dịch, phản ứng nặng sau tiêm vắc xin, tử vong do bệnh truyền nhiễm, tử vong không rõ nguyên nhân, tử vong sau tiêm vắc xin, động vật ốm chết hàng loạt, gia cầm ốm chết, unknown disease, emerging disease, re-emerging disease, avian influenza, H5N1, Bird Flu, Ebola`}
            readOnly
          />
        </CardContent>
      </Card>
    </div>
  );
};

export default KeywordMonitoring;
