import { useState, useEffect } from "react";
import { AlertCircle, CheckCircle2, Loader2, X } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useToast } from "@/components/ui/use-toast";

interface ScanStatus {
  scheduler_running: boolean;
  is_scanning: boolean;
  last_run_at: string | null;
  last_run_saved_count: number;
  next_run_at: string | null;
}

export const ScanStatusBanner = () => {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [visible, setVisible] = useState(true);
  const [wasScanning, setWasScanning] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    // Polling every 60 seconds
    const fetchStatus = async () => {
      try {
        const token = localStorage.getItem("token");
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch("/api/scan-status", { headers });
        if (res.ok) {
          const data = await res.json();
          setStatus(data);

          if (data.is_scanning) {
            setWasScanning(true);
            setVisible(true); // Always show when scanning
          } else if (wasScanning && !data.is_scanning) {
            // Scan just finished
            setWasScanning(false);
            toast({
              title: "Quét hoàn tất",
              description: `Đã lưu ${data.last_run_saved_count} bài viết mới.`,
              duration: 5000,
            });
            // Auto hide success banner after 5s
            setTimeout(() => setVisible(false), 5000);
          }
        }
      } catch (error) {
        console.error("Lỗi khi kiểm tra trạng thái quét", error);
      }
    };

    fetchStatus();
    const interval = setInterval(fetchStatus, 60000); // 1 min

    return () => clearInterval(interval);
  }, [wasScanning, toast]);

  if (!visible || !status) return null;

  if (status.is_scanning) {
    return (
      <div className="fixed top-0 left-0 right-0 z-50 animate-in slide-in-from-top-2">
        <Alert className="rounded-none border-t-0 border-l-0 border-r-0 border-b-primary/20 bg-primary/5 text-primary">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          <AlertTitle className="text-sm font-semibold flex items-center gap-2">
            Hệ thống đang quét tin tức...
          </AlertTitle>
          <AlertDescription className="text-xs">
            Đang tìm kiếm và phân tích các sự kiện dịch tễ mới. Quá trình này có thể mất vài phút.
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  // Show result after scanning finishes (until closed or auto-hidden)
  if (wasScanning === false && status.last_run_at && visible) {
    return (
      <div className="fixed top-0 left-0 right-0 z-50 animate-in slide-in-from-top-2">
        <Alert className="rounded-none border-t-0 border-l-0 border-r-0 border-b-green-500/20 bg-green-500/5 text-green-700">
          <CheckCircle2 className="h-4 w-4 text-green-600" />
          <AlertTitle className="text-sm font-semibold">
            Hoàn thành quét tin tức
          </AlertTitle>
          <AlertDescription className="text-xs flex justify-between items-center">
            <span>
              Cập nhật lúc {new Date(status.last_run_at).toLocaleTimeString()} - Lưu {status.last_run_saved_count} bài viết mới.
            </span>
            <button onClick={() => setVisible(false)} className="hover:bg-green-500/20 p-1 rounded">
              <X className="h-4 w-4" />
            </button>
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return null;
};
