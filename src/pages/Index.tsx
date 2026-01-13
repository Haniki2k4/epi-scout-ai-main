import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Activity, FileText, Search, BarChart3, Database, AlertTriangle } from "lucide-react";
import DashboardOverview from "@/components/DashboardOverview";
import KeywordMonitoring from "@/components/KeywordMonitoring";
import DataExtraction from "@/components/DataExtraction";
import DataAnalysis from "@/components/DataAnalysis";

const Index = () => {
  const [activeTab, setActiveTab] = useState("overview");

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
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <div className="h-2 w-2 rounded-full bg-accent animate-pulse"></div>
              Đang hoạt động
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
