import SidebarBrand from "@/components/SidebarBrand";
import { ArrowLeft } from "lucide-react";
import { NavLink, useLocation } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { adminNavigation } from "@/config/navigation";
import {
  Sidebar, SidebarContent, SidebarFooter, SidebarGroup, SidebarGroupContent,
  SidebarGroupLabel, SidebarMenu, SidebarMenuButton, SidebarMenuItem,
  SidebarTrigger, useSidebar,
} from "@/components/ui/sidebar";

export default function AdminSidebar() {
  const { pathname } = useLocation();
  const { user } = useAuth();
  const { setOpenMobile } = useSidebar();
  const groups = adminNavigation.map((group) => ({
    ...group,
    items: group.items.filter((item) => !("admin" in item && item.admin) || user?.role === "admin"),
  }));

  return <Sidebar collapsible="icon" className="border-border bg-card">
    <SidebarBrand isAdmin /><SidebarContent className="bg-card pt-3">{groups.map((group) => group.items.length > 0 &&
      <SidebarGroup key={group.label}><SidebarGroupLabel>{group.label}</SidebarGroupLabel><SidebarGroupContent><SidebarMenu>
        {group.items.map((item) => <SidebarMenuItem key={item.to}><SidebarMenuButton asChild isActive={pathname === item.to} tooltip={item.label}>
          <NavLink to={item.to} end onClick={() => setOpenMobile(false)}><item.icon /><span>{item.label}</span></NavLink>
        </SidebarMenuButton></SidebarMenuItem>)}
      </SidebarMenu></SidebarGroupContent></SidebarGroup>
    )}</SidebarContent>
    <SidebarFooter className="border-t border-border bg-card"><SidebarMenu>
      <SidebarMenuItem><SidebarMenuButton asChild tooltip="Về trang giám sát"><NavLink to="/dashboard" onClick={() => setOpenMobile(false)}><ArrowLeft /><span>Về trang giám sát</span></NavLink></SidebarMenuButton></SidebarMenuItem>
      <SidebarMenuItem><SidebarTrigger className="w-full" aria-label="Thu gọn hoặc mở rộng menu quản trị" /></SidebarMenuItem>
    </SidebarMenu></SidebarFooter>
  </Sidebar>;
}
