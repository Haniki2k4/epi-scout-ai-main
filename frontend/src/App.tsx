import WorkspaceShell from "./layouts/WorkspaceShell";
import AdminShell from "./layouts/AdminShell";
import SystemStatus from "./pages/SystemStatus";
import UserManagement from "./components/admin/UserManagement";
import EvaluationManagement from "./components/admin/EvaluationManagement";
import QualityReview from "./components/admin/QualityReview";
import ArticleManagement from "./components/admin/ArticleManagement";
import ResourceManagement from "./components/admin/ResourceManagement";
import SchedulerConfig from "./components/admin/SchedulerConfig";
import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import LoginPage from "./pages/LoginPage";
import AdminInterface from "./pages/AdminInterface";
import SignalsPage from "./pages/SignalsPage";
import SignalQueue from "./components/analyst/SignalQueue";
import { AuthProvider } from "./contexts/AuthContext";
import { PublicRoute, AdminRoute, AnalystRoute } from "./components/auth/AuthGuard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,
      gcTime: 5 * 60 * 1000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <TooltipProvider>
      <AuthProvider>
        <Toaster />
        <Sonner />
        <BrowserRouter>
          <Routes>
            <Route element={<PublicRoute />}>
              <Route path="/login" element={<LoginPage />} />
            </Route>

            {["/", "/dashboard", "/news", "/analytics", "/reports", "/alerts", "/bookmarks"].map((path) => (
              <Route key={path} path={path} element={<Index />} />
            ))}

            <Route element={<AnalystRoute />}>
              <Route element={<WorkspaceShell />}>
                <Route path="/signals" element={<SignalsPage />} />
                <Route path="/signals/gate-b" element={<SignalQueue />} />
              </Route>

              <Route element={<AdminShell />}>
                <Route path="/admin/quality/stage-2" element={<EvaluationManagement />} />
                <Route element={<AdminRoute />}>
                  <Route path="/admin" element={<AdminInterface />} />
                  <Route path="/admin/quality/stage-1" element={<QualityReview />} />
                  <Route path="/admin/data/articles" element={<ArticleManagement />} />
                  <Route path="/admin/data/keywords" element={<ResourceManagement section="keywords" />} />
                  <Route path="/admin/data/rss-sources" element={<ResourceManagement section="rss" />} />
                  <Route path="/admin/operations/scheduler" element={<SchedulerConfig />} />
                  <Route path="/admin/operations/status" element={<SystemStatus />} />
                  <Route path="/admin/system/users" element={<UserManagement />} />
                </Route>
              </Route>
            </Route>
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
