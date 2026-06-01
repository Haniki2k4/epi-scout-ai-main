import { Toaster } from "@/components/ui/toaster";
import { Toaster as Sonner } from "@/components/ui/sonner";
import { TooltipProvider } from "@/components/ui/tooltip";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import Index from "./pages/Index";
import NotFound from "./pages/NotFound";
import LoginPage from "./pages/LoginPage";
import AdminInterface from "./pages/AdminInterface";
import { AuthProvider } from "./contexts/AuthContext";
import { PublicRoute, AdminRoute } from "./components/auth/AuthGuard";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 2 * 60 * 1000,   // 2 phút: data vẫn "fresh", không refetch khi remount
      gcTime: 5 * 60 * 1000,      // 5 phút: giữ cache trong memory sau unmount
      refetchOnWindowFocus: false, // Không refetch khi focus lại tab trình duyệt
      retry: 1,                    // Chỉ retry 1 lần khi lỗi mạng
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

            <Route path="/" element={<Index />} />

            <Route element={<AdminRoute />}>
              <Route path="/admin/*" element={<AdminInterface />} />
            </Route>

            {/* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */}
            <Route path="*" element={<NotFound />} />
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </TooltipProvider>
  </QueryClientProvider>
);

export default App;
