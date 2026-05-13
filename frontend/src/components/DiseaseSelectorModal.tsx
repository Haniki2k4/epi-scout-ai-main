import React, { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Search, AlertTriangle, Check, X } from "lucide-react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { useToast } from "@/components/ui/use-toast";

interface Disease {
  disease_name: string;
  article_count: number;
}

interface ZScoreSpike {
  date: string;
  count: number;
  ma: number;
  zscore: number;
  spike_level: string;
}

interface DiseaseSelectorModalProps {
  selectedDiseases: string[];
  onChange: (diseases: string[]) => void;
  maxSelect?: number;
  triggerButtonText?: string;
  disabled?: boolean;
}

export function DiseaseSelectorModal({
  selectedDiseases,
  onChange,
  maxSelect = 1,
  triggerButtonText = "Chọn dịch bệnh",
  disabled = false,
}: DiseaseSelectorModalProps) {
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [diseases, setDiseases] = useState<Disease[]>([]);
  const [spikes, setSpikes] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    if (open && diseases.length === 0) {
      fetchData();
    }
  }, [open]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [topRes, keywordRes] = await Promise.all([
        fetch("/api/stats/top-diseases?months=12"),
        fetch("/api/keywords")
      ]);

      if (topRes.ok && keywordRes.ok) {
        const topData = await topRes.json();
        const keywordData = await keywordRes.json();

        const topDict: Record<string, number> = {};
        topData.forEach((d: any) => {
          topDict[d.disease_name.toLowerCase()] = d.article_count;
        });

        // Tạo mảng danh sách từ khóa
        const keywordMap = new Map<string, Disease>();
        
        // Thêm tất cả keyword đang active
        keywordData.forEach((k: any) => {
          if (k.is_active) {
            keywordMap.set(k.text.toLowerCase(), {
              disease_name: k.text,
              article_count: topDict[k.text.toLowerCase()] || 0
            });
          }
        });

        // Nếu muốn thêm cả những bệnh trong topData mà không nằm trong keyword (dữ liệu cũ)
        topData.forEach((d: any) => {
          if (!keywordMap.has(d.disease_name.toLowerCase())) {
            keywordMap.set(d.disease_name.toLowerCase(), {
              disease_name: d.disease_name,
              article_count: d.article_count
            });
          }
        });

        const combinedDiseases = Array.from(keywordMap.values());
        setDiseases(combinedDiseases);

        // Kiểm tra z-score cho 10 bệnh có article_count cao nhất
        const spikeMap: Record<string, boolean> = {};
        const sortedForSpikes = [...combinedDiseases].sort((a, b) => b.article_count - a.article_count);
        
        await Promise.all(
          sortedForSpikes.slice(0, 10).map(async (d: Disease) => {
            if (d.article_count === 0) return;
            try {
              const zRes = await fetch(
                `/api/stats/zscore?disease=${encodeURIComponent(d.disease_name)}&days=14`
              );
              if (zRes.ok) {
                const zData: ZScoreSpike[] = await zRes.json();
                const hasSpike = zData.some(
                  (s) => s.spike_level === "alert" || s.spike_level === "danger"
                );
                if (hasSpike) {
                  spikeMap[d.disease_name] = true;
                }
              }
            } catch (e) {
              console.error(e);
            }
          })
        );
        setSpikes(spikeMap);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleToggle = (name: string) => {
    if (selectedDiseases.includes(name)) {
      onChange(selectedDiseases.filter((d) => d !== name));
    } else {
      if (maxSelect === 1) {
        onChange([name]);
        setOpen(false);
        return;
      }
      if (selectedDiseases.length >= maxSelect) {
        toast({
          title: "Giới hạn chọn",
          description: `Chỉ được chọn tối đa ${maxSelect} bệnh.`,
          variant: "destructive",
        });
        return;
      }
      onChange([...selectedDiseases, name]);
    }
  };

  const filteredDiseases = diseases.filter((d) =>
    d.disease_name.toLowerCase().includes(search.toLowerCase())
  );

  // Sắp xếp: có spike lên đầu
  const sortedDiseases = [...filteredDiseases].sort((a, b) => {
    const aSpike = spikes[a.disease_name] ? 1 : 0;
    const bSpike = spikes[b.disease_name] ? 1 : 0;
    if (aSpike !== bSpike) return bSpike - aSpike;
    return b.article_count - a.article_count;
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" className="w-[200px] justify-between" disabled={disabled}>
          <span className="truncate">
            {selectedDiseases.length > 0
              ? selectedDiseases.join(", ")
              : triggerButtonText}
          </span>
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Chọn dịch bệnh</DialogTitle>
        </DialogHeader>
        <div className="space-y-4 py-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm bệnh..."
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <ScrollArea className="h-[300px] rounded-md border p-2">
            {loading ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Đang tải dữ liệu...
              </div>
            ) : sortedDiseases.length === 0 ? (
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                Không tìm thấy bệnh nào.
              </div>
            ) : (
              <div className="space-y-1">
                {sortedDiseases.map((d) => {
                  const isSelected = selectedDiseases.includes(d.disease_name);
                  const isSpike = spikes[d.disease_name];

                  return (
                    <div
                      key={d.disease_name}
                      className={`flex cursor-pointer items-center justify-between rounded-sm px-2 py-2 text-sm transition-colors hover:bg-accent hover:text-accent-foreground ${
                        isSelected ? "bg-accent text-accent-foreground font-medium" : ""
                      }`}
                      onClick={() => handleToggle(d.disease_name)}
                    >
                      <div className="flex items-center gap-2">
                        {isSpike && (
                          <AlertTriangle className="h-4 w-4 text-destructive" />
                        )}
                        <span>{d.disease_name}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs text-muted-foreground">
                          {d.article_count} bài
                        </span>
                        {isSelected && <Check className="h-4 w-4" />}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </ScrollArea>
        </div>
      </DialogContent>
    </Dialog>
  );
}
