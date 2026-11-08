import { ProphetForecast } from "@/types";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface Props {
  data: ProphetForecast[];
  metrics: { mae: number | null; rmse: number | null; eval_method: string; train_days?: number; test_days?: number } | null;
  error?: string;
  intervalWidth: number;
}

export function ForecastNarrative({ data, metrics, error, intervalWidth }: Props) {
  const future = data.filter((row): row is ProphetForecast & { forecast: number; forecast_lower: number; forecast_upper: number } =>
    row.is_future && typeof row.forecast === 'number' && typeof row.forecast_lower === 'number' && typeof row.forecast_upper === 'number');
  const format = (value: number) => value.toLocaleString("vi-VN", { maximumFractionDigits: 2 });
  if (!future.length) return <div role="status" className="mt-4 rounded-lg border p-4 text-sm">{error || "Chưa có đủ thông tin dự báo. Không suy ra xu hướng hoặc số ca bệnh từ dữ liệu này."}</div>;
  const first = future[0];
  const last = future[future.length - 1];
  return <section className="mt-4 space-y-3 rounded-lg border p-4 text-sm" aria-label="Diễn giải dự báo">
    <h3 className="font-semibold">Diễn giải từ kết quả mô hình</h3>
    <p>Giá trị điểm ngày {first.date}: {format(first.forecast)} bài; ngày {last.date}: {format(last.forecast)} bài. Khoảng dự báo {Math.round(intervalWidth * 100)}% thể hiện bất định của lượt bài được ghi nhận.</p>
    {metrics?.mae != null && metrics?.rmse != null ? <p>Kiểm tra trên dữ liệu lịch sử: MAE {format(metrics.mae)} bài/ngày, RMSE {format(metrics.rmse)} bài/ngày. {metrics.eval_method}{metrics.test_days != null ? ` (${metrics.train_days} ngày học, ${metrics.test_days} ngày kiểm tra).` : "."} Chưa có ngưỡng sai số được thẩm định để kết luận độ tin cậy cao.</p> : <p>Chưa có MAE/RMSE kiểm định; chưa đủ thông tin đánh giá sai số dự báo.</p>}
    <Table><TableHeader><TableRow><TableHead>Ngày</TableHead><TableHead>Bài dự kiến</TableHead><TableHead>Giới hạn dưới</TableHead><TableHead>Giới hạn trên</TableHead></TableRow></TableHeader>
      <TableBody>{future.map(row => <TableRow key={row.date}><TableCell>{row.date}</TableCell><TableCell>{format(row.forecast)}</TableCell><TableCell>{format(row.forecast_lower)}</TableCell><TableCell>{format(row.forecast_upper)}</TableCell></TableRow>)}</TableBody>
    </Table>
    <p className="text-muted-foreground">Chưa thực hiện kiểm định ý nghĩa thống kê: không kết luận p &lt; 0,05 từ dải dự báo hay Z-score. Báo chí dẫn lại cùng nguồn có thể làm tăng lượt bài. Gia tăng lượt bài cần đối chiếu nguồn y tế trước khi đánh giá dịch bệnh thực tế.</p>
  </section>;
}
