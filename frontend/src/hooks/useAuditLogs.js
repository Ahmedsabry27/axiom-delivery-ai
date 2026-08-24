import { useQuery } from "@tanstack/react-query";
import { getAuditLogs } from "../services/auditService";
export const useAuditLogs=(filters)=>useQuery({queryKey:["audit",filters],queryFn:()=>getAuditLogs(filters),staleTime:15_000});
