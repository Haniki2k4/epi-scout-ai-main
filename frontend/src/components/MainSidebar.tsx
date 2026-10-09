import SidebarBrand from "@/components/SidebarBrand";
import { Bell, Bookmark } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { mainNavigation } from "@/config/navigation";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  SidebarTrigger, useSidebar,
} from "@/components/ui/sidebar";

const personalItems = [
  { label: "Cảnh báo cá nhân", to: "/alerts", icon: Bell, authenticated: true },
  { label: "Bài đã lưu", to: "/bookmarks", icon: Bookmark, authenticated: true },
];

export default function MainSidebar({ hasPersonalFilters = false }: { hasPersonalFilters?: boolean }) {
  const { pathname } = useLocation();
  const { user, isAuthenticated } = useAuth();
  const { setOpenMobile } = useSidebar();
  const isActive = (to: string) => {
    if (to === "/dashboard") return pathname === "/" || pathname === "/dashboard";
    if (to === "/analytics") return pathname === "/analytics" || pathname === "/reports";
    return pathname === to;
  };

  const groups = mainNavigation.map((group) => ({
    ...group,
    items: group.items.filter(() => group.label === "Giám sát" || user?.role === "analyst" || user?.role === "admin"),
  }));
  if (isAuthenticated) groups[0] = { ...groups[0], items: [...groups[0].items, ...personalItems] };

  return <Sidebar collapsible="icon" className="border-border bg-card">
    <SidebarBrand /><SidebarContent className="bg-card pt-3">{groups.map((group) => group.items.length > 0 &&
      <SidebarGroup key={group.label}><SidebarGroupLabel>{group.label}</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>
        {group.items.map((item) => <SidebarMenuItem key={item.to}><SidebarMenuButton asChild isActive={isActive(item.to)} tooltip={item.label}>
          <NavLink to={item.to} end onClick={() => setOpenMobile(false)}><item.icon /><span>{item.label}</span>{item.to === "/alerts" && hasPersonalFilters && <span className="ml-auto h-2 w-2 rounded-full bg-red-500" aria-label="Đang có bộ lọc cảnh báo" />}</NavLink>
        </SidebarMenuButton></SidebarMenuItem>)}
      </SidebarMenu></SidebarGroupContent></SidebarGroup>
    )}</SidebarContent>
    <SidebarFooter className="border-t border-border bg-card"><SidebarTrigger className="w-full" aria-label="Thu gọn hoặc mở rộng menu" /></SidebarFooter>
  </Sidebar>;
}
