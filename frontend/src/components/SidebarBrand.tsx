import { Activity } from "lucide-react";
import { Link } from "react-router-dom";
import { SidebarHeader } from "@/components/ui/sidebar";

export default function SidebarBrand({ isAdmin = false }: { isAdmin?: boolean }) {
  return <SidebarHeader className="h-16 justify-center border-b border-sidebar-border px-3 group-data-[collapsible=icon]:items-center group-data-[collapsible=icon]:px-0">
    <Link to={isAdmin ? "/admin" : "/dashboard"} aria-label={isAdmin ? "EpiScout AI · Quản trị" : "EpiScout AI · Tổng quan"} className="flex items-center gap-3 rounded-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring group-data-[collapsible=icon]:size-8 group-data-[collapsible=icon]:shrink-0 group-data-[collapsible=icon]:justify-center">
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-primary text-primary-foreground"><Activity className="h-5 w-5" /></span>
      <span className="sidebar-brand-copy min-w-0"><span className="block text-sm font-semibold text-primary">EpiScout AI</span><span className="block text-xs text-muted-foreground">{isAdmin ? "Quản trị hệ thống" : "Giám sát dịch bệnh"}</span></span>
    </Link>
  </SidebarHeader>;
}
