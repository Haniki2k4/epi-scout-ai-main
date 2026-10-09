import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Activity, Users } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
type LlmStatus = {
  primary_model: string;
  fallback_model: string;
  current_model: string;
  circuit_state: string;
  fallback_count_today: number;
  primary_error_rate: number;
  last_fallback_at?: string | null;
};

export default function SystemStatus() {
  // Fetch danh sách user để đếm số lượng thực tế
  const { data: userList = [], error: usersError, isLoading: usersLoading, refetch: refetchUsers } = useQuery<{ id: number; is_active: boolean }[]>({
    queryKey: ["admin_users"],
    queryFn: async () => {
      const res = await fetch("/api/admin/users");
      if (!res.ok) throw new Error("Không tải được tài khoản");
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    },
  });
  const activeUserCount = userList.filter((u) => u.is_active).length;

  const {data: llmStatus, error: statusError, isLoading: statusLoading, refetch: refetchStatus} = useQuery<LlmStatus>({
    queryKey: ["admin_llm_status"], queryFn: async()=>{const response=await fetch("/api/admin/llm-status");if(!response.ok)throw new Error("Không tải được trạng thái LLM");return response.json();}, refetchInterval: 30000,
  });
  return <div className="space-y-6">{(usersLoading || statusLoading) && <p role="status">Đang tải…</p>}{(usersError || statusError) && <div role="alert" className="text-destructive">{usersError?.message || statusError?.message}<Button variant="outline" onClick={()=>{void refetchUsers();void refetchStatus();}}>Thử lại</Button></div>}        {/* Dashboard Cards */}
        <div className="status-grid">
          <Card>
            <CardHeader className="flex flex-row items-center justify-between pb-2">
              <CardTitle className="text-sm font-medium">Quản lý Người Dùng</CardTitle>
              <Users className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold">{usersLoading || usersError ? "—" : activeUserCount}</div>
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

</div>;
}
