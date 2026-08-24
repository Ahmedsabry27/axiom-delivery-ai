import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createWorkflow, deleteWorkflow, executeWorkflow, getWorkflows } from "../services/workflowService";
export function useWorkflows(){const qc=useQueryClient(),key=["workflows"],refresh=()=>qc.invalidateQueries({queryKey:key}); return {query:useQuery({queryKey:key,queryFn:getWorkflows}),create:useMutation({mutationFn:createWorkflow,onSuccess:refresh}),execute:useMutation({mutationFn:executeWorkflow,onSuccess:refresh}),remove:useMutation({mutationFn:deleteWorkflow,onSuccess:refresh})};}
