import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/contexts/AuthContext";
import { Link } from "react-router-dom";
import { Activity, ArrowLeft, Users, Shield, Database, Clock, CheckCircle } from "lucide-react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import UserManagement from "@/components/admin/UserManagement";
import EvaluationManagement from "@/components/admin/EvaluationManagement";
import ArticleManagement from "@/components/admin/ArticleManagement";
import ResourceManagement from "@/components/admin/ResourceManagement";
import SchedulerConfig from "@/components/admin/SchedulerConfig";
import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

type LlmStatus = {
  primary_model: string;
  fallback_model: string;
  current_model: string;
  circuit_state: string;
  fallback_count_today: number;
  primary_error_rate: number;
  last_fallback_at?: string | null;
};

export default function AdminInterface() {
  const { user } = useAuth();
  const [llmStatus, setLlmStatus] = useState<LlmStatus | null>(null);

  // Fetch danh sách user để đếm số lượng thực tế
  const { data: userList = [] } = useQuery<{ id: number; is_active: boolean }[]>({
    queryKey: ["admin_users"],
    queryFn: async () => {
      const res = await fetch("/api/admin/users");
      if (!res.ok) return [];
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    },
  });
  const activeUserCount = userList.filter((u) => u.is_active).length;

  useEffect(() => {
    const fetchLlmStatus = async () => {
      try {
        const res = await fetch("/api/admin/llm-status");
        if (res.ok) setLlmStatus(await res.json());
      } catch {
        setLlmStatus(null);
      }
    };
    fetchLlmStatus();
  }, []);

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
        <div className="grid gap-6 md:grid-cols-2">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Quản lý Người Dùng</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{activeUserCount}</div>
              <p className="text-xs text-muted-foreground mt-1">
                Tài khoản đang hoạt động / {userList.length} tổng cộng
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">LLM Fallback</CardTitle>
              <Activity className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              {llmStatus ? (
                <div className="space-y-2">
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Mô hình chính:</span>
                    <span className={`font-semibold ${llmStatus.circuit_state === 'CLOSED' ? 'text-green-600' : 'text-muted-foreground'}`} title={llmStatus.primary_model}>
                      {llmStatus.primary_model?.split('/').pop() || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between items-center text-sm">
                    <span className="text-muted-foreground">Mô hình dự phòng:</span>
                    <span className={`font-semibold ${llmStatus.circuit_state === 'OPEN' ? 'text-amber-600' : 'text-muted-foreground'}`} title={llmStatus.fallback_model}>
                      {llmStatus.fallback_model?.split('/').pop() || 'N/A'}
                    </span>
                  </div>
                  <div className="pt-2 mt-2 border-t text-xs text-muted-foreground flex justify-between">
                    <span>Circuit: <strong className={llmStatus.circuit_state === 'OPEN' ? 'text-red-500' : 'text-green-500'}>{llmStatus.circuit_state}</strong></span>
                    <span>Lỗi: {(llmStatus.primary_error_rate * 100).toFixed(1)}% ({llmStatus.fallback_count_today} fallback)</span>
                  </div>
                </div>
              ) : (
                <div className="text-sm text-muted-foreground">Chưa có dữ liệu</div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Content Tabs */}
        <div className="mt-8">
          <Tabs defaultValue="users" className="w-full">
            <TabsList className="grid w-full grid-cols-5 max-w-[850px] mb-6">
              <TabsTrigger value="users">Tài Khoản</TabsTrigger>
              <TabsTrigger value="evaluation" className="gap-1.5"><CheckCircle className="h-3.5 w-3.5" /> Đánh giá LLM</TabsTrigger>
              <TabsTrigger value="articles">Bài Báo</TabsTrigger>
              <TabsTrigger value="resources">Từ Khóa &amp; RSS</TabsTrigger>
              <TabsTrigger value="scheduler" className="gap-1.5">
                <Clock className="h-3.5 w-3.5" />Lịch Quét
              </TabsTrigger>
            </TabsList>
            <TabsContent value="users" className="mt-0">
              <UserManagement />
            </TabsContent>
            <TabsContent value="evaluation" className="mt-0">
              <EvaluationManagement />
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
          </Tabs>
        </div>

      </div>
    </div>
  );
}
