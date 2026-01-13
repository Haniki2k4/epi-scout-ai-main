import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { TrendingUp, Download, FileText, BarChart3, Database } from "lucide-react";
import { Badge } from "@/components/ui/badge";

const DataAnalysis = () => {
  // Seasonal flu data (monthly)
  const fluData = [
    { month: "T1", vietnam: 234, global: 45000 },
    { month: "T2", vietnam: 189, global: 38000 },
    { month: "T3", vietnam: 267, global: 52000 },
    { month: "T4", vietnam: 312, global: 61000 },
    { month: "T5", vietnam: 289, global: 55000 },
    { month: "T6", vietnam: 245, global: 48000 },
    { month: "T7", vietnam: 198, global: 39000 },
    { month: "T8", vietnam: 223, global: 43000 },
    { month: "T9", vietnam: 276, global: 54000 },
    { month: "T10", vietnam: 334, global: 68000 },
    { month: "T11", vietnam: 298, global: 59000 },
    { month: "T12", vietnam: 256, global: 51000 },
  ];

  // Comparison data
  const comparisonData = [
    { source: "Google Alerts", articles: 3420, relevant: 2145, accuracy: 62.7, speed: 15 },
    { source: "In-house Script", articles: 5678, relevant: 4892, accuracy: 86.2, speed: 8 },
  ];

  return (
    <div className="space-y-6">
      <Tabs defaultValue="flu" className="space-y-6">
        <TabsList className="grid w-full grid-cols-3">
          <TabsTrigger value="flu">Phân tích cúm mùa</TabsTrigger>
          <TabsTrigger value="comparison">So sánh công cụ</TabsTrigger>
          <TabsTrigger value="report">Báo cáo tự động</TabsTrigger>
        </TabsList>

        {/* Flu Analysis Tab */}
        <TabsContent value="flu" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Xu hướng cúm mùa theo tháng</CardTitle>
              <CardDescription>So sánh dữ liệu Việt Nam và toàn cầu (52,000 bản ghi)</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={400}>
                <LineChart data={fluData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" />
                  <YAxis yAxisId="left" stroke="hsl(var(--chart-1))" />
                  <YAxis yAxisId="right" orientation="right" stroke="hsl(var(--chart-2))" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)"
                    }}
                  />
                  <Legend />
                  <Line 
                    yAxisId="left"
                    type="monotone" 
                    dataKey="vietnam" 
                    stroke="hsl(var(--chart-1))" 
                    strokeWidth={2}
                    name="Việt Nam"
                    dot={{ fill: "hsl(var(--chart-1))", r: 4 }}
                  />
                  <Line 
                    yAxisId="right"
                    type="monotone" 
                    dataKey="global" 
                    stroke="hsl(var(--chart-2))" 
                    strokeWidth={2}
                    name="Toàn cầu"
                    dot={{ fill: "hsl(var(--chart-2))", r: 4 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Nhận xét chính</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-start gap-3">
                  <div className="h-2 w-2 rounded-full bg-chart-1 mt-2"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Đỉnh dịch:</strong> Ca bệnh tăng cao vào tháng 10-11, trùng với mùa lạnh ở Việt Nam.
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="h-2 w-2 rounded-full bg-chart-2 mt-2"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Xu hướng toàn cầu:</strong> Phù hợp với mô hình Bắc bán cầu, đỉnh dịch vào mùa đông.
                  </p>
                </div>
                <div className="flex items-start gap-3">
                  <div className="h-2 w-2 rounded-full bg-chart-3 mt-2"></div>
                  <p className="text-sm text-muted-foreground">
                    <strong className="text-foreground">Sự khác biệt:</strong> Việt Nam có biên độ dao động nhỏ hơn do khí hậu nhiệt đới.
                  </p>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Đề xuất giải pháp</CardTitle>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="p-3 bg-secondary rounded-lg">
                  <p className="text-sm font-medium text-foreground mb-1">Chuẩn hóa báo cáo</p>
                  <p className="text-sm text-muted-foreground">
                    Thống nhất format dữ liệu theo chuẩn WHO ICD-10 để dễ so sánh quốc tế.
                  </p>
                </div>
                <div className="p-3 bg-secondary rounded-lg">
                  <p className="text-sm font-medium text-foreground mb-1">Tích hợp DHIS2</p>
                  <p className="text-sm text-muted-foreground">
                    Sử dụng DHIS2 làm nền tảng tổng hợp dữ liệu từ nhiều nguồn.
                  </p>
                </div>
                <div className="p-3 bg-secondary rounded-lg">
                  <p className="text-sm font-medium text-foreground mb-1">Mô hình dự báo</p>
                  <p className="text-sm text-muted-foreground">
                    Áp dụng ARIMA/SARIMA để dự báo xu hướng dịch theo mùa.
                  </p>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>

        {/* Comparison Tab */}
        <TabsContent value="comparison" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>So sánh hiệu suất công cụ tìm kiếm</CardTitle>
              <CardDescription>Google Alerts vs Scripts tự phát triển</CardDescription>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={comparisonData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis dataKey="source" stroke="hsl(var(--muted-foreground))" />
                  <YAxis stroke="hsl(var(--muted-foreground))" />
                  <Tooltip 
                    contentStyle={{ 
                      backgroundColor: "hsl(var(--card))",
                      border: "1px solid hsl(var(--border))",
                      borderRadius: "var(--radius)"
                    }}
                  />
                  <Legend />
                  <Bar dataKey="articles" fill="hsl(var(--chart-1))" name="Tổng bài viết" radius={[8, 8, 0, 0]} />
                  <Bar dataKey="relevant" fill="hsl(var(--chart-2))" name="Bài viết liên quan" radius={[8, 8, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          <div className="grid gap-6 md:grid-cols-2">
            {comparisonData.map((tool, index) => (
              <Card key={index} className={index === 1 ? "border-l-4 border-l-accent" : ""}>
                <CardHeader>
                  <CardTitle>{tool.source}</CardTitle>
                  {index === 1 && (
                    <Badge className="w-fit bg-accent text-accent-foreground">
                      Được đề xuất
                    </Badge>
                  )}
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <p className="text-sm text-muted-foreground">Tổng bài viết</p>
                      <p className="text-2xl font-bold text-foreground">{tool.articles.toLocaleString()}</p>
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Liên quan</p>
                      <p className="text-2xl font-bold text-foreground">{tool.relevant.toLocaleString()}</p>
                    </div>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-muted-foreground">Độ chính xác</span>
                      <span className="font-medium text-foreground">{tool.accuracy}%</span>
                    </div>
                    <div className="h-2 bg-secondary rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-primary transition-all"
                        style={{ width: `${tool.accuracy}%` }}
                      ></div>
                    </div>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-secondary rounded-lg">
                    <span className="text-sm text-muted-foreground">Thời gian quét</span>
                    <span className="text-sm font-medium text-foreground">{tool.speed} phút</span>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card className="border-l-4 border-l-chart-2">
            <CardHeader>
              <CardTitle>Kết luận & Đề xuất</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <p className="text-muted-foreground">
                <strong className="text-foreground">Scripts tự phát triển</strong> cho kết quả vượt trội với:
              </p>
              <ul className="space-y-2 ml-4">
                <li className="flex items-start gap-2">
                  <TrendingUp className="h-4 w-4 text-accent mt-0.5" />
                  <span className="text-muted-foreground">
                    Độ chính xác cao hơn <strong className="text-foreground">37.5%</strong> (86.2% vs 62.7%)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <TrendingUp className="h-4 w-4 text-accent mt-0.5" />
                  <span className="text-muted-foreground">
                    Thu thập nhiều hơn <strong className="text-foreground">66%</strong> bài viết (5,678 vs 3,420)
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <TrendingUp className="h-4 w-4 text-accent mt-0.5" />
                  <span className="text-muted-foreground">
                    Tốc độ nhanh hơn gần <strong className="text-foreground">2 lần</strong> (8 phút vs 15 phút)
                  </span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </TabsContent>

        {/* Report Tab */}
        <TabsContent value="report" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Hệ thống báo cáo tự động</CardTitle>
              <CardDescription>Tích hợp từ nhiều nguồn dữ liệu giám sát</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 border border-border rounded-lg">
                  <Database className="h-8 w-8 text-primary mb-2" />
                  <h4 className="font-medium text-foreground mb-1">Nguồn dữ liệu</h4>
                  <p className="text-sm text-muted-foreground">TT54, Internet, DHIS2, Social Media</p>
                </div>
                <div className="p-4 border border-border rounded-lg">
                  <BarChart3 className="h-8 w-8 text-accent mb-2" />
                  <h4 className="font-medium text-foreground mb-1">Phân tích AI</h4>
                  <p className="text-sm text-muted-foreground">Tự động phân loại & phát hiện xu hướng</p>
                </div>
                <div className="p-4 border border-border rounded-lg">
                  <FileText className="h-8 w-8 text-chart-2 mb-2" />
                  <h4 className="font-medium text-foreground mb-1">Báo cáo tuần</h4>
                  <p className="text-sm text-muted-foreground">Tự động tạo & gửi email</p>
                </div>
              </div>

              <div className="p-6 bg-secondary rounded-lg space-y-4">
                <h4 className="font-medium text-foreground">Nội dung báo cáo tuần bao gồm:</h4>
                <ul className="space-y-2 text-sm text-muted-foreground ml-4">
                  <li className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5"></div>
                    <span>Tổng quan số liệu: Ca bệnh mới, tử vong, khỏi bệnh</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5"></div>
                    <span>Phân bố theo bệnh, theo địa bàn (tỉnh/thành)</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5"></div>
                    <span>Xu hướng so với tuần trước, tháng trước, cùng kỳ năm ngoái</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5"></div>
                    <span>Cảnh báo ổ dịch mới, bệnh lạ, tăng đột biến</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <div className="h-1.5 w-1.5 rounded-full bg-primary mt-1.5"></div>
                    <span>Tổng hợp tin tức nổi bật từ Internet & mạng xã hội</span>
                  </li>
                </ul>
              </div>

              <Button className="w-full" size="lg">
                <Download className="mr-2 h-4 w-4" />
                Tải báo cáo mẫu (PDF)
              </Button>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-l-primary">
            <CardHeader>
              <CardTitle>Giải pháp DHIS2 Integration</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 md:grid-cols-2">
                <div>
                  <h4 className="font-medium text-foreground mb-2">Ưu điểm</h4>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-accent mt-1.5"></div>
                      <span>Tích hợp nhiều nguồn dữ liệu</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-accent mt-1.5"></div>
                      <span>Báo cáo real-time, dashboard linh hoạt</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-accent mt-1.5"></div>
                      <span>Mở rộng dễ dàng, chi phí hợp lý</span>
                    </li>
                  </ul>
                </div>
                <div>
                  <h4 className="font-medium text-foreground mb-2">Thách thức</h4>
                  <ul className="space-y-2 text-sm text-muted-foreground">
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-destructive mt-1.5"></div>
                      <span>Cần đào tạo nhân sự vận hành</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-destructive mt-1.5"></div>
                      <span>Chuyển đổi dữ liệu hiện có sang DHIS2</span>
                    </li>
                    <li className="flex items-start gap-2">
                      <div className="h-1.5 w-1.5 rounded-full bg-destructive mt-1.5"></div>
                      <span>Đồng bộ với hệ thống cũ (TT54)</span>
                    </li>
                  </ul>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
};

export default DataAnalysis;
