import { ChevronRight, UserRound } from "lucide-react";
import { Outlet, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { adminNavigation } from "@/config/navigation";
import AdminSidebar from "@/components/AdminSidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

export default function AdminShell() {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const group = adminNavigation.find((section) => section.items.some((item) => item.to === pathname));
  const page = group?.items.find((item) => item.to === pathname);

  return <SidebarProvider className="app-workspace">
    <AdminSidebar />
    <SidebarInset className="min-w-0 bg-background">
      <a href="#admin-main" className="workspace-skip-link">Đến nội dung chính</a>
      <header className="workspace-header">
        <div className="flex min-w-0 items-center gap-3">
          <SidebarTrigger aria-label="Thu gọn hoặc mở menu" />
          <span className="hidden text-sm text-muted-foreground sm:inline">{group?.label ?? "Quản trị"}</span>
          <ChevronRight className="hidden h-4 w-4 text-muted-foreground sm:block" />
          <span className="truncate text-sm font-medium">{page?.label ?? "Quản trị hệ thống"}</span>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <span className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-primary"><UserRound className="h-4 w-4" /></span>
          <span className="hidden text-sm sm:inline">{user?.username}</span>
        </div>
      </header>
      <main id="admin-main" className="workspace-content"><Outlet /></main>
    </SidebarInset>
  </SidebarProvider>;
}
