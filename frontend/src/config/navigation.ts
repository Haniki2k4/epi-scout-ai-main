import { Activity, BarChart3, FileText, Search, Shield, CheckCircle, Database, Tag, Rss, Clock, Users } from "lucide-react";

export const mainNavigation = [
  { label: "Giám sát", items: [
    { label: "Tổng quan", to: "/dashboard", icon: BarChart3 },
    { label: "Tin tức", to: "/news", icon: Search },
    { label: "Phân tích & Báo cáo", to: "/analytics", icon: FileText },
  ] },
  { label: "Xử lý tín hiệu", items: [
    { label: "Hàng đợi tín hiệu", to: "/signals", icon: Activity },
    { label: "Duyệt tín hiệu Cửa B", to: "/signals/gate-b", icon: Shield },
  ] },
];

export const adminNavigation = [
  { label: "Kiểm soát chất lượng", items: [
    { label: "Stage 1 · Chất lượng Scout", to: "/admin/quality/stage-1", icon: Search, admin: true },
    { label: "Stage 2 · Đánh giá LLM", to: "/admin/quality/stage-2", icon: CheckCircle },
  ] },
  { label: "Quản lý dữ liệu", items: [
    { label: "Bài báo", to: "/admin/data/articles", icon: Database, admin: true },
    { label: "Từ khóa bệnh", to: "/admin/data/keywords", icon: Tag, admin: true },
    { label: "Nguồn RSS", to: "/admin/data/rss-sources", icon: Rss, admin: true },
  ] },
  { label: "Vận hành", items: [
    { label: "Lịch quét", to: "/admin/operations/scheduler", icon: Clock, admin: true },
    { label: "Trạng thái hệ thống", to: "/admin/operations/status", icon: Activity, admin: true },
  ] },
  { label: "Hệ thống", items: [
    { label: "Tài khoản", to: "/admin/system/users", icon: Users, admin: true },
  ] },
];

export const legacyAdminPaths: Record<string, string> = {
  users: "/admin/system/users", evaluation: "/admin/quality/stage-2", quality: "/admin/quality/stage-1",
  articles: "/admin/data/articles", resources: "/admin/data/keywords", scheduler: "/admin/operations/scheduler",
};
