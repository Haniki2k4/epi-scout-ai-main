import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { Link } from "react-router-dom";
import { Activity, ArrowLeft, Users, Shield, Database, Clock, Mail } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import UserManagement from "@/components/admin/UserManagement";
import ArticleManagement from "@/components/admin/ArticleManagement";
import ResourceManagement from "@/components/admin/ResourceManagement";
import SchedulerConfig from "@/components/admin/SchedulerConfig";
import EmailConfig from "@/components/admin/EmailConfig";

export default function AdminInterface() {
  const { user } = useAuth();

  return (
    <div className="min-h-screen bg-background p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link to="/" className="p-2 hover:bg-accent rounded-full transition-colors">
              <ArrowLeft className="h-5 w-5 text-muted-foreground" />
            </Link>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-foreground flex items-center gap-2">
                <Shield className="h-6 w-6 text-primary" />
                Quản trị Hệ Thống
              </h1>
              <p className="text-muted-foreground">Epi Scout AI • Admin Panel</p>
            </div>
          </div>
          
          <div className="flex items-center gap-3">
             <div className="text-sm font-medium">Xin chào, {user?.username}</div>
             <div className="h-10 w-10 bg-primary/10 rounded-full flex items-center justify-center">
                <i className="fa-regular fa-circle-user text-xl text-primary"></i>
             </div>
          </div>
        </div>

        {/* Dashboard Cards */}
        <div className="grid gap-6 md:grid-cols-2 lg:grid-cols-3">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Quản lý Người Dùng</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">2</div>
              <p className="text-xs text-muted-foreground mt-1">Tài khoản đang hoạt động</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Quản lý Dữ Liệu RSS</CardTitle>
              <Database className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">Active</div>
              <p className="text-xs text-muted-foreground mt-1">Hệ thống nguồn mở</p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Máy Chủ Quét</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold text-green-500">Đang chạy</div>
              <p className="text-xs text-muted-foreground mt-1">Uvicorn Backend</p>
            </CardContent>
          </Card>
        </div>

        {/* Content Tabs */}
        <div className="mt-8">
          <Tabs defaultValue="users" className="w-full">
            <TabsList className="grid w-full grid-cols-5 max-w-[900px] mb-6">
              <TabsTrigger value="users">Tài Khoản</TabsTrigger>
              <TabsTrigger value="articles">Bài Báo</TabsTrigger>
              <TabsTrigger value="resources">Từ Khóa &amp; RSS</TabsTrigger>
              <TabsTrigger value="scheduler" className="gap-1.5">
                <Clock className="h-3.5 w-3.5" />Lịch Quét
              </TabsTrigger>
              <TabsTrigger value="email" className="gap-1.5">
                <Mail className="h-3.5 w-3.5" />Cấu hình Email
              </TabsTrigger>
            </TabsList>
            <TabsContent value="users" className="mt-0">
              <UserManagement />
            </TabsContent>
            <TabsContent value="articles" className="mt-0">
              <ArticleManagement />
            </TabsContent>
            <TabsContent value="resources" className="mt-0">
              <ResourceManagement />
            </TabsContent>
            <TabsContent value="scheduler" className="mt-0">
              <SchedulerConfig />
            </TabsContent>
            <TabsContent value="email" className="mt-0">
              <EmailConfig />
            </TabsContent>
          </Tabs>
        </div>

      </div>
    </div>
  );
}
