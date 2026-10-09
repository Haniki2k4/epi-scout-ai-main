import { useState, useEffect } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChevronRight, Bookmark, Bell, Settings, AlertTriangle } from "lucide-react";
import DashboardOverview from "@/components/DashboardOverview";
import KeywordMonitoring from "@/components/KeywordMonitoring";
import DataAnalysis from "@/components/DataAnalysis";
import BookmarksPage from "@/components/BookmarksPage";
import AlertsPage from "@/components/AlertsPage";
import { GuestBanner } from "@/components/GuestBanner";
import { UserSettingsModal } from "@/components/UserSettingsModal";
import { ScanStatusBanner } from "@/components/ScanStatusBanner";
import { useAuth } from "@/contexts/AuthContext";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Badge } from "@/components/ui/badge";
import { useNewArticleCount, useImportantSignals } from "@/hooks/useNotificationBadge";
import MainSidebar from "@/components/MainSidebar";
import { SidebarInset, SidebarProvider, SidebarTrigger } from "@/components/ui/sidebar";

const Index = () => {
  const { pathname } = useLocation();
  const paths: Record<string, string> = { overview: "/dashboard", keyword: "/news", analysis: "/analytics", report: "/reports", alerts: "/alerts", bookmarks: "/bookmarks" };
  const activeTab = Object.keys(paths).find(key => paths[key] === pathname) ?? "overview";
  const setActiveTab = (tab: string) => navigate(paths[tab] ?? "/dashboard");
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  // Số lượng tín hiệu quan trọng (score >= 2) trong 24h
  const signalCount = useNewArticleCount();
  // Danh sách chi tiết tín hiệu để hiển thị trong dropdown
  const { signals, loading: loadingSignals } = useImportantSignals(isAuthenticated);

  // Chấm đỏ trên tab Cảnh báo cá nhân
  const [hasPersonalFilters, setHasPersonalFilters] = useState(false);

  useEffect(() => {
    if (!isAuthenticated) return;
    const token = localStorage.getItem("token");
    fetch("/api/alerts", {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    })
      .then((r) => r.json())
      .then((data) => {
        setHasPersonalFilters(Array.isArray(data) && data.length > 0);
      })
      .catch(() => {});
  }, [isAuthenticated]);

  const handleSignalClick = (articleId: number) => {
    // Chuyển sang tab Tin tức và tìm bài báo đó (tạm thời chỉ chuyển tab)
    setActiveTab("keyword");
  };

  const pageTitle = { overview: "Tổng quan", keyword: "Tin tức", analysis: "Phân tích tương tác", report: "Xuất báo cáo", alerts: "Cảnh báo cá nhân", bookmarks: "Bài đã lưu" }[activeTab];

  return (
    <SidebarProvider className="app-workspace">
      <MainSidebar hasPersonalFilters={hasPersonalFilters} />
      <SidebarInset className="min-w-0 bg-background">
      <a href="#main-content" className="workspace-skip-link">Đến nội dung chính</a>
      {/* Header */}
      <header className="workspace-header">
        <div className="flex h-full w-full items-center">
          <div className="flex w-full items-center justify-between">
            <div className="flex items-center gap-3">
              <SidebarTrigger aria-label="Thu gọn hoặc mở menu" />
              <span className="hidden text-sm text-muted-foreground sm:inline">Giám sát</span>
              <ChevronRight className="hidden h-4 w-4 text-muted-foreground sm:block" />
              <span className="truncate text-sm font-medium">{pageTitle}</span>
            </div>

            <div className="flex items-center gap-2">
              <ScanStatusBanner inline />
              {/* Dropdown Thông báo tín hiệu quan trọng */}
              {isAuthenticated && (
                <DropdownMenu>
                  <DropdownMenuTrigger asChild>
                    <button aria-label="Thông báo tín hiệu" className="relative p-2 rounded-full hover:bg-secondary transition-colors outline-none">
                      <Bell className="h-5 w-5 text-muted-foreground" /><span className="sr-only">Thông báo tín hiệu</span>
                      {signalCount > 0 && (
                        <span className="absolute top-1.5 right-1.5 flex h-3 w-3">
                          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-red-400 opacity-75"></span>
                          <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500"></span>
                        </span>
                      )}
                    </button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-80 mt-2 p-0 overflow-hidden">
                    <DropdownMenuLabel className="px-4 py-3 border-b bg-muted/30 flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <AlertTriangle className="h-4 w-4 text-primary" />
                        <span>Tín hiệu cảnh báo (24h)</span>
                      </div>
                      <Badge variant="destructive" className="text-[10px]">{signalCount}</Badge>
                    </DropdownMenuLabel>
                    
                    <div className="max-h-[350px] overflow-y-auto">
                      {loadingSignals ? (
                        <div className="p-8 text-center text-xs text-muted-foreground">Đang tải tín hiệu...</div>
                      ) : signals.length === 0 ? (
                        <div className="p-8 text-center text-muted-foreground text-xs italic">
                          Không có tín hiệu nguy cơ cao nào trong 24h qua.
                        </div>
                      ) : (
                        <div className="divide-y divide-border">
                          {signals.map((sig) => (
                            <DropdownMenuItem
                              key={sig.id}
                              className="p-3 cursor-pointer focus:bg-secondary flex flex-col items-start gap-1"
                              onClick={() => handleSignalClick(sig.id)}
                            >
                              <div className="flex items-center gap-2 w-full">
                                <Badge 
                                  variant={sig.outbreak_relevance_score >= 4 ? "destructive" : "default"}
                                  className="text-[9px] h-4 px-1"
                                >
                                  Mức {sig.outbreak_relevance_score}
                                </Badge>
                                <span className="text-[10px] text-muted-foreground ml-auto">
                                  {new Date(sig.published_date).toLocaleTimeString('vi-VN', {hour: '2-digit', minute:'2-digit'})}
                                </span>
                              </div>
                              <div className="text-xs font-semibold line-clamp-2 leading-snug">
                                {sig.title}
                              </div>
                              <div className="text-[10px] text-muted-foreground flex items-center gap-1">
                                <span>{sig.source}</span>
                                <span>•</span>
                                <span className="text-primary">{sig.keywords_matched?.split(',')[0]}</span>
                              </div>
                            </DropdownMenuItem>
                          ))}
                        </div>
                      )}
                    </div>
                    <DropdownMenuSeparator className="m-0" />
                    <button 
                      onClick={() => setActiveTab("keyword")}
                      className="w-full py-2.5 text-xs text-center text-primary font-medium hover:bg-secondary transition-colors"
                    >
                      Xem tất cả bài báo
                    </button>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}

              {/* User Menu */}
              {!isAuthenticated ? (
                <Link to="/login" className="text-sm font-medium hover:text-primary transition-colors px-3 py-2">
                  Đăng nhập
                </Link>
              ) : (
                <DropdownMenu>
                  <DropdownMenuTrigger aria-label="Menu tài khoản" className="flex items-center gap-2 hover:bg-secondary p-1.5 rounded-full transition-colors outline-none group">
                    <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center text-primary border border-primary/20">
                      <span className="text-xs font-bold">{user?.username?.substring(0, 2).toUpperCase()}</span>
                    </div>
                    <span className="hidden text-sm font-medium sm:inline">{user?.username}</span>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 mt-2">
                    <DropdownMenuLabel>
                      <p className="text-sm font-medium">{user?.username}</p>
                      <p className="text-[10px] text-muted-foreground uppercase">{user?.role === 'admin' ? 'Quản trị viên' : user?.role === 'analyst' ? 'Chuyên viên dịch tễ' : 'Người dùng'}</p>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {user?.role === "admin" && (
                      <DropdownMenuItem onClick={() => navigate("/admin")} className="cursor-pointer">
                        Trang quản trị
                      </DropdownMenuItem>
                    )}
                    {(user?.role === "analyst" || user?.role === "admin") && (
                      <DropdownMenuItem onClick={() => navigate("/signals")} className="cursor-pointer">
                        Hàng đợi tín hiệu
                      </DropdownMenuItem>
                    )}                    <DropdownMenuItem onClick={() => setActiveTab("bookmarks")} className="cursor-pointer">
                      <Bookmark className="mr-2 h-4 w-4" /> Bookmark đã lưu
                    </DropdownMenuItem>
                    <UserSettingsModal>
                      <DropdownMenuItem onSelect={(e) => e.preventDefault()} className="cursor-pointer">
                        <Settings className="mr-2 h-4 w-4" /> Cài đặt báo cáo
                      </DropdownMenuItem>
                    </UserSettingsModal>
                    <DropdownMenuSeparator />
                    <DropdownMenuItem onClick={() => logout()} className="text-destructive cursor-pointer">
                      Đăng xuất
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </div>
      </header>
      

      <GuestBanner />

      {/* Main Content */}
      <main id="main-content" className="workspace-content">
        <Tabs value={activeTab === "report" ? "analysis" : activeTab} onValueChange={setActiveTab} className="space-y-6">
          <div className="min-h-[600px]">
            <TabsContent value="overview" className="m-0 focus-visible:outline-none">
              <DashboardOverview />
            </TabsContent>

            <TabsContent value="keyword" className="m-0 focus-visible:outline-none">
              <KeywordMonitoring />
            </TabsContent>

            <TabsContent value="analysis" className="m-0 focus-visible:outline-none">
              <Tabs value={activeTab === "report" ? "report" : "analysis"} onValueChange={setActiveTab} className="space-y-4">
                <TabsList><TabsTrigger value="analysis">Phân tích tương tác</TabsTrigger><TabsTrigger value="report">Xuất báo cáo</TabsTrigger></TabsList>
                <TabsContent value="analysis"><DataAnalysis/></TabsContent>
                <TabsContent value="report"><DataAnalysis showOnlyReport/></TabsContent>
              </Tabs>
            </TabsContent>
            {isAuthenticated && (
              <TabsContent value="alerts" className="m-0 focus-visible:outline-none">
                <AlertsPage />
              </TabsContent>
            )}

            <TabsContent value="bookmarks" className="m-0 focus-visible:outline-none">
              <BookmarksPage />
            </TabsContent>
          </div>
        </Tabs>
      </main>
        </SidebarInset>
    </SidebarProvider>
  );
};

export default Index;
