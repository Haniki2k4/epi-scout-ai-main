import { useInfiniteQuery } from "@tanstack/react-query";
import { Article } from "@/types";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

type ArticlePage = { items: Article[]; total: number; skip: number; limit: number };
const caseLabels: Record<string, string> = {
  confirmed: "Ca xác nhận theo nguồn", suspected: "Ca nghi nhiễm",
  deaths: "Tử vong", total_unspecified: "Ca chưa rõ trạng thái",
};
const scopeLabels: Record<string, string> = {
  new: "mới", cumulative: "lũy kế", period_total: "trong kỳ", unknown: "chưa rõ kỳ",
};

function sourceUrl(link: string) {
  try { const url = new URL(link); return /^https?:$/.test(url.protocol) ? url : null; }
  catch { return null; }
}

function publicationTime(value: string) {
  if (!value) return "Chưa xác định thời gian";
  const date = new Date(/Z$|[+-]\d\d:\d\d$/.test(value) ? value : `${value}Z`);
  return Number.isNaN(date.getTime()) ? "Chưa xác định thời gian" : date.toLocaleString("vi-VN");
}

export function ArticleDetailList() {
  const query = useInfiniteQuery({
    queryKey: ["analysis-article-details"],
    initialPageParam: 0,
    queryFn: async ({ pageParam, signal }): Promise<ArticlePage> => {
      const response = await fetch(`/api/articles?limit=5&skip=${pageParam}`, { signal });
      if (!response.ok) throw new Error("Không tải được danh sách bài báo");
      return response.json();
    },
    getNextPageParam: (page) => {
      const next = page.skip + page.items.length;
      return page.items.length && next < page.total ? next : undefined;
    },
  });
  const articles = [...new Map((query.data?.pages.flatMap(page => page.items) || []).map(article => [article.id ?? article.link, article])).values()];
  const total = query.data?.pages[0]?.total ?? 0;

  return <Card>
    <CardHeader>
      <CardTitle>Chi tiết bài báo và bằng chứng</CardTitle>
      <CardDescription>Tất cả thời gian, từ mới đến cũ; hiển thị 5 bài mỗi lượt. Số liệu là từng ghi nhận từ nguồn, không cộng thành tổng ca bệnh.</CardDescription>
    </CardHeader>
    <CardContent className="space-y-4">
      {query.isPending && <p role="status">Đang tải bài báo...</p>}
      {query.data && <p className="text-sm text-muted-foreground">Đang xem {articles.length.toLocaleString("vi-VN")} / {total.toLocaleString("vi-VN")} bài hợp lệ</p>}
      {articles.map((article, index) => {
        const url = sourceUrl(article.link);
        const observations = (article.cases || []).filter(item => item.reported_value != null && item.reported_value > 0 && item.evidence_quote?.trim());
        const diseases = [...new Set((article.cases || []).map(item => item.disease_name).filter(Boolean))];
        const locations = [...new Set((article.cases || []).map(item => item.location).filter(value => value && value !== "unknown"))];
        return <article key={article.id ?? article.link} className="rounded-lg border p-4 space-y-3">
          <h3 className="font-semibold">{index + 1}. {url ? <a href={url.href} target="_blank" rel="noopener noreferrer" className="hover:underline">{article.title}</a> : article.title}</h3>
          <dl className="grid gap-3 text-sm md:grid-cols-2">
            <div><dt className="text-muted-foreground">Nguồn & ngày giờ phát hành</dt><dd>{article.source || url?.hostname || "Chưa xác định nguồn"} · {publicationTime(article.published_date)}</dd></div>
            <div><dt className="text-muted-foreground">Bệnh / tác nhân</dt><dd>{diseases.join(", ") || article.keywords_matched || "Chưa xác định"}</dd></div>
            <div><dt className="text-muted-foreground">Địa bàn dịch tễ</dt><dd>{locations.join("; ") || "Chưa xác định"}</dd></div>
            <div className="md:col-span-2"><dt className="text-muted-foreground">Bằng chứng số liệu</dt><dd className="space-y-2 mt-1">
              {observations.length ? observations.map((item, itemIndex) => <div key={itemIndex}>
                <p>{item.disease_name}: {caseLabels[item.case_type || ""] || "Ghi nhận chưa phân loại"} {item.reported_value?.toLocaleString("vi-VN")} ({scopeLabels[item.count_scope || "unknown"] || "chưa rõ kỳ"}){item.location ? ` · ${item.location}` : ""}</p>
                <blockquote className="border-l-2 pl-3 text-muted-foreground" title={item.evidence_quote || undefined}>“{Array.from(item.evidence_quote || "").slice(0, 150).join("")}”</blockquote>
              </div>) : <p>Chưa có số liệu ca cụ thể kèm trích dẫn.</p>}
            </dd></div>
          </dl>
        </article>;
      })}
      {query.data && !articles.length && <p>Chưa có bài báo hợp lệ.</p>}
      {query.isError && <div role="alert" className="space-y-2"><p>{query.error.message}</p><Button variant="outline" onClick={() => void (query.data ? query.fetchNextPage() : query.refetch())}>Thử lại</Button></div>}
      {query.hasNextPage && <Button variant="outline" disabled={query.isFetchingNextPage} onClick={() => void query.fetchNextPage()}>{query.isFetchingNextPage ? "Đang tải..." : "Xem thêm 5 bài tiếp theo"}</Button>}
    </CardContent>
  </Card>;
}
