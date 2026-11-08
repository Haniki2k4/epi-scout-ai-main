import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { llmApi, type Revision } from "@/lib/llmEvaluationApi";
import { llmEvalKeys } from "@/lib/queryKeys";
import { Button } from "@/components/ui/button";

export default function ReviewHistory({ itemId }: { itemId: number }) {
  const [isOpen, setIsOpen] = useState(false);
  const historyQuery = useQuery({
    queryKey: llmEvalKeys.detail(itemId),
    queryFn: ({ signal }) => llmApi.detail(itemId, signal),
    staleTime: 120_000,
    enabled: isOpen,
  });
  const rows: Revision[] | undefined = historyQuery.data?.revisions;

  return (
    <details open={isOpen} onToggle={(event) => setIsOpen(event.currentTarget.open)}>
      <summary className="cursor-pointer font-medium text-primary">Lịch sử sửa nhãn</summary>
      {historyQuery.isLoading && <p role="status">Đang tải…</p>}
      {historyQuery.error && (
        <div role="alert">
          {historyQuery.error instanceof Error ? historyQuery.error.message : "Không tải được lịch sử"}
          <Button variant="outline" onClick={() => void historyQuery.refetch()}>Thử lại</Button>
        </div>
      )}
      {rows?.length === 0 && <p>Chưa có lần sửa nhãn.</p>}
      <ol className="mt-2 space-y-2">
        {rows?.map((row) => (
          <li key={row.revision_number} className="border-t pt-2">
            Lần {row.revision_number} · {new Date(row.created_at).toLocaleString("vi-VN")}
            <p>{row.previous_ground_truth?.human_label || "Chưa có"} → {row.new_ground_truth?.human_label || "Chưa có"}</p>
            <p>{row.reason}</p>
          </li>
        ))}
      </ol>
    </details>
  );
}
