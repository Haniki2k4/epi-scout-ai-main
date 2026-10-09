import { useState } from "react";
import { llmApi, type Revision } from "@/lib/llmEvaluationApi";
import { Button } from "@/components/ui/button";
export default function ReviewHistory({itemId}:{itemId:number}) {
 const [rows,setRows]=useState<Revision[] | null>(null);const [error,setError]=useState("");const [loading,setLoading]=useState(false);
 const load=async()=>{setLoading(true);setError("");try{setRows((await llmApi.detail(itemId)).revisions);}catch(error){setError(error instanceof Error?error.message:"Không tải được lịch sử");}finally{setLoading(false);}};
 return <details onToggle={event=>{if(event.currentTarget.open && rows===null && !loading) void load();}}><summary className="cursor-pointer font-medium text-primary">Lịch sử sửa nhãn</summary>{loading&&<p role="status">Đang tải…</p>}{error&&<div role="alert">{error}<Button variant="outline" onClick={load}>Thử lại</Button></div>}{rows?.length===0&&<p>Chưa có lần sửa nhãn.</p>}<ol className="mt-2 space-y-2">{rows?.map(row=><li key={row.revision_number} className="border-t pt-2">Lần {row.revision_number} · {new Date(row.created_at).toLocaleString("vi-VN")}<p>{row.previous_ground_truth?.human_label || "Chưa có"} → {row.new_ground_truth?.human_label || "Chưa có"}</p><p>{row.reason}</p></li>)}</ol></details>;
}
