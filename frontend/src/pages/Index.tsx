import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, FileText, Search, BarChart3, Database, AlertTriangle } from "lucide-react";
import DashboardOverview from "@/components/DashboardOverview";
import KeywordMonitoring from "@/components/KeywordMonitoring";
import DataExtraction from "@/components/DataExtraction";
import DataAnalysis from "@/components/DataAnalysis";
import { useAuth } from "@/contexts/AuthContext";
import { Link, useNavigate } from "react-router-dom";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const Index = () => {
  const [activeTab, setActiveTab] = useState("overview");
  const { user, isAuthenticated, logout } = useAuth();
  const navigate = useNavigate();

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="border-b border-border bg-card">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-lg bg-primary flex items-center justify-center">
                <Activity className="h-6 w-6 text-primary-foreground" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-foreground">Hệ Thống Giám Sát Dịch Bệnh</h1>
                <p className="text-sm text-muted-foreground">Disease Surveillance System</p>
              </div>
            </div>
            <div className="flex items-center gap-2 text-sm">
              {!isAuthenticated ? (
                <Link to="/login" className="flex items-center gap-2 hover:text-primary transition-colors text-muted-foreground mr-2 font-medium">
                  Đăng nhập
                </Link>
              ) : (
                <DropdownMenu>
                  <DropdownMenuTrigger className="flex items-center gap-2 hover:bg-primary/10 p-2 py-1 rounded-md transition-colors outline-none cursor-pointer group">
                    <span className="font-medium mr-1 text-foreground hidden sm:block group-hover:text-primary transition-colors">
                      {user?.username}
                    </span>
                    <i className="fa-regular fa-circle-user text-xl text-primary"></i>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="end" className="w-56 mt-2">
                    <DropdownMenuLabel className="font-normal">
                      <div className="flex flex-col space-y-1">
                        <p className="text-sm font-medium leading-none">{user?.username}</p>
                        <p className="text-xs leading-none text-muted-foreground">
                          Vai trò: {user?.role === 'admin' ? 'Quản trị viên' : 'Người dùng'}
                        </p>
                      </div>
                    </DropdownMenuLabel>
                    <DropdownMenuSeparator />
                    {user?.role === "admin" && (
                      <>
                        <DropdownMenuItem 
                          onClick={() => navigate("/admin")} 
                          className="cursor-pointer focus:bg-primary focus:text-primary-foreground"
                        >
                          Đi tới Trang Quản Trị
                        </DropdownMenuItem>
                        <DropdownMenuSeparator />
                      </>
                    )}
                    <DropdownMenuItem className="cursor-pointer focus:bg-primary focus:text-primary-foreground">
                      Cài đặt thông tin
                    </DropdownMenuItem>
                    <DropdownMenuItem 
                      onClick={() => logout()} 
                      className="text-destructive focus:bg-destructive focus:text-destructive-foreground cursor-pointer"
                    >
                      Đăng xuất
                    </DropdownMenuItem>
                  </DropdownMenuContent>
                </DropdownMenu>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="container mx-auto px-4 py-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="space-y-6">
          <TabsList className="grid w-full grid-cols-4 lg:w-auto lg:inline-grid">
            <TabsTrigger value="overview" className="gap-2">
              <BarChart3 className="h-4 w-4" />
              <span className="hidden sm:inline">Tổng quan</span>
            </TabsTrigger>
            <TabsTrigger value="keyword" className="gap-2">
              <Search className="h-4 w-4" />
              <span className="hidden sm:inline">Quét từ khóa</span>
            </TabsTrigger>
            <TabsTrigger value="extraction" className="gap-2">
              <Database className="h-4 w-4" />
              <span className="hidden sm:inline">Trích xuất TT54</span>
            </TabsTrigger>
            <TabsTrigger value="analysis" className="gap-2">
              <FileText className="h-4 w-4" />
              <span className="hidden sm:inline">Phân tích</span>
            </TabsTrigger>
          </TabsList>

          <TabsContent value="overview" className="space-y-6">
            <DashboardOverview />
          </TabsContent>

          <TabsContent value="keyword" className="space-y-6">
            <KeywordMonitoring />
          </TabsContent>

          <TabsContent value="extraction" className="space-y-6">
            <DataExtraction />
          </TabsContent>

          <TabsContent value="analysis" className="space-y-6">
            <DataAnalysis />
          </TabsContent>
        </Tabs>
      </main>
    </div>
  );
};

export default Index;
