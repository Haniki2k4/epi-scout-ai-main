import { Link } from "react-router-dom";
import { Info } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";

export function GuestBanner() {
  const { isGuest } = useAuth();

  if (!isGuest) return null;

  return (
    <div className="border-b border-amber-200 bg-amber-50 text-amber-900">
      <div className="container mx-auto flex items-center gap-2 px-4 py-2 text-sm">
        <Info className="h-4 w-4 shrink-0" />
        <span className="min-w-0">
          Bạn đang xem ở chế độ guest.{" "}
          <Link to="/login" className="font-medium underline underline-offset-2">
            Đăng nhập
          </Link>{" "}
          để sử dụng đầy đủ tính năng.
        </span>
      </div>
    </div>
  );
}
