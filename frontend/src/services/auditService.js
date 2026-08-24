import api from "./api";
export const getAuditLogs=(filters={})=>api.get("/api/audit",{params:filters}).then(({data})=>data);
