import { useAuth } from "@/contexts/AuthContext";
import { useSearchParams } from "react-router-dom";
import { Tabs,TabsContent,TabsList,TabsTrigger } from "@/components/ui/tabs";
import { Overview,ConfusionMatrix,ReviewQueue,ExtractionMetrics,ProviderHealth,DatasetVersions } from "./llm-evaluation/Panels";
const groups = [
 {label:"Hiệu quả model",tabs:[{id:"overview",label:"Tổng quan",component:Overview},{id:"matrix",label:"Ma trận nhầm lẫn",component:ConfusionMatrix},{id:"extract",label:"Trích xuất",component:ExtractionMetrics}]},
 {label:"Kiểm duyệt",tabs:[{id:"review",label:"Gán nhãn",component:ReviewQueue}]},
 {label:"Vận hành AI",tabs:[{id:"provider",label:"Provider",component:ProviderHealth},{id:"dataset",label:"Dataset",component:DatasetVersions}]},
];
export default function EvaluationManagement(){
 const {user}=useAuth();
 const visibleGroups=groups.map(group=>({...group,tabs:group.tabs.filter(tab=>tab.id!=="dataset" || user?.role==="admin")}));
 const [params,setParams]=useSearchParams(); const tabs=visibleGroups.flatMap(group=>group.tabs);
 const section=tabs.some(tab=>tab.id===params.get("section")) ? params.get("section")! : "overview";
 return <div className="space-y-6"><div><h2 className="text-2xl font-bold">Đánh giá LLM · Stage 2</h2><p className="mt-2 text-muted-foreground">Theo dõi chất lượng model, gán nhãn và quản lý dữ liệu huấn luyện.</p></div>
 <Tabs value={section} onValueChange={value=>setParams(current=>{current.set("section",value);return current;})}>
 <TabsList className="evaluation-tabs h-auto w-full flex-wrap justify-start gap-3 bg-transparent p-0">{visibleGroups.map(group=><div key={group.label} className="space-y-2"><p className="text-sm font-medium text-muted-foreground">{group.label}</p><div className="flex flex-wrap gap-1">{group.tabs.map(tab=><TabsTrigger key={tab.id} value={tab.id}>{tab.label}</TabsTrigger>)}</div></div>)}</TabsList>
 {tabs.map(tab=><TabsContent key={tab.id} value={tab.id} className="mt-6"><tab.component/></TabsContent>)}
 </Tabs></div>;
}
