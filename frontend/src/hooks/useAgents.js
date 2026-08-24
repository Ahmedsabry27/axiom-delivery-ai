import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createAgent, getAgent, getAgentAnalytics, getAgentExecutions, getAgents, lifecycleAgent, updateAgent } from "../services/agentService";

export function useAgents(params={}){return useQuery({queryKey:["agents",params],queryFn:()=>getAgents(params),placeholderData:previous=>previous});}
export const useAgent=id=>useQuery({queryKey:["agent",id],queryFn:()=>getAgent(id),enabled:Boolean(id)});
export const useAgentExecutions=(id,params={})=>useQuery({queryKey:["agent",id,"executions",params],queryFn:()=>getAgentExecutions(id,params),enabled:Boolean(id),refetchInterval:15_000});
export const useAgentAnalytics=(id,params={})=>useQuery({queryKey:["agent",id,"analytics",params],queryFn:()=>getAgentAnalytics(id,params),enabled:Boolean(id)});
export function useAgentMutations(){const queryClient=useQueryClient();const refresh=()=>queryClient.invalidateQueries({queryKey:["agents"]});return {create:useMutation({mutationFn:createAgent,onSuccess:refresh}),update:useMutation({mutationFn:({id,payload,lockVersion})=>updateAgent(id,payload,lockVersion),onSuccess:refresh}),lifecycle:useMutation({mutationFn:({id,action,lockVersion,payload})=>lifecycleAgent(id,action,lockVersion,payload),onSuccess:refresh})};}
