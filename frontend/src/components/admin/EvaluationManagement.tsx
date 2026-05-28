import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  AlertCircle,
  BarChart3,
  Bug,
  CheckCircle,
  Download,
  FileUp,
  RefreshCcw,
  Upload,

  Database,
  X,

} from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

// --- Types ---

interface DiseaseCaseInfo {
  disease_name: string;
  case_count: number;
  location?: string;
}

interface Article {
  id: number;
  title?: string;
  link: string;
  source?: string;
  keywords_matched?: string;
  event_id?: number;
  llm_label: string;           // "relevant" | "irrelevant"
  human_label?: string;        // Nhãn thủ công đã lưu trong DB
  keyword_is_correct?: boolean;
  corrected_keyword?: string;
  draft_keyword?: string;
  is_verified: boolean;
  cases: DiseaseCaseInfo[];    // Danh sách dịch bệnh từ disease_cases
}

interface Metrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1_score: number;
  total_verified: number;
  agreement_rate: number;
  confusion_matrix: Record<string, Record<string, number>>;
  disease_accuracy: number;
  latest_session?: {
    date: string;
    total: number;
    correct: number;
    verified_count: number;
    total_checked: number;
    noise_count: number;
    irrelevant_count: number;
    unsure_count: number;
    duration_seconds: number;
    avg_time_per_article: number;
  } | null;
}

interface ImportSummary {
  updated: number;
  skipped: number;
  not_found: number;
  errors: number;
  dataset_examples: number;
}

interface ImportResult {
  status: string;
  filename: string;
  summary: ImportSummary;
  dataset_path?: string | null;
  dataset_error?: string | null;
  details: Array<{
    row: number;
    status: string;
    article_id?: number;
    title?: string;
    reason?: string;
  }>;
}

// --- Helpers ---

