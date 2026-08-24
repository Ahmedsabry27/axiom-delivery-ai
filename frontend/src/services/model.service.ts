import api from "./api";

export const getModels=(params:Record<string,string>={})=>api.get("/api/models",{params}).then(response=>response.data);
export const getModelSummary=()=>api.get("/api/models/summary").then(response=>response.data);
export const getModelCatalog=()=>api.get("/api/models/catalog").then(response=>response.data);
export const getModel=(id:string)=>api.get(`/api/models/${id}`).then(response=>response.data);
export const createModel=(payload:Record<string,unknown>)=>api.post("/api/models",payload).then(response=>response.data);
export const getModelSection=(id:string,section:string)=>api.get(`/api/models/${id}/${section}`).then(response=>response.data);
