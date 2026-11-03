import { Navigate, Outlet } from "react-router-dom";
import { useAuth } from "@/contexts/AuthContext";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

function LoadingScreen() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-background">
      <Loader2 className="h-8 w-8 animate-spin text-primary" />
    </div>
  );
}

function AuthCheckFailure() {
  const { retryAuthCheck, isLoading } = useAuth();
  return (
    <div className="flex min-h-screen flex-col items-center justify-center space-y-4 p-4 text-center">
      <p role="alert" className="font-medium text-destructive">Không thể kết nối đến máy chủ xác thực.</p>
      <Button onClick={() => void retryAuthCheck()} disabled={isLoading}>
        {isLoading ? "Đang kết nối…" : "Thử lại kết nối"}
      </Button>
    </div>
  );
}

export const ProtectedRoute = () => {
  const { isAuthenticated, isLoading, authCheckFailed } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (authCheckFailed) return <AuthCheckFailure />;
  return isAuthenticated ? <Outlet /> : <Navigate to="/login" replace />;
};

export const AdminRoute = () => {
  const { user, isAuthenticated, isLoading, authCheckFailed } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (authCheckFailed) return <AuthCheckFailure />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.role !== "admin") return <Navigate to="/" replace />;
  return <Outlet />;
};

export const AnalystRoute = () => {
  const { user, isAuthenticated, isLoading, authCheckFailed } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (authCheckFailed) return <AuthCheckFailure />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  return user?.role === "analyst" || user?.role === "admin" ? <Outlet /> : <Navigate to="/" replace />;
};

export const PublicRoute = () => {
  const { isAuthenticated, isLoading, authCheckFailed } = useAuth();
  if (isLoading) return <LoadingScreen />;
  if (authCheckFailed) return <AuthCheckFailure />;
  return isAuthenticated ? <Navigate to="/" replace /> : <Outlet />;
};