export default function EvaluationManagement() {
  const { toast } = useToast();
  const [articles, setArticles] = useState<Article[]>([]);
  const [metrics, setMetrics] = useState<Metrics>({ accuracy: 0, precision: 0, recall: 0, f1_score: 0, total_verified: 0, agreement_rate: 0, confusion_matrix: {}, disease_accuracy: 0 });
  const [totalArticles, setTotalArticles] = useState(0);
  const [totalVerified, setTotalVerified] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [page, setPage] = useState(1);
  const [syncing, setSyncing] = useState(false);
  const [filterLabel, setFilterLabel] = useState<string | null>(null);
  const [savingKeywordId, setSavingKeywordId] = useState<number | null>(null);
  const [savedKeywordId, setSavedKeywordId] = useState<number | null>(null);
  const limit = 100;

  useEffect(() => {
    fetchData();
  }, [page, filterLabel]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("token");
      const headers = { Authorization: `Bearer ${token}` };

      // Fetch metrics
      const mRes = await fetch("/api/evaluation/metrics", { headers });
      if (mRes.ok) {
        setMetrics(await mRes.json());
      }

      // Fetch articles qua endpoint chuyên dụng:
      const url = new URL("/api/evaluation/articles", window.location.origin);
      url.searchParams.append("limit", limit.toString());
      url.searchParams.append("skip", ((page - 1) * limit).toString());
      if (filterLabel) {
        url.searchParams.append("filter_label", filterLabel);
      }

      const aRes = await fetch(url.toString(), { headers });
      if (aRes.ok) {
        const data = await aRes.json();
        setArticles((data.items || []).map((a: Article) => ({ ...a, draft_keyword: a.corrected_keyword })));
        setTotalArticles(data.total || 0);
        setTotalVerified(data.total_verified || 0);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleUpdateLabel = async (articleId: number, label: string) => {
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/evaluation/${articleId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ human_label: label }),
      });
      if (res.ok) {
        toast({ title: "Thành công", description: "Đã cập nhật nhãn đánh giá" });
        setArticles(articles.map(a => a.id === articleId ? { ...a, human_label: label, is_verified: true } : a));
        // Refresh metrics
        const mRes = await fetch("/api/evaluation/metrics", { headers: { Authorization: `Bearer ${token}` } });
        if (mRes.ok) setMetrics(await mRes.json());
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể cập nhật nhãn", variant: "destructive" });
    }
  };

  const handleUpdateKeyword = async (articleId: number, isCorrect: boolean, correctedKeyword?: string) => {
    let updateGlobal = false;
    // Ask if they want to update global if they typed a new keyword and article is relevant
    if (correctedKeyword) {
      updateGlobal = window.confirm(
        "Bạn có muốn cập nhật keyword này làm keyword chính thức cho bài báo trên toàn hệ thống không?"
      );
    }

    setSavingKeywordId(articleId);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch(`/api/evaluation/${articleId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          keyword_is_correct: isCorrect,
          corrected_keyword: correctedKeyword,
          update_article_keyword: updateGlobal
        }),
      });
      if (res.ok) {
        toast({ title: "Thành công", description: "Đã cập nhật kiểm chứng keyword" });
        setArticles(articles.map(a => {
          if (a.id === articleId) {
            return {
              ...a,
              keyword_is_correct: isCorrect,
              corrected_keyword: correctedKeyword,
              draft_keyword: correctedKeyword,
              keywords_matched: updateGlobal ? (correctedKeyword === "NONE" ? "" : correctedKeyword) : a.keywords_matched,
              is_verified: true
            };
          }
          return a;
        }));
        setSavedKeywordId(articleId);
        setTimeout(() => setSavedKeywordId(null), 2000);
        // Refresh metrics
        const mRes = await fetch("/api/evaluation/metrics", { headers: { Authorization: `Bearer ${token}` } });
        if (mRes.ok) setMetrics(await mRes.json());
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Không thể cập nhật kiểm chứng keyword", variant: "destructive" });
    } finally {
      setSavingKeywordId(null);
    }
  };

  const handleSyncDataset = async () => {
    setSyncing(true);
    try {
      const token = localStorage.getItem("token");
      const res = await fetch("/api/evaluation/sync-dataset", {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` }
      });
      if (!res.ok) {
        let detail = "Đồng bộ thất bại";
        try { const payload = await res.json(); if (payload?.detail) detail = payload.detail; } catch { /* ignore */ }
        throw new Error(detail);
      }
      const data = await res.json();
      toast({ title: "Đồng bộ thành công", description: data.message });
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Đồng bộ thất bại";
      toast({ title: "Lỗi", description: msg, variant: "destructive" });
    } finally {
      setSyncing(false);
    }
  };

  const handleExportExcel = async () => {
    try {
      const token = localStorage.getItem("token");
      toast({ title: "Đang tải...", description: "Vui lòng chờ trong khi hệ thống xuất file Excel." });

      const response = await fetch(`/api/evaluation/export-excel`, {
        method: "GET",
        headers: {
          Authorization: `Bearer ${token}`,
        },
      });

      if (!response.ok) {
        throw new Error("Không thể tải file, xác thực thất bại hoặc có lỗi máy chủ.");
      }

      // Convert response to Blob
      const blob = await response.blob();

      // Create a temporary link to download the blob
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.setAttribute("download", "llm_evaluation_dataset.xlsx");
      document.body.appendChild(link);
      link.click();

      // Clean up
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast({ title: "Thành công", description: "Đã xuất file Excel thành công." });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Đã có lỗi xảy ra khi xuất file.";
      toast({ title: "Lỗi", description: message, variant: "destructive" });
    }
  };

  const handleFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] ?? null;
    setSelectedFile(file);
    setImportResult(null);
  };

  const resetImportDialog = (open: boolean) => {
    setImportDialogOpen(open);
    if (!open) {
      setSelectedFile(null);
      setImportResult(null);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleImportExcel = async () => {
    if (!selectedFile) return;

    setImporting(true);
    try {
      const token = localStorage.getItem("token");
      const formData = new FormData();
      formData.append("file", selectedFile);

      const response = await fetch("/api/evaluation/import-excel", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
        },
        body: formData,
      });

      if (!response.ok) {
        let errorDetail = "Không thể nhập file Excel.";
        try {
          const payload = await response.json();
          if (payload?.detail) errorDetail = payload.detail;
        } catch {
          try {
            const text = await response.text();
            if (text) errorDetail = text.substring(0, 300);
          } catch { /* ignore */ }
        }
        throw new Error(errorDetail);
      }

      const result = await response.json() as ImportResult;
      setImportResult(result);
      await fetchData();
      toast({
        title: "Thành công",
        description: `Đã cập nhật ${result.summary.updated} nhãn và đồng bộ ${result.summary.dataset_examples} mẫu cho mô hình.`,
      });
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : "Đã có lỗi xảy ra khi nhập file.";
      toast({ title: "Lỗi", description: message, variant: "destructive" });
    } finally {
      setImporting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-start">
        <div>
          <h2 className="text-3xl font-bold tracking-tight">Đánh giá Mô hình LLM</h2>
          <p className="text-muted-foreground mt-2">
            Gán nhãn thủ công và đối soát kết quả phân loại của Gemini AI.
            <br />
            <span className="text-xs">
              <strong>Relevant</strong>: Có sự kiện dịch tễ thực ·{" "}
              <strong >Noise</strong>: Đề cập bệnh nhưng không liên quan ·{" "}
              <strong>Irrelevant</strong>: Không liên quan đến dịch bệnh ·{" "}
              <strong>Unsure</strong>: Chưa chắc, cần xem xét thêm
            </span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Dialog open={importDialogOpen} onOpenChange={resetImportDialog}>
            <DialogTrigger asChild>
              <Button variant="outline" className="gap-2">
                <Upload className="h-4 w-4" />
                Nhập Dataset
              </Button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[560px]">
              <DialogHeader>
                <DialogTitle className="flex items-center gap-2">
                  <FileUp className="h-5 w-5 text-primary" />
                  Nhập dữ liệu đã gán nhãn
                </DialogTitle>
                <DialogDescription>
                  Tải lên file Excel đã xuất từ màn hình này sau khi điền cột Nhãn Thủ công. Hệ thống sẽ cập nhật danh sách và tạo lại dataset cho mô hình đọc.
                </DialogDescription>
              </DialogHeader>

              <div className="space-y-4 py-2">
                <div
                  className="rounded-lg border-2 border-dashed border-border p-6 text-center transition-colors hover:border-primary/50 hover:bg-primary/5"
                  onClick={() => fileInputRef.current?.click()}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      fileInputRef.current?.click();
                    }
                  }}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".xlsx,.xlsm,.xls"
                    className="hidden"
                    onChange={handleFileChange}
                  />
                  {selectedFile ? (
                    <div className="flex flex-col items-center gap-2">
                      <FileUp className="h-8 w-8 text-primary" />
                      <p className="text-sm font-medium">{selectedFile.name}</p>
                      <p className="text-xs text-muted-foreground">{(selectedFile.size / 1024).toFixed(1)} KB</p>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        className="gap-1 text-destructive hover:text-destructive"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSelectedFile(null);
                          setImportResult(null);
                          if (fileInputRef.current) {
                            fileInputRef.current.value = "";
                          }
                        }}
                      >
                        <X className="h-3.5 w-3.5" />
                        Xóa file
                      </Button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center gap-2 text-muted-foreground">
                      <Upload className="h-8 w-8" />
                      <p className="text-sm font-medium">Nhấn để chọn file Excel</p>
                      <p className="text-xs">File cần có cột ID hoặc Link/Tiêu đề và cột Nhãn Thủ công.</p>
                    </div>
                  )}
                </div>

                {importResult && (
                  <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
                    <p className="flex items-center gap-2 text-sm font-semibold">
                      <CheckCircle className="h-4 w-4 text-green-600" />
                      Kết quả nhập: <span className="font-normal text-muted-foreground">{importResult.filename}</span>
                    </p>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <Badge className="justify-start border-0 bg-green-500/15 text-green-700 dark:text-green-400">
                        Cập nhật: {importResult.summary.updated}
                      </Badge>
                      <Badge variant="secondary" className="justify-start">
                        Bỏ qua: {importResult.summary.skipped}
                      </Badge>
                      <Badge className="justify-start border-0 bg-amber-500/15 text-amber-700 dark:text-amber-400">
                        Không khớp: {importResult.summary.not_found}
                      </Badge>
                      <Badge className="justify-start border-0 bg-primary/15 text-primary">
                        Dataset: {importResult.summary.dataset_examples}
                      </Badge>
                    </div>
                    {importResult.summary.errors > 0 && (
                      <p className="flex items-start gap-1.5 text-xs text-destructive">
                        <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        Có {importResult.summary.errors} lỗi trong quá trình nhập. Kiểm tra lại định dạng nhãn hoặc dữ liệu bài báo trong file.
                      </p>
                    )}
                    {importResult.dataset_error && (
                      <p className="flex items-start gap-1.5 text-xs text-destructive">
                        <AlertCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                        Chưa ghi được dataset cho mô hình: {importResult.dataset_error}
                      </p>
                    )}
                  </div>
                )}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => resetImportDialog(false)}>
                  Đóng
                </Button>
                <Button onClick={handleImportExcel} disabled={!selectedFile || importing} className="gap-2">
                  {importing ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
                  {importing ? "Đang nhập..." : "Nhập dữ liệu"}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
          <Button variant="outline" className="gap-2" onClick={handleExportExcel}>
            <Download className="h-4 w-4" />
            Xuất Excel
          </Button>
          <Button className="gap-2" onClick={handleSyncDataset} disabled={syncing}>
            {syncing ? <RefreshCcw className="h-4 w-4 animate-spin" /> : <Database className="h-4 w-4" />}
            Đồng bộ Model
          </Button>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-6">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Độ chính xác (Accuracy)</CardTitle>
            <BarChart3 className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.accuracy}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Tính chuẩn xác (Precision)</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.precision ?? 0}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">F1 Score</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.f1_score ?? 0}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Recall</CardTitle>
            <AlertCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.recall ?? 0}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Disease Name Accuracy</CardTitle>
            <Bug className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.disease_accuracy ?? 0}%</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Mẫu đã gán nhãn</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{totalVerified} / {totalArticles}</div>
          </CardContent>
        </Card>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Latest Scan Session - Detailed Stats */}
        <Card className="border-blue-200 dark:border-blue-800 shadow-sm">
          <CardHeader className="bg-blue-50/50 dark:bg-blue-900/20 pb-4 border-b">
            <CardTitle className="text-lg flex items-center gap-2">
              <RefreshCcw className="h-5 w-5 text-blue-600 dark:text-blue-400" />
              Phiên quét gần nhất
            </CardTitle>
            <CardDescription>
              Thông tin chi tiết phiên crawl tin tức gần đây nhất
              {metrics.latest_session?.date ? ` (${metrics.latest_session.date})` : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="pt-6">
            {metrics.latest_session ? (
              <div className="space-y-4">
                {/* Tổng quan */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded-lg border p-3 bg-blue-50/30 dark:bg-blue-900/10">
                    <div className="text-xs text-blue-700 dark:text-blue-400 font-medium mb-1">Tổng bài đã quét</div>
                    <div className="text-2xl font-bold text-blue-700 dark:text-blue-400">
                      {metrics.latest_session.total_checked || 0}
                    </div>
                  </div>
                  <div className="rounded-lg border p-3 bg-indigo-50/30 dark:bg-indigo-900/10">
                    <div className="text-xs text-indigo-700 dark:text-indigo-400 font-medium mb-1">Bài được lưu</div>
                    <div className="text-2xl font-bold text-indigo-700 dark:text-indigo-400">
                      {metrics.latest_session.total || 0}
                    </div>
                  </div>
                </div>

                {/* Phân bổ LLM label */}
                <div>
                  <div className="text-xs font-medium text-muted-foreground mb-2">Phân bổ nhãn LLM:</div>
                  <div className="grid grid-cols-3 gap-3">
                    <div className="rounded border p-2.5 bg-orange-50/30 dark:bg-orange-900/10 text-center">
                      <div className="text-xs text-orange-700 dark:text-orange-400 font-medium">Noise</div>
                      <div className="text-lg font-bold text-orange-700 dark:text-orange-400">{metrics.latest_session.noise_count}</div>
                    </div>
                    <div className="rounded border p-2.5 bg-red-50/30 dark:bg-red-900/10 text-center">
                      <div className="text-xs text-red-700 dark:text-red-400 font-medium">Irrelevant</div>
                      <div className="text-lg font-bold text-red-700 dark:text-red-400">{metrics.latest_session.irrelevant_count}</div>
                    </div>
                    <div className="rounded border p-2.5 bg-yellow-50/30 dark:bg-yellow-900/10 text-center">
                      <div className="text-xs text-yellow-700 dark:text-yellow-400 font-medium">Unsure</div>
                      <div className="text-lg font-bold text-yellow-700 dark:text-yellow-400">{metrics.latest_session.unsure_count}</div>
                    </div>
                  </div>
                </div>

                {/* Thời gian */}
                <div className="grid grid-cols-2 gap-4">
                  <div className="rounded border p-3">
                    <div className="text-xs text-muted-foreground mb-1">Thời gian quét</div>
                    <div className="font-semibold">
                      {metrics.latest_session.duration_seconds >= 60
                        ? `${(metrics.latest_session.duration_seconds / 60).toFixed(1)} phút`
                        : `${metrics.latest_session.duration_seconds} giây`}
                    </div>
                  </div>
                  <div className="rounded border p-3">
                    <div className="text-xs text-muted-foreground mb-1">TB mỗi bài</div>
                    <div className="font-semibold">{metrics.latest_session.avg_time_per_article} giây</div>
                  </div>
                </div>

                {/* Đánh giá thủ công */}
                {metrics.latest_session.verified_count > 0 ? (
                  <div className="border-t pt-4">
                    <div className="text-xs font-medium text-muted-foreground mb-2">Đánh giá thủ công trong phiên:</div>
                    <div className="grid grid-cols-2 gap-4">
                      <div className="rounded-lg border p-3 bg-green-50/30 dark:bg-green-900/10">
                        <div className="text-xs text-green-700 dark:text-green-400 font-medium mb-1">Label đúng</div>
                        <div className="text-2xl font-bold text-green-700 dark:text-green-400">
                          {metrics.latest_session.correct}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {`${(metrics.latest_session.correct / metrics.latest_session.verified_count * 100).toFixed(1)}%`}
                        </div>
                      </div>
                      <div className="rounded-lg border p-3 bg-red-50/30 dark:bg-red-900/10">
                        <div className="text-xs text-red-700 dark:text-red-400 font-medium mb-1">Label sai</div>
                        <div className="text-2xl font-bold text-red-700 dark:text-red-400">
                          {metrics.latest_session.verified_count - metrics.latest_session.correct}
                        </div>
                        <div className="text-xs text-muted-foreground mt-1">
                          {`${((metrics.latest_session.verified_count - metrics.latest_session.correct) / metrics.latest_session.verified_count * 100).toFixed(1)}%`}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}
              </div>
            ) : (
              <div className="text-center text-muted-foreground py-8 text-sm">
                Chưa có phiên quét nào
              </div>
            )}
          </CardContent>
        </Card>

        {/* False Positive Analysis */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Phân tích Hiệu suất Lọc Tổng thể</CardTitle>
            <CardDescription>
              Chi tiết đánh giá thủ công trên tất cả bài báo được phân loại là Relevant
            </CardDescription>
          </CardHeader>
        <CardContent>
          {metrics.confusion_matrix && metrics.confusion_matrix["relevant"] ? (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-lg border p-4">
                  <div className="text-sm text-green-700 dark:text-green-400 font-medium mb-1">True Positive</div>
                  <div className="text-3xl font-bold text-green-700 dark:text-green-400">
                    {metrics.confusion_matrix["relevant"]["relevant"] || 0}
                  </div>
                </div>
                <div className="rounded-lg border p-4">
                  <div className="text-sm text-red-700 dark:text-red-400 font-medium mb-1">False Positive</div>
                  <div className="text-3xl font-bold text-red-700 dark:text-red-400">
                    {(metrics.confusion_matrix["relevant"]["noise"] || 0) + (metrics.confusion_matrix["relevant"]["irrelevant"] || 0)}
                  </div>
                </div>
                <div className="rounded-lg border p-4">
                  <div className="text-sm text-yellow-700 dark:text-yellow-400 font-medium mb-1">Unsure (Chưa rõ)</div>
                  <div className="text-3xl font-bold text-yellow-700 dark:text-yellow-400">
                    {metrics.confusion_matrix["relevant"]["unsure"] || 0}
                  </div>
                </div>
              </div>

              {/* Phân bổ chi tiết */}
              <div className="pt-4 border-t">
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold">Phân bổ nhãn thủ công chi tiết:</h4>
                  {filterLabel && (
                    <Button variant="ghost" size="sm" className="h-6 px-2 text-xs text-muted-foreground" onClick={() => setFilterLabel(null)}>
                      Xóa lọc <X className="h-3 w-3 ml-1" />
                    </Button>
                  )}
                </div>
                <div className="flex flex-wrap gap-4">
                  <Badge
                    variant={filterLabel === "relevant" ? "default" : "outline"}
                    className={`text-sm py-1.5 px-3 cursor-pointer ${filterLabel === "relevant" ? "" : "text-green-700 dark:text-green-400"}`}
                    onClick={() => setFilterLabel(filterLabel === "relevant" ? null : "relevant")}
                  >
                    Relevant: <strong className="ml-1">{metrics.confusion_matrix["relevant"]["relevant"] || 0}</strong>
                  </Badge>
                  <Badge
                    variant={filterLabel === "noise" ? "default" : "outline"}
                    className={`text-sm py-1.5 px-3 cursor-pointer ${filterLabel === "noise" ? "" : "text-orange-700 dark:text-orange-400"}`}
                    onClick={() => setFilterLabel(filterLabel === "noise" ? null : "noise")}
                  >
                    Noise: <strong className="ml-1">{metrics.confusion_matrix["relevant"]["noise"] || 0}</strong>
                  </Badge>
                  <Badge
                    variant={filterLabel === "irrelevant" ? "default" : "outline"}
                    className={`text-sm py-1.5 px-3 cursor-pointer ${filterLabel === "irrelevant" ? "" : "text-red-700 dark:text-red-400"}`}
                    onClick={() => setFilterLabel(filterLabel === "irrelevant" ? null : "irrelevant")}
                  >
                    Irrelevant: <strong className="ml-1">{metrics.confusion_matrix["relevant"]["irrelevant"] || 0}</strong>
                  </Badge>
                  <Badge
                    variant={filterLabel === "unsure" ? "default" : "outline"}
                    className={`text-sm py-1.5 px-3 cursor-pointer ${filterLabel === "unsure" ? "" : "text-yellow-700 dark:text-yellow-400"}`}
                    onClick={() => setFilterLabel(filterLabel === "unsure" ? null : "unsure")}
                  >
                    Unsure: <strong className="ml-1">{metrics.confusion_matrix["relevant"]["unsure"] || 0}</strong>
                  </Badge>
                </div>
              </div>
            </div>
          ) : (
            <div className="text-center text-muted-foreground py-8">
              Chưa có dữ liệu đánh giá thủ công cho các bài báo
            </div>
          )}
        </CardContent>
      </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Danh sách bài báo</CardTitle>
            <CardDescription>Trang {page} - Đang hiển thị {articles.length} bài báo</CardDescription>
          </div>
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead className="w-[32%]">Tiêu đề & Link</TableHead>
                  <TableHead>Nguồn</TableHead>
                  <TableHead>
                    <span className="flex items-center gap-1">
                      Tên dịch bệnh
                    </span>
                  </TableHead>
                  <TableHead>Nhãn LLM</TableHead>
                  <TableHead className="w-[180px]">Nhãn Thủ Công</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      Đang tải...
                    </TableCell>
                  </TableRow>
                ) : articles.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-10 text-muted-foreground">
                      Không có bài báo nào
                    </TableCell>
                  </TableRow>
                ) : (
                  articles.map((article) => {
                    return (
                      <TableRow key={article.id} className={article.is_verified ? "bg-muted/20" : ""}>
                        {/* Tiêu đề */}
                        <TableCell>
                          <a
                            href={article.link}
                            target="_blank"
                            rel="noreferrer"
                            className="text-sm font-medium text-blue-600 dark:text-blue-400 hover:underline line-clamp-2"
                          >
                            {article.title || article.link}
                          </a>
                          {article.is_verified && article.human_label && (
                            <span className="ml-1 inline-flex items-center text-[10px] text-green-600 dark:text-green-400 font-medium">
                              <CheckCircle className="h-3 w-3 mr-0.5" /> Đã gán nhãn
                            </span>
                          )}
                        </TableCell>

                        {/* Nguồn */}
                        <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                          {article.source || "—"}
                        </TableCell>

                        {/* Tên dịch bệnh */}
                        <TableCell>
                          <div className="space-y-2">
                            {article.keywords_matched ? (
                              <div className="flex flex-wrap gap-1">
                                {article.keywords_matched.split(",").map((name, idx) => (
                                  <Badge
                                    key={idx}
                                    variant="outline"
                                    className="text-[10px] bg-orange-50 text-orange-700 border-orange-200 dark:bg-orange-900/20 dark:text-orange-400 dark:border-orange-800"
                                  >
                                    {name.trim()}
                                  </Badge>
                                ))}
                              </div>
                            ) : (
                              <span className="text-xs text-muted-foreground italic block">
                                Không xác định
                              </span>
                            )}

                            {/* Keyword Verification */}
                            <div className="pt-2 border-t border-border/50">
                              <div className="flex flex-col gap-1.5 mb-2">
                                <label className="text-xs font-medium text-muted-foreground">
                                  Đúng keyword?
                                </label>
                                <Select
                                  value={article.keyword_is_correct !== false ? "true" : "false"}
                                  onValueChange={(val) => handleUpdateKeyword(article.id, val === "true", article.corrected_keyword)}
                                >
                                  <SelectTrigger className="w-[120px] h-7 text-xs">
                                    <SelectValue />
                                  </SelectTrigger>
                                  <SelectContent>
                                    <SelectItem value="true">Đúng</SelectItem>
                                    <SelectItem value="false">Sai</SelectItem>
                                  </SelectContent>
                                </Select>
                              </div>
                              {article.keyword_is_correct === false && (
                                <div className="flex flex-col gap-1.5 mt-1">
                                  <div className="flex gap-1">
                                    <Input
                                      className="h-7 text-xs flex-1"
                                      placeholder="Nhập keyword đúng..."
                                      value={article.draft_keyword && article.draft_keyword !== "NONE" ? article.draft_keyword : ""}
                                      onChange={(e) => {
                                        const val = e.target.value;
                                        setArticles(articles.map(a => a.id === article.id ? { ...a, draft_keyword: val } : a));
                                      }}
                                      onKeyDown={(e) => {
                                        if (e.key === 'Enter') {
                                          handleUpdateKeyword(article.id, false, article.draft_keyword);
                                        }
                                      }}
                                    />
                                    <Button
                                      size="sm"
                                      className={`h-7 px-2 text-xs transition-colors ${savedKeywordId === article.id ? 'bg-green-600 hover:bg-green-700 text-white' : ''}`}
                                      onClick={() => handleUpdateKeyword(article.id, false, article.draft_keyword)}
                                      disabled={savingKeywordId === article.id}
                                    >
                                      {savingKeywordId === article.id ? (
                                        <RefreshCcw className="h-3.5 w-3.5 animate-spin" />
                                      ) : savedKeywordId === article.id ? (
                                        <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                      ) : null}
                                      {savedKeywordId === article.id ? 'Đã lưu' : 'Lưu'}
                                    </Button>
                                  </div>
                                  <div className="flex items-center justify-between">
                                    <div className="flex items-center gap-2">
                                      <input
                                        type="checkbox"
                                        id={`no-kw-${article.id}`}
                                        checked={article.draft_keyword === "NONE"}
                                        onChange={(e) => {
                                          const val = e.target.checked ? "NONE" : "";
                                          setArticles(articles.map(a => a.id === article.id ? { ...a, draft_keyword: val } : a));
                                        }}
                                      />
                                      <label htmlFor={`no-kw-${article.id}`} className="text-[10px] text-muted-foreground cursor-pointer">
                                        Không có keyword
                                      </label>
                                    </div>
                                    <span className="text-[10px] font-medium">
                                      {article.corrected_keyword === article.draft_keyword && article.corrected_keyword ? (
                                        <span className="text-green-600 dark:text-green-400 flex items-center gap-1"><CheckCircle className="h-3 w-3" /> Đã cập nhật</span>
                                      ) : (
                                        <span className="text-orange-500 flex items-center gap-1">Chưa cập nhật</span>
                                      )}
                                    </span>
                                  </div>
                                </div>
                              )}
                            </div>
                          </div>
                        </TableCell>

                        {/* Nhãn LLM */}
                        <TableCell>
                          <span
                            className={`px-2 py-1 rounded-full text-xs font-medium ${article.llm_label === "relevant"
                              ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
                              : article.llm_label === "noise"
                                ? "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-400"
                                : article.llm_label === "unsure"
                                  ? "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
                                  : "bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-400"
                              }`}
                          >
                            {article.llm_label}
                          </span>
                        </TableCell>

                        {/* Nhãn Human */}
                        <TableCell>
                          <Select
                            value={article.human_label || undefined}
                            onValueChange={(val) => handleUpdateLabel(article.id, val)}
                          >
                            <SelectTrigger className="w-full h-8 text-xs">
                              <SelectValue placeholder="Chọn nhãn..." />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="relevant">Relevant</SelectItem>
                              <SelectItem value="noise">Noise</SelectItem>
                              <SelectItem value="irrelevant">Irrelevant</SelectItem>
                              <SelectItem value="unsure">Unsure</SelectItem>
                            </SelectContent>
                          </Select>
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>

          {/* Pagination */}
          <div className="flex items-center justify-between mt-4">
            <div className="text-sm text-muted-foreground">
              Hiển thị {(page - 1) * limit + 1} - {Math.min(page * limit, totalArticles)} trong {totalArticles} bài báo
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => Math.max(1, p - 1))}
                disabled={page === 1 || loading}
              >
                Trang trước
              </Button>
              {Array.from({ length: Math.ceil(totalArticles / limit) }, (_, i) => i + 1)
                .filter(p => p === 1 || p === Math.ceil(totalArticles / limit) || Math.abs(p - page) <= 2)
                .reduce<(number | string)[]>((acc, p, idx, arr) => {
                  if (idx > 0 && p - (arr[idx - 1] as number) > 1) acc.push("...");
                  acc.push(p);
                  return acc;
                }, [])
                .map((p, i) =>
                  p === "..." ? (
                    <span key={`ellipsis-${i}`} className="px-1 text-muted-foreground">...</span>
                  ) : (
                    <Button
                      key={`page-${p}`}
                      variant={page === p ? "default" : "outline"}
                      size="sm"
                      className="min-w-[32px] h-8"
                      onClick={() => setPage(p as number)}
                      disabled={loading}
                    >
                      {p}
                    </Button>
                  )
                )}
              <Button
                variant="outline"
                size="sm"
                onClick={() => setPage(p => p + 1)}
                disabled={page * limit >= totalArticles || loading}
              >
                Trang tiếp
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
