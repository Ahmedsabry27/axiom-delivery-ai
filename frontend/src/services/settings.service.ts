import api from "./api";

export const getSettings=(category:string)=>api.get(`/api/settings/${category}`).then(r=>r.data);
export const getEffectiveSettings=()=>api.get("/api/settings/effective").then(r=>r.data);
export const saveSettings=(category:string,payload:Record<string,unknown>)=>api.patch(category==="ai"?"/api/settings/ai/preferences":`/api/settings/${category}`,payload).then(r=>r.data);
export const resetPreferences=()=>api.post("/api/settings/preferences/reset").then(r=>r.data);
export const previewRetention=()=>api.post("/api/settings/data/retention-preview").then(r=>r.data);
export const sendTestNotification=()=>api.post("/api/settings/notifications/test").then(r=>r.data);
