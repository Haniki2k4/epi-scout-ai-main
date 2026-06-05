import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CheckCircle2, FileSpreadsheet, Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";

export type ExcelProgressMode = "export" | "import";
export type ExcelProgressStatus = "running" | "success" | "error";

interface ExcelProgressDialogProps {
  open: boolean;
  mode: ExcelProgressMode;
  status: ExcelProgressStatus;
  fileName?: string;
  fileSize?: number;
  message?: string;
  onOpenChange: (open: boolean) => void;
}

const EXPORT_STEPS = ["Chuẩn bị dữ liệu", "Tạo file Excel", "Hoàn tất"];
const IMPORT_STEPS = ["Đọc file", "Phân tích dữ liệu", "Gán nhãn", "Đồng bộ dataset", "Hoàn tất"];
const MAX_SIMULATED_PROGRESS = 90;
const PROGRESS_TICK_MS = 450;

function formatFileSize(size?: number) {
  if (!size) return "Đang xác định";
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(2)} MB`;
}

function getCurrentStepIndex(progress: number, totalSteps: number) {
  if (progress >= 100) return totalSteps - 1;
  return Math.min(totalSteps - 1, Math.floor((progress / 100) * totalSteps));
}

export function ExcelProgressDialog({
  open,
  mode,
  status,
  fileName,
  fileSize,
  message,
  onOpenChange,
}: ExcelProgressDialogProps) {
  const [progress, setProgress] = useState(0);
  const steps = mode === "export" ? EXPORT_STEPS : IMPORT_STEPS;
  const currentStepIndex = getCurrentStepIndex(progress, steps.length);

  useEffect(() => {
    if (status === "success" && open) {
      const timer = window.setTimeout(() => {
        onOpenChange(false);
      }, 2000); // Tự động đóng sau 2 giây
      return () => window.clearTimeout(timer);
    }
  }, [status, open, onOpenChange]);

  useEffect(() => {
    if (!open) {
      setProgress(0);
      return;
    }

    if (status !== "running") {
      setProgress(100);
      return;
    }

    setProgress(8);
    const timer = window.setInterval(() => {
      setProgress((currentProgress) => {
        if (currentProgress >= MAX_SIMULATED_PROGRESS) return currentProgress;

        const remaining = MAX_SIMULATED_PROGRESS - currentProgress;
        const increment = Math.max(0.7, Math.min(7, remaining * 0.18));
        return Math.min(MAX_SIMULATED_PROGRESS, currentProgress + increment);
      });
    }, PROGRESS_TICK_MS);

    return () => window.clearInterval(timer);
  }, [open, status]);

  const title = useMemo(() => {
    if (status === "success") return mode === "export" ? "Xuất Excel thành công" : "Nhập Excel thành công";
    if (status === "error") return mode === "export" ? "Xuất Excel thất bại" : "Nhập Excel thất bại";
    return mode === "export" ? "Đang xuất Excel" : "Đang nhập Excel";
  }, [mode, status]);

  const description = useMemo(() => {
    if (message) return message;
    if (status === "running") return "Vui lòng giữ cửa sổ này mở trong khi hệ thống xử lý.";
    return status === "success" ? "Quá trình xử lý đã hoàn tất." : "Có lỗi xảy ra trong quá trình xử lý.";
  }, [message, status]);

  const statusIcon = {
    running: <Loader2 className="h-5 w-5 animate-spin text-primary" />,
    success: <CheckCircle2 className="h-5 w-5 text-green-600" />,
    error: <AlertCircle className="h-5 w-5 text-destructive" />,
  }[status];

  return (
    <Dialog
      open={open}
      onOpenChange={(nextOpen) => {
        if (status === "running" && !nextOpen) return;
        onOpenChange(nextOpen);
      }}
    >
      <DialogContent className="sm:max-w-[520px]">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            {statusIcon}
            {title}
          </DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>

        <div className="space-y-5">
          <div className="flex items-center gap-3 rounded-lg border bg-muted/30 p-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <FileSpreadsheet className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium">{fileName || "llm_evaluation_dataset.xlsx"}</p>
              <p className="text-xs text-muted-foreground">{formatFileSize(fileSize)}</p>
            </div>
          </div>

          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="font-medium">{steps[currentStepIndex]}</span>
              <span className="tabular-nums text-muted-foreground">{Math.round(progress)}%</span>
            </div>
            <Progress value={progress} className="h-3" aria-label="Tiến trình xử lý Excel" />
          </div>

          <div className="grid gap-2">
            {steps.map((step, index) => {
              const isDone = status === "success" || (status !== "error" && index < currentStepIndex);
              const isCurrent = index === currentStepIndex && status === "running";
              const isError = status === "error" && index === currentStepIndex;

              return (
                <div key={step} className="flex items-center gap-2 text-sm">
                  <span
                    className={cn(
                      "flex h-5 w-5 shrink-0 items-center justify-center rounded-full border text-[10px]",
                      isDone && "border-green-600 bg-green-600 text-white",
                      isCurrent && "border-primary bg-primary/10 text-primary",
                      isError && "border-destructive bg-destructive/10 text-destructive",
                      !isDone && !isCurrent && !isError && "border-muted-foreground/30 text-muted-foreground",
                    )}
                  >
                    {isDone ? <CheckCircle2 className="h-3.5 w-3.5" /> : index + 1}
                  </span>
                  <span
                    className={cn(
                      "text-muted-foreground",
                      (isDone || isCurrent) && "font-medium text-foreground",
                      isError && "font-medium text-destructive",
                    )}
                  >
                    {step}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
