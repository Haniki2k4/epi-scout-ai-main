import React, { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import {
  AlertCircle,
  BarChart3,
  Bug,
  CheckCircle,
  Download,
  FileUp,
  RefreshCcw,
  Upload,
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
  is_verified: boolean;
  cases: DiseaseCaseInfo[];    // Danh sách dịch bệnh từ disease_cases
}

interface Metrics {
  accuracy: number;
  precision: number;
  total_verified: number;
  agreement_rate: number;
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
  const [metrics, setMetrics] = useState<Metrics>({ accuracy: 0, precision: 0, total_verified: 0, agreement_rate: 0 });
  const [loading, setLoading] = useState(false);
  const [importDialogOpen, setImportDialogOpen] = useState(false);
  const [importing, setImporting] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [importResult, setImportResult] = useState<ImportResult | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchData();
  }, []);

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
      // Trả về cases[], human_label thực từ DB, llm_label từ event_id
      const aRes = await fetch("/api/evaluation/articles?limit=50", { headers });
      if (aRes.ok) {
        setArticles(await aRes.json());
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
        const errorPayload = await response.json().catch(() => null) as { detail?: string } | null;
        throw new Error(errorPayload?.detail || "Không thể nhập file Excel.");
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
          <Button className="gap-2" onClick={handleExportExcel}>
            <Download className="h-4 w-4" />
            Xuất Dataset (Excel)
          </Button>
        </div>
      </div>

      {/* Metrics Cards */}
      <div className="grid gap-4 md:grid-cols-3">
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
            <CardTitle className="text-sm font-medium">Tổng mẫu đã gán nhãn</CardTitle>
            <CheckCircle className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{metrics.total_verified}</div>
          </CardContent>
        </Card>
      </div>

      {/* Table */}
      <Card>
        <CardHeader>
          <CardTitle>Danh sách bài báo</CardTitle>
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
                          {article.is_verified && (
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
                            <span className="text-xs text-muted-foreground italic">
                              Không xác định
                            </span>
                          )}
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
        </CardContent>
      </Card>
    </div>
  );
}
