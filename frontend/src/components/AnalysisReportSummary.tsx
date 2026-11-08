import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface AnalysisReport {
  report_metadata: { total_articles: number; generated_at: string };
  executive_summary: {
    headline: string; key_findings: string[];
    media_alerts: { disease: string; date: string; zscore: number | null }[];
    epidemiological_alerts: { event_id: number; disease: string; location: string | null; verification_source: string | null }[];
  };
}

export function AnalysisReportSummary() {
  const [hours, setHours] = useState(24);
  const query = useQuery<AnalysisReport>({
    queryKey: ["grounded-analysis-report", hours],
    queryFn: async ({ signal }) => {
      const response = await fetch(`/api/report/analysis?hours=${hours}&include_all_articles=true`, { signal });
      if (!response.ok) throw new Error("Không tải được báo cáo phân tích");
      return response.json();
    },
    staleTime: 5 * 60 * 1000,
    refetchOnWindowFocus: false,
  });
  const download = () => {
    if (!query.data) return;
    const url = URL.createObjectURL(new Blob([JSON.stringify(query.data, null, 2)], { type: "application/json;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `epi-scout-analysis-${hours}h.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return <Card>
    <CardHeader>
      <CardTitle>Tổng quan tín hiệu trong kỳ</CardTitle>
      <CardDescription>Phân tích dựa trên bài hợp lệ và các ghi nhận có nguồn. Lượt bài truyền thông được theo dõi riêng với số ca bệnh.</CardDescription>
      <div className="flex flex-wrap gap-2 pt-2">
        {[24, 48, 72].map(value => <Button key={value} size="sm" variant={hours === value ? "default" : "outline"} onClick={() => setHours(value)}>{value} giờ</Button>)}
        <Button size="sm" variant="outline" disabled={!query.data} onClick={download}>Xuất báo cáo JSON</Button>
      </div>
    </CardHeader>
    <CardContent className="space-y-3 text-sm">
      {query.isPending && <p role="status">Đang tổng hợp dữ liệu...</p>}
      {query.isError && <div role="alert">{query.error.message} <Button variant="outline" onClick={() => void query.refetch()}>Thử lại</Button></div>}
      {query.data && <>
        <p className="font-medium">{query.data.executive_summary.headline}</p>
        <ul className="list-disc pl-5">{query.data.executive_summary.key_findings.map(text => <li key={text}>{text}</li>)}</ul>
        {!query.data.report_metadata.total_articles && <p>Chưa đủ thông tin đánh giá tình hình dịch bệnh trong kỳ.</p>}
        {query.data.executive_summary.media_alerts.map(row => <p key={`${row.disease}-${row.date}`}>Ngưỡng theo dõi truyền thông: {row.disease}, ngày {row.date}, Z-score {row.zscore?.toFixed(2) ?? "chưa tính được"}. Chưa kiểm định p-value.</p>)}
        {query.data.executive_summary.epidemiological_alerts.map(row => <p key={row.event_id}>Sự kiện đã được chuyên viên xác minh: {row.disease} · {row.location || "Chưa xác định địa bàn"} · nguồn xác minh: {row.verification_source || "Chưa xác định"}.</p>)}
        <p className="text-muted-foreground">Không cộng các số ca mới, lũy kế và số liệu dẫn lại thành tổng ca bệnh. Chưa có kiểm định để gán độ tin cậy 95% hoặc p &lt; 0,05 cho toàn báo cáo.</p>
      </>}
    </CardContent>
  </Card>;
}
