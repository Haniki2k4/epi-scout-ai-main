import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Upload, Download, Database, Search, ChevronLeft, ChevronRight, User, Shield } from "lucide-react";
import { useToast } from "@/components/ui/use-toast";
import { Article } from "@/types";

const DataExtraction = () => {
  const { toast } = useToast();
  // Login State
  const [isLoggedIn, setIsLoggedIn] = useState(false);
  const [userRole, setUserRole] = useState<"staff" | "demo" | null>(null);
  const [showLoginModal, setShowLoginModal] = useState(true);

  // Data State
  const [articles, setArticles] = useState<Article[]>([]);
  const [page, setPage] = useState(1);
  const [limit] = useState(10);
  const [keyword, setKeyword] = useState("");

  const handleLogin = (role: "staff" | "demo") => {
    setUserRole(role);
    setIsLoggedIn(true);
    setShowLoginModal(false);
    if (role === "staff") {
      fetchArticles(1);
    }
  };

  const fetchArticles = async (p: number) => {
    try {
      // In a real app, we would append ?keyword={keyword} to the API
      // For now, simple pagination
      const res = await fetch(`/api/articles?skip=${(p - 1) * limit}&limit=${limit}`);
      if (res.ok) {
        const data = await res.json();
        setArticles(data);
      }
    } catch (e) {
      console.error("Fetch error", e);
    }
  };

  useEffect(() => {
    if (userRole === "staff") {
      fetchArticles(page);
    }
  }, [page, userRole]);


  if (!isLoggedIn) {
    return (
      <Dialog open={showLoginModal} onOpenChange={setShowLoginModal}>
        <DialogContent className="sm:max-w-[425px]">
          <DialogHeader>
            <DialogTitle>Đăng nhập hệ thống TT54</DialogTitle>
            <DialogDescription>
              Vui lòng chọn vai trò để truy cập chức năng trích xuất dữ liệu.
            </DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-2 gap-4 py-4">
            <Button variant="outline" className="h-24 flex flex-col gap-2" onClick={() => handleLogin("demo")}>
              <User className="h-8 w-8 text-muted-foreground" />
              <span>Người dùng Demo</span>
            </Button>
            <Button className="h-24 flex flex-col gap-2" onClick={() => handleLogin("staff")}>
              <Shield className="h-8 w-8" />
              <span>Nhân viên Y tế</span>
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center bg-secondary/50 p-4 rounded-lg">
        <div className="flex items-center gap-2">
          {userRole === 'staff' ? <Shield className="h-5 w-5 text-primary" /> : <User className="h-5 w-5 text-muted-foreground" />}
          <span className="font-medium">
            {userRole === 'staff' ? 'Nhân viên Y tế (Đầy đủ quyền)' : 'Tài khoản Demo (Hạn chế)'}
          </span>
        </div>
        <Button variant="ghost" size="sm" onClick={() => setShowLoginModal(true)}>Đổi tài khoản</Button>
      </div>

      {userRole === 'demo' ? (
        <DemoView />
      ) : (
        <StaffView
          articles={articles}
          page={page}
          setPage={setPage}
          keyword={keyword}
          setKeyword={setKeyword}
          onExtract={() => fetchArticles(page)}
        />
      )}
    </div>
  );
};

const StaffView = ({ articles, page, setPage, keyword, setKeyword, onExtract }: any) => {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Dữ liệu Báo cáo TT54 (Realtime)</CardTitle>
        <CardDescription>Danh sách tin tức và ca bệnh được trích xuất từ hệ thống giám sát</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Tìm kiếm bài báo..."
              className="pl-8"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
            />
          </div>
          <Button onClick={onExtract}>Làm mới</Button>
        </div>

        <div className="rounded-md border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Tiêu đề bài viết</TableHead>
                <TableHead>Nguồn</TableHead>
                <TableHead>Ngày đăng</TableHead>
                <TableHead>Tag</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {articles.map((article: Article) => (
                <TableRow key={article.id}>
                  <TableCell className="font-medium">
                    <a href={article.link} target="_blank" className="hover:underline">
                      {article.title}
                    </a>
                  </TableCell>
                  <TableCell>{article.source}</TableCell>
                  <TableCell>{new Date(article.published_date).toLocaleDateString('vi-VN')}</TableCell>
                  <TableCell>{article.keywords_matched}</TableCell>
                </TableRow>
              ))}
              {articles.length === 0 && (
                <TableRow>
                  <TableCell colSpan={4} className="text-center h-24 text-muted-foreground">
                    Không có dữ liệu. Hãy thực hiện quét tin tức trước.
                  </TableCell>
                </TableRow>
              )}
            </TableBody>
          </Table>
        </div>

        {/* Pagination */}
        <div className="flex items-center justify-end space-x-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(Math.max(1, page - 1))}
            disabled={page === 1}
          >
            <ChevronLeft className="h-4 w-4" />
            Trước
          </Button>
          <div className="text-sm font-medium">Trang {page}</div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => setPage(page + 1)}
            disabled={articles.length < 10}
          >
            Sau
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}

const DemoView = () => {
  const { toast } = useToast();
  const [isExtracting, setIsExtracting] = useState(false);

  const handleExtract = () => {
    setIsExtracting(true);
    setTimeout(() => {
      setIsExtracting(false);
      toast({
        title: "Trích xuất Demo thành công",
        description: "Dữ liệu mẫu đã được tải về.",
      });
    }, 1500);
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>Trích xuất dữ liệu Thông tư 54 (Demo)</CardTitle>
        <CardDescription>
          Phiên bản Demo giới hạn tính năng. Chỉ cho phép tải template mẫu.
        </CardDescription>
      </CardHeader>
      <CardContent className="space-y-6">
        <div className="p-8 border-2 border-dashed rounded-lg flex flex-col items-center justify-center gap-4 text-center">
          <div className="h-16 w-16 bg-muted rounded-full flex items-center justify-center">
            <Database className="h-8 w-8 text-muted-foreground" />
          </div>
          <div>
            <h3 className="font-medium text-lg">Dữ liệu mẫu tuần 24/2024</h3>
            <p className="text-sm text-muted-foreground">Bao gồm 1,247 bản ghi mô phỏng</p>
          </div>
          <Button onClick={handleExtract} disabled={isExtracting}>
            {isExtracting ? "Đang xử lý..." : "Tải về báo cáo mẫu (Excel)"}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export default DataExtraction;
