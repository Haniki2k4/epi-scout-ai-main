import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { User, Shield, ShieldAlert, Key, Edit, Plus, RefreshCcw } from "lucide-react";

import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

// Types
interface UserModel {
  id: number;
  username: string;
  role: string;
  is_active: boolean;
  failed_login_attempts: number;
  created_at: string;
}

export default function UserManagement() {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editItem, setEditItem] = useState<UserModel | null>(null);

  // Form states cho Modal Thêm/Sửa
  const [formUsername, setFormUsername] = useState("");
  const [formPassword, setFormPassword] = useState("");
  const [formRole, setFormRole] = useState("user");

  // Form states cho Modal Đổi Trạng thái
  const [isStatusModalOpen, setIsStatusModalOpen] = useState(false);
  const [statusUser, setStatusUser] = useState<UserModel | null>(null);
  const [targetStatus, setTargetStatus] = useState<boolean>(false);
  const [statusReason, setStatusReason] = useState("");
  const [adminPassword, setAdminPassword] = useState("");

  // Fetch Users
  const { data: users = [], isLoading } = useQuery<UserModel[]>({
    queryKey: ["admin_users"],
    queryFn: async () => {
      const res = await fetch("/api/admin/users");
      if (!res.ok) throw new Error("Failed to fetch users");
      const data = await res.json();
      return Array.isArray(data) ? data : [];
    },
  });

  // Mutations
  const toggleUserMutation = useMutation({
    mutationFn: async (data: { id: number; is_active: boolean; reason: string; admin_password: string }) => {
      const res = await fetch(`/api/admin/users/${data.id}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          is_active: data.is_active, 
          reason: data.reason, 
          admin_password: data.admin_password 
        }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Cập nhật thất bại");
      }
      return res.json();
    },
    onSuccess: () => {
      toast.success("Đã cập nhật trạng thái hoạt động");
      queryClient.invalidateQueries({ queryKey: ["admin_users"] });
      closeStatusModal();
    },
    onError: (error) => {
      toast.error(error.message);
      if (error.message.includes("Mật khẩu")) {
        closeStatusModal();
      }
    },
  });

  const saveUserMutation = useMutation({
    mutationFn: async () => {
      const isEditing = !!editItem;
      const url = isEditing ? `/api/admin/users/${editItem.id}` : `/api/admin/users`;
      const method = isEditing ? "PUT" : "POST";
      
      const payload: any = { role: formRole };
      if (!isEditing) payload.username = formUsername;
      if (formPassword) payload.password = formPassword;

      const res = await fetch(url, {
        method,
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || "Lưu thất bại");
      }
      return res.json();
    },
    onSuccess: () => {
      toast.success(editItem ? "Cập nhật thành công!" : "Tạo tài khoản thành công!");
      queryClient.invalidateQueries({ queryKey: ["admin_users"] });
      closeModal();
    },
    onError: (error) => toast.error(error.message),
  });

  // Handlers
  const openStatusModal = (user: UserModel, checked: boolean) => {
    if (!checked && user.username === "epi_scout_admin") {
      toast.error("Không thể khóa tài khoản quản trị chính");
      return;
    }
    setStatusUser(user);
    setTargetStatus(checked);
    setStatusReason("");
    setAdminPassword("");
    setIsStatusModalOpen(true);
  };

  const closeStatusModal = () => {
    setIsStatusModalOpen(false);
    setStatusUser(null);
  };

  const handleToggleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!statusUser) return;
    if (!statusReason.trim()) {
      toast.error("Trường lý do là bắt buộc");
      return;
    }
    if (!adminPassword.trim()) {
      toast.error("Cần mật khẩu Admin để xác thực");
      return;
    }
    toggleUserMutation.mutate({
      id: statusUser.id,
      is_active: targetStatus,
      reason: statusReason,
      admin_password: adminPassword,
    });
  };

  const openModalForNew = () => {
    setEditItem(null);
    setFormUsername("");
    setFormPassword("");
    setFormRole("user");
    setIsModalOpen(true);
  };

  const openModalForEdit = (user: UserModel) => {
    setEditItem(user);
    setFormUsername(user.username);
    setFormPassword(""); // Don't show old password
    setFormRole(user.role);
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
    setEditItem(null);
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!editItem && (!formUsername || !formPassword)) {
      toast.error("Vui lòng nhập tài khoản và mật khẩu!");
      return;
    }
    saveUserMutation.mutate();
  };

  if (isLoading) return <div className="p-8 text-center"><RefreshCcw className="h-6 w-6 animate-spin mx-auto text-primary" /></div>;

  return (
    <Card className="shadow-sm border-border/50">
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>Danh sách Tài khoản</CardTitle>
          <CardDescription>Quản lý quyền truy cập và bảo mật hệ thống</CardDescription>
        </div>
        <Button onClick={openModalForNew} className="gap-2">
          <Plus className="h-4 w-4" /> Tạo Tài khoản
        </Button>
      </CardHeader>
      <CardContent>
        <div className="rounded-md border border-border/50 overflow-hidden">
          <Table>
            <TableHeader className="bg-muted/50">
              <TableRow>
                <TableHead>Tên đăng nhập</TableHead>
                <TableHead>Vai trò</TableHead>
                <TableHead>Trạng thái</TableHead>
                <TableHead className="text-right">Thao tác</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {users.map((u) => (
                <TableRow key={u.id}>
                  <TableCell className="font-medium flex items-center gap-2">
                    <User className="h-4 w-4 text-muted-foreground mr-1" />
                    {u.username}
                  </TableCell>
                  <TableCell>
                    {u.role === "admin" ? (
                      <span className="flex items-center gap-1 text-primary text-xs font-semibold px-2 py-1 bg-primary/10 rounded-full w-fit">
                        <Shield className="h-3 w-3" /> Admin
                      </span>
                    ) : (
                      <span className="text-xs font-medium px-2 py-1 bg-secondary text-secondary-foreground rounded-full">
                        User
                      </span>
                    )}
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      <Switch 
                        checked={u.is_active} 
                        onCheckedChange={(c) => openStatusModal(u, c)}
                        disabled={toggleUserMutation.isPending}
                      />
                      <span className={`text-xs font-medium ${u.is_active ? 'text-green-600' : 'text-muted-foreground'}`}>
                        {u.is_active ? 'Active' : 'Inactive'}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="text-right">
                    <Button variant="ghost" size="sm" onClick={() => openModalForEdit(u)} className="hover:text-blue-700 hover:bg-blue-200">
                      <Edit className="h-4 w-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
              {users.length === 0 && (
                <TableRow>
                  <TableCell colSpan={5} className="text-center py-6 text-muted-foreground">
                    Không có tài khoản nào
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>

      {/* Modal Add/Edit */}
      <Dialog open={isModalOpen} onOpenChange={setIsModalOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleSubmit}>
            <DialogHeader>
              <DialogTitle>{editItem ? "Cập nhật tài khoản" : "Tạo tài khoản mới"}</DialogTitle>
              <DialogDescription>
                {editItem 
                  ? "Cấp lại mật khẩu hoặc đổi role cho người dùng." 
                  : "Chỉ quản trị viên mới có thể tạo người dùng cấp phép."}
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">Tên đăng nhập</label>
                <div className="relative">
                  <User className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    value={formUsername}
                    onChange={(e) => setFormUsername(e.target.value)}
                    disabled={!!editItem} // Cannot edit username
                    placeholder="epi_scout_agent"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {editItem ? "Mật khẩu mới (Bỏ trống nếu không đổi)" : "Mật khẩu khởi tạo"}
                </label>
                <div className="relative">
                  <Key className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    type="password"
                    value={formPassword}
                    onChange={(e) => setFormPassword(e.target.value)}
                    placeholder="••••••"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Vai trò hệ thống (Role)</label>
                <select 
                  className="flex h-10 w-full items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={formRole}
                  onChange={(e) => setFormRole(e.target.value)}
                  disabled={editItem?.username === "epi_scout_admin"}
                >
                  <option value="user">Người dùng (Chỉ quét & xem)</option>
                  <option value="admin">Quản trị viên (Toàn quyền)</option>
                </select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeModal} disabled={saveUserMutation.isPending}>
                Hủy
              </Button>
              <Button type="submit" disabled={saveUserMutation.isPending}>
                {saveUserMutation.isPending && <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />}
                Lưu Thay Đổi
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Modal Status Toggle */}
      <Dialog open={isStatusModalOpen} onOpenChange={setIsStatusModalOpen}>
        <DialogContent className="sm:max-w-md">
          <form onSubmit={handleToggleSubmit}>
            <DialogHeader>
              <DialogTitle>{targetStatus ? "Mở khóa tài khoản" : "Vô hiệu hóa tài khoản"}</DialogTitle>
              <DialogDescription>
                Vui lòng cung cấp lý do và nhập mật khẩu Admin để xác nhận đổi trạng thái cho tài khoản <span className="font-semibold">{statusUser?.username}</span>.
              </DialogDescription>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-destructive">Lý do thay đổi</label>
                <Input
                  value={statusReason}
                  onChange={(e) => setStatusReason(e.target.value)}
                  placeholder="Ví dụ: Cần mở khóa tài khoản, Nhân viên nghỉ việc..."
                  required
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">Mật khẩu Admin</label>
                <div className="relative">
                  <Key className="absolute left-3 top-2.5 h-4 w-4 text-muted-foreground" />
                  <Input
                    className="pl-9"
                    type="password"
                    value={adminPassword}
                    onChange={(e) => setAdminPassword(e.target.value)}
                    placeholder="Nhập mật khẩu của bạn để xác thực"
                    required
                  />
                </div>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={closeStatusModal} disabled={toggleUserMutation.isPending}>
                Hủy
              </Button>
              <Button type="submit" disabled={toggleUserMutation.isPending} variant={targetStatus ? "default" : "destructive"}>
                {toggleUserMutation.isPending && <RefreshCcw className="mr-2 h-4 w-4 animate-spin" />}
                Xác nhận {targetStatus ? "Mở khóa" : "Vô hiệu hóa"}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
