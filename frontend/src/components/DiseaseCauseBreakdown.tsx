import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

interface Breakdown {
  total_articles: number;
  diseases: { disease_name: string; article_count: number }[];
}

export function DiseaseCauseBreakdown() {
  const [category, setCategory] = useState("virus");
  const [days, setDays] = useState("30");
  const { data, isLoading, error, refetch } = useQuery<Breakdown>({
    queryKey: ["disease-cause-breakdown", category, days],
    queryFn: async () => {
      const response = await fetch(`/api/stats/disease-breakdown?category=${encodeURIComponent(category)}&days=${days}`);
      if (!response.ok) throw new Error("Không tải được thống kê theo nguyên nhân");
      return response.json();
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Chi tiết theo bệnh và tác nhân</CardTitle>
        <CardDescription>
          Giữ riêng từng bệnh, từng loại virus và những tín hiệu chưa rõ nguyên nhân.
          Đây là lượt bài báo, không phải số ca bệnh.
        </CardDescription>
        <div className="flex flex-wrap gap-3 pt-2">
          <div className="flex gap-2" aria-label="Nhóm nguyên nhân">
            {[['virus', 'Bệnh do virus'], ['sốt', 'Sốt theo nguyên nhân']].map(([value, label]) => <Button key={value} variant={category === value ? 'default' : 'outline'} onClick={() => setCategory(value)}>{label}</Button>)}
          </div>
          <div className="flex gap-2" aria-label="Khoảng thời gian">
            {['7', '30', '90'].map(value => <Button key={value} variant={days === value ? 'default' : 'outline'} onClick={() => setDays(value)}>{value} ngày</Button>)}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-3">
        {isLoading ? <p>Đang tải...</p> : error ? (
          <div role="alert">{error.message} <Button variant="outline" onClick={() => void refetch()}>Thử lại</Button></div>
        ) : data ? <>
          <p className="font-medium">Tổng chung trong nhóm: {data.total_articles.toLocaleString("vi-VN")} bài</p>
          <Table>
            <TableHeader><TableRow><TableHead>Bệnh / tác nhân</TableHead><TableHead className="text-right">Số bài</TableHead></TableRow></TableHeader>
            <TableBody>
              {data.diseases.map((disease) => <TableRow key={disease.disease_name}>
                <TableCell>{disease.disease_name}</TableCell>
                <TableCell className="text-right">{disease.article_count.toLocaleString("vi-VN")}</TableCell>
              </TableRow>)}
              {!data.diseases.length && <TableRow><TableCell colSpan={2}>Chưa có bài báo trong khoảng thời gian này.</TableCell></TableRow>}
            </TableBody>
          </Table>
        </> : null}
        <p className="text-sm text-muted-foreground">
          Một bài có thể đề cập nhiều bệnh nên tổng chung có thể nhỏ hơn tổng các dòng.
          Nguyên nhân chỉ được xác định khi dữ liệu nguồn nêu rõ; dữ liệu cũ chưa đủ thông tin vẫn được giữ riêng.
          Nhóm sốt là danh mục giám sát, không khẳng định mọi ca đều có triệu chứng sốt.
        </p>
      </CardContent>
    </Card>
  );
}
