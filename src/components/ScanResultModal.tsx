import { useState } from "react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Article } from "@/types";
import { Badge } from "@/components/ui/badge";
import { ExternalLink, ShieldAlert, PlusCircle } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface ScanResultModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  unknownArticles: Article[];
  onSaveArticles: (articles: Article[]) => void;
  onAddWhitelist: (domain: string) => void;
}

export function ScanResultModal({
  open,
  onOpenChange,
  unknownArticles,
  onSaveArticles,
  onAddWhitelist,
}: ScanResultModalProps) {
  const [selectedLinks, setSelectedLinks] = useState<Set<string>>(new Set());
  const { toast } = useToast();

  const handleToggle = (link: string) => {
    const newSelected = new Set(selectedLinks);
    if (newSelected.has(link)) {
      newSelected.delete(link);
    } else {
      newSelected.add(link);
    }
    setSelectedLinks(newSelected);
  };

  const handleSave = () => {
    const articlesToSave = unknownArticles.filter((a) => selectedLinks.has(a.link));
    onSaveArticles(articlesToSave);
    onOpenChange(false);
  };

  const handleAddWhitelist = (domain: string) => {
    onAddWhitelist(domain);
    toast({
      title: "Đã thêm vào Whitelist",
      description: `Domain ${domain} đã được thêm vào danh sách tin cậy.`,
    });
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl max-h-[80vh] flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <ShieldAlert className="w-5 h-5 text-yellow-500" />
            Phát hiện nguồn chưa xác thực
          </DialogTitle>
          <DialogDescription>
            Hệ thống tìm thấy {unknownArticles.length} bài viết từ các nguồn chưa có trong Whitelist.
            Vui lòng chọn bài viết để lưu hoặc thêm nguồn vào danh sách tin cậy.
          </DialogDescription>
        </DialogHeader>

        <ScrollArea className="flex-1 pr-4 py-4">
          <div className="space-y-4">
            {unknownArticles.map((article, index) => (
              <div
                key={index}
                className="flex items-start gap-3 p-3 border rounded-lg hover:bg-muted/50 transition-colors"
              >
                <Checkbox
                  checked={selectedLinks.has(article.link)}
                  onCheckedChange={() => handleToggle(article.link)}
                  className="mt-1"
                />
                <div className="flex-1 space-y-1">
                  <h4 className="font-medium text-sm leading-tight">
                    <a
                      href={article.link}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="hover:underline flex items-center gap-1"
                    >
                      {article.title}
                      <ExternalLink className="w-3 h-3 text-muted-foreground" />
                    </a>
                  </h4>
                  <p className="text-xs text-muted-foreground line-clamp-2">
                    {article.summary}
                  </p>
                  <div className="flex items-center justify-between pt-1">
                    <div className="flex gap-2 text-xs text-muted-foreground">
                      <span>{article.source}</span>
                      <span>•</span>
                      <span>{new Date(article.published_date).toLocaleDateString()}</span>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs gap-1 text-primary"
                      onClick={() => handleAddWhitelist(article.source)}
                    >
                      <PlusCircle className="w-3 h-3" />
                      Thêm Whitelist
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </ScrollArea>

        <DialogFooter className="flex items-center justify-between sm:justify-between">
          <div className="text-sm text-muted-foreground">
            Đã chọn: {selectedLinks.size}
          </div>
          <div className="flex gap-2">
            <Button variant="outline" onClick={() => onOpenChange(false)}>
              Bỏ qua tất cả
            </Button>
            <Button onClick={handleSave} disabled={selectedLinks.size === 0}>
              Lưu bài đã chọn
            </Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
