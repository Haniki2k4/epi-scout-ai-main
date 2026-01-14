import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { Search, Plus, X, Play, Pause, Download, Settings } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Switch } from "@/components/ui/switch";
import { Label } from "@/components/ui/label";
import { ScanResultModal } from "./ScanResultModal";
import { Slider } from "@/components/ui/slider";
import { Article, Keyword } from "@/types";

const KeywordMonitoring = () => {
  const { toast } = useToast();
  const [isScanning, setIsScanning] = useState(false);
  const [newKeyword, setNewKeyword] = useState("");
  const [activeKeywords, setActiveKeywords] = useState<Keyword[]>([]);
  const [articles, setArticles] = useState<Article[]>([]);
  const [scanAll, setScanAll] = useState(false);
  const [unknownArticles, setUnknownArticles] = useState<Article[]>([]);
  const [showModal, setShowModal] = useState(false);
  const [scanMode, setScanMode] = useState<'days' | 'time'>('days');
  const [daysLimit, setDaysLimit] = useState("3");
  const [timeLimit, setTimeLimit] = useState("15");

  // Initial Fetch
  useEffect(() => {
    fetchKeywords();
    fetchArticles();
  }, []);

  const fetchKeywords = async () => {
    try {
      const res = await fetch("/api/keywords");
      if (res.ok) {
        const data = await res.json();
        setActiveKeywords(data);
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

  const handleAddKeyword = async () => {
    if (newKeyword.trim()) {
      try {
        const res = await fetch("/api/keywords", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: newKeyword.trim() }),
        });
        if (res.ok) {
          const keyword = await res.json();
          setActiveKeywords([...activeKeywords, keyword]);
          setNewKeyword("");
          toast({
            title: "Đã thêm từ khóa",
            description: `Từ khóa "${keyword.text}" đã được thêm vào hệ thống.`,
          });
        }
      } catch (e) {
        toast({ title: "Lỗi", description: "Không thể thêm từ khóa.", variant: "destructive" });
      }
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

  const handleStartScan = async () => {
    setIsScanning(true);
    toast({
      title: "Đang quét tin tức...",
      description: "Hệ thống đang tìm kiếm tin tức từ nguồn RSS...",
    });

    try {
      const payload = {
        fetch_unknown: scanAll,
        days_limit: scanMode === 'days' ? parseInt(daysLimit) : 180,
        max_execution_time: scanMode === 'time' ? parseInt(timeLimit) : 0
      };

      const res = await fetch("/api/scan", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const result = await res.json();

        // Refresh articles list
        fetchArticles();

        if (result.saved_trusted_count > 0) {
          toast({
            title: "Quét hoàn tất",
            description: `Đã tự động lưu ${result.saved_trusted_count} bài viết từ nguồn uy tín.`,
          });
        } else {
          if (result.unknown_articles.length === 0) {
            toast({
              title: "Quét hoàn tất",
              description: "Không tìm thấy bài viết mới.",
            });
          }
        }

        if (result.unknown_articles.length > 0) {
          setUnknownArticles(result.unknown_articles);
          setShowModal(true);
        }
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Quét thất bại.", variant: "destructive" });
    } finally {
      setIsScanning(false);
    }
  };

  const handleSaveUnknown = async (articlesToSave: Article[]) => {
    try {
      const res = await fetch("/api/articles/save", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(articlesToSave),
      });
      if (res.ok) {
        toast({ title: "Thành công", description: `Đã lưu ${articlesToSave.length} bài viết.` });
        fetchArticles();
      }
    } catch (e) {
      toast({ title: "Lỗi", description: "Lưu thất bại.", variant: "destructive" });
    }
  };

  const handleAddWhitelist = async (domain: string) => {
    try {
      await fetch("/api/whitelist", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ domain: domain, is_active: true }),
      });
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6">
      <ScanResultModal
        open={showModal}
        onOpenChange={setShowModal}
        unknownArticles={unknownArticles}
        onSaveArticles={handleSaveUnknown}
        onAddWhitelist={handleAddWhitelist}
      />

      {/* Control Panel */}
      <div className="grid gap-6 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Quản lý từ khóa</CardTitle>
            <CardDescription>Thêm từ khóa giám sát vào database</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex gap-2">
              <Input
                placeholder="Nhập từ khóa mới..."
                value={newKeyword}
                onChange={(e) => setNewKeyword(e.target.value)}
                onKeyPress={(e) => e.key === 'Enter' && handleAddKeyword()}
              />
              <Button onClick={handleAddKeyword} size="icon">
                <Plus className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex flex-wrap gap-2">
              {activeKeywords.map((keyword) => (
                <Badge key={keyword.id} variant="secondary" className="gap-1 pr-1 pl-2 py-1 flex items-center">
                  {keyword.text}
                  <button
                    onClick={() => handleDeleteKeyword(keyword.id!)}
                    className="ml-1 hover:bg-destructive/10 hover:text-destructive rounded-full p-0.5 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
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

            {/* UI for Scan Config */}
            <div className="space-y-4 border-t pt-4">
              <div>
                <Label className="mb-2 block">Chế độ quét</Label>
                <div className="flex gap-4">
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio" id="mode-days" name="scanMode"
                      checked={scanMode === 'days'} onChange={() => setScanMode('days')}
                      className="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                    />
                    <Label htmlFor="mode-days">Theo phạm vi ngày</Label>
                  </div>
                  <div className="flex items-center space-x-2">
                    <input
                      type="radio" id="mode-time" name="scanMode"
                      checked={scanMode === 'time'} onChange={() => setScanMode('time')}
                      className="h-4 w-4 border-gray-300 text-primary focus:ring-primary"
                    />
                    <Label htmlFor="mode-time">Theo thời gian chạy</Label>
                  </div>
                </div>
              </div>

              {scanMode === "days" && (
                <div className="space-y-2">
                  <Label>Phạm vi (ngày)</Label>
                  <div className="flex gap-2">
                    {["3", "5", "10"].map(val => (
                      <Button
                        key={val}
                        variant={daysLimit === val ? "default" : "outline"}
                        size="sm"
                        onClick={() => setDaysLimit(val)}
                        className="flex-1"
                      >
                        {val} ngày
                      </Button>
                    ))}
                  </div>
                </div>
              )}

              {scanMode === "time" && (
                <div className="space-y-4">
                  <div className="flex justify-between items-center">
                    <Label>Chạy trong (phút)</Label>
                    <span className="text-sm font-medium text-muted-foreground">{timeLimit} phút</span>
                  </div>
                  <Slider
                    value={[parseInt(timeLimit)]}
                    onValueChange={(val) => setTimeLimit(val[0].toString())}
                    min={5}
                    max={60}
                    step={1}
                    className="w-full"
                  />
                  <div className="flex justify-between text-xs text-muted-foreground">
                    <span>5p</span>
                    <span>15p</span>
                    <span>30p</span>
                    <span>45p</span>
                    <span>60p</span>
                  </div>
                </div>
              )}
            </div>

            <div className="flex items-center gap-4 pt-2">
              <Button
                onClick={handleStartScan}
                className="flex-1"
                disabled={isScanning}
                variant={isScanning ? "destructive" : "default"}
              >
                {isScanning ? (
                  <>
                    <Pause className="mr-2 h-4 w-4" />
                    Đang quét...
                  </>
                ) : (
                  <>
                    <Play className="mr-2 h-4 w-4" />
                    Bắt đầu quét
                  </>
                )}
              </Button>
            </div>

            <div className="grid grid-cols-2 gap-4 pt-2">
              <div className="text-center p-3 bg-secondary rounded-lg">
                <div className="text-2xl font-bold text-foreground">{articles.length}</div>
                <div className="text-xs text-muted-foreground">Bài viết đã lưu</div>
              </div>
              <div className="text-center p-3 bg-secondary rounded-lg">
                {/* Placeholder stats */}
                <div className="text-2xl font-bold text-foreground">6</div>
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
          <div className="space-y-4">
            {articles.length === 0 ? (
              <div className="text-center text-muted-foreground py-4">Chưa có bài viết nào. Hãy thêm từ khóa và quét ngay!</div>
            ) : (
              articles.map((article, index) => (
                <div
                  key={index}
                  className="flex items-start justify-between p-4 border border-border rounded-lg hover:bg-secondary/50 transition-colors"
                >
                  <div className="flex-1 space-y-2">
                    <div className="flex items-start gap-3">
                      <div className="flex-1">
                        <h4 className="font-medium text-foreground">
                          <a href={article.link} target="_blank" rel="noreferrer" className="hover:underline">
                            {article.title}
                          </a>
                        </h4>
                        <p className="text-sm text-muted-foreground mt-1">
                          {article.source} • {new Date(article.published_date).toLocaleString()}
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
