import { useState, useEffect } from "react";
import { CheckCircle2, Loader2, X } from "lucide-react";
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
  const [visible, setVisible] = useState(false);
  const [wasScanning, setWasScanning] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    // Polling every 30 seconds
    const fetchStatus = async () => {
      try {
        const token = localStorage.getItem("token");
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const res = await fetch("/api/scan-status", { headers });
        if (res.ok) {
          const data: ScanStatus = await res.json();
          setStatus(data);

          if (data.is_scanning) {
            setWasScanning(true);
            setVisible(true); // Always show when scanning
          } else {
            // If it just stopped scanning in this session
            if (wasScanning) {
              setWasScanning(false);
              setVisible(true);
              toast({
                title: "Quét hoàn tất",
                description: `Đã lưu ${data.last_run_saved_count} bài viết mới.`,
                duration: 5000,
              });
              // Auto hide success banner after 60s
              setTimeout(() => setVisible(false), 60000);
            } else {
              // Show if last run was very recent (within 1 hour) and we haven't hidden it
              if (data.last_run_at) {
                const runTime = new Date(data.last_run_at).getTime();
                const now = new Date().getTime();
                if (now - runTime < 60 * 60 * 1000) {
                  // Only set visible if we haven't manually closed it yet
                  setVisible((prev) => {
                    if (prev === false) return false;
                    setTimeout(() => setVisible(false), 60000);
                    return true;
                  });
                }
              }
            }
          }
        }
      } catch (error) {
        console.error("Lỗi khi kiểm tra trạng thái quét", error);
      }
    };

    fetchStatus(); // Check immediately on mount (after login)
    const interval = setInterval(fetchStatus, 30000); // 30 seconds

    return () => clearInterval(interval);
  }, [wasScanning, toast]);

  if (!visible || !status) return null;

  if (status.is_scanning) {
    return (
      <div className="mx-4 mt-2 animate-in slide-in-from-top-2 fade-in duration-300">
        <div className="flex items-center justify-center gap-2.5 px-4 py-2 bg-orange-500 text-white rounded-lg shadow-sm">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm font-medium">Hệ thống đang quét tin tức...</span>
        </div>
      </div>
    );
  }

  if (!status.is_scanning && status.last_run_at && visible) {
    return (
      <div className="mx-4 mt-2 animate-in slide-in-from-top-2 fade-in duration-300">
        <div className="flex items-center justify-center gap-2 px-4 py-2 bg-emerald-500 text-white rounded-lg shadow-sm">
          <CheckCircle2 className="h-4 w-4" />
          <span className="text-sm font-medium">
            Quét hoàn tất ({new Date(status.last_run_at).toLocaleTimeString()}) - Lưu {status.last_run_saved_count} bài mới.
          </span>
          <button 
            onClick={() => setVisible(false)} 
            className="p-1 ml-2 hover:bg-emerald-600 rounded-full transition-colors focus:outline-none"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
      </div>
    );
  }

  return null;
};
