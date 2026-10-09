import { Navigate, useSearchParams } from "react-router-dom";
import { legacyAdminPaths } from "@/config/navigation";
export default function AdminInterface() {
 const [params] = useSearchParams();
 return <Navigate replace to={legacyAdminPaths[params.get("tab") ?? ""] ?? "/admin/operations/status"}/>;
}
