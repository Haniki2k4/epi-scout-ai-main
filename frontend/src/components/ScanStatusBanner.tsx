import { useEffect, useRef, useState } from "react";
import { CheckCircle2, Loader2, X } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";

interface ScanStatus {
  scheduler_running: boolean;
  is_scanning: boolean;
  last_run_at: string | null;
  last_run_saved_count: number;
  next_run_at: string | null;
  active_scan_run_id?: string | null;
  active_scan_started_at?: string | null;
}

const ACTIVE_POLL_MS = 5000;
const IDLE_POLL_MS = 30000;

export const ScanStatusBanner = ({ inline = false }: { inline?: boolean }) => {
  const [status, setStatus] = useState<ScanStatus | null>(null);
  const [visible, setVisible] = useState(false);
  const wasScanningRef = useRef(false);
  const { toast } = useToast();

  useEffect(() => {
    let isCancelled = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const scheduleNext = (isScanning: boolean) => {
      timer = setTimeout(fetchStatus, isScanning ? ACTIVE_POLL_MS : IDLE_POLL_MS);
    };

    const fetchStatus = async () => {
      const controller = new AbortController();
      const requestTimeout = setTimeout(() => controller.abort(), 5000);
      try {
        const token = localStorage.getItem("token");
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const response = await fetch("/api/scan-status", {
          headers,
          signal: controller.signal,
          cache: "no-store",
        });
        if (!response.ok || isCancelled) {
          setVisible(false);
          scheduleNext(false);
          return;
        }

        const data: ScanStatus = await response.json();
        setStatus(data);

        if (data.is_scanning) {
          wasScanningRef.current = true;
          setVisible(true);
        } else if (wasScanningRef.current) {
          wasScanningRef.current = false;
          setVisible(true);
          toast({
            title: "Quét hoàn tất",
            description: `Đã lưu ${data.last_run_saved_count} bài viết mới.`,
            duration: 5000,
          });
          setTimeout(() => {
            if (!isCancelled) setVisible(false);
          }, 60000);
        } else if (data.last_run_at) {
          const isRecent = Date.now() - new Date(data.last_run_at).getTime() < 60 * 60 * 1000;
          const dismissedTime = sessionStorage.getItem("dismissed_scan_time");
          if (isRecent && dismissedTime !== data.last_run_at) setVisible(true);
        }

        scheduleNext(data.is_scanning);
      } catch (error) {
        console.error("Lỗi khi kiểm tra trạng thái quét", error);
        if (!isCancelled) {
          setVisible(false);
          scheduleNext(false);
        }
      } finally {
        clearTimeout(requestTimeout);
      }
    };

    void fetchStatus();
    return () => {
      isCancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [toast]);

  const handleDismiss = () => {
    setVisible(false);
    if (status?.last_run_at) {
      sessionStorage.setItem("dismissed_scan_time", status.last_run_at);
    }
  };

  if (!visible || !status) return null;

  if (status.is_scanning) {
    return <div role="status" aria-live="polite" className={inline ? "max-w-full" : "fixed top-[75px] left-1/2 z-[60] -translate-x-1/2 animate-in slide-in-from-top-2 fade-in duration-300"}>
      <div className="flex items-center justify-center gap-2.5 rounded-full border border-orange-400/30 bg-orange-500/90 px-4 py-2 text-white shadow-md backdrop-blur-sm transition-all hover:bg-orange-500">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span className="text-sm font-medium">Hệ thống đang quét tin tức...</span>
      </div>
    </div>;
  }

  if (status.last_run_at) {
    return <div role="status" aria-live="polite" className={inline ? "max-w-full" : "fixed top-[75px] left-1/2 z-[60] -translate-x-1/2 animate-in slide-in-from-top-2 fade-in duration-300"}>
      <div className="flex items-center justify-center gap-2.5 rounded-full border border-emerald-400/30 bg-emerald-500/90 px-4 py-2 text-white shadow-md backdrop-blur-sm transition-all hover:bg-emerald-500">
        <CheckCircle2 className="h-4 w-4" />
        <span className="text-sm font-medium">
          Quét hoàn tất ({new Date(status.last_run_at).toLocaleTimeString()}) - Lưu {status.last_run_saved_count} bài mới.
        </span>
        <button onClick={handleDismiss}
          className="p-1 -mr-1 ml-1 rounded-full transition-colors hover:bg-black/10 focus:outline-none"
          title="Đóng" aria-label="Đóng thông báo quét">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>;
  }

  return null;
};
