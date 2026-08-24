import {useMutation,useQuery,useQueryClient} from "@tanstack/react-query";
import * as service from "../services/integration.service";

export const useIntegrations=(filters={})=>useQuery({queryKey:["integrations",filters],queryFn:()=>service.listIntegrations(filters)});
export const useConnectorCatalog=()=>useQuery({queryKey:["integration-catalog"],queryFn:service.getConnectorCatalog});
export const useIntegration=(id:string)=>useQuery({queryKey:["integration",id],queryFn:()=>service.getIntegration(id),enabled:!!id});
export const useCapabilities=(id:string)=>useQuery({queryKey:["integration",id,"capabilities"],queryFn:()=>service.getCapabilities(id),enabled:!!id});
export const useIntegrationAgents=(id:string)=>useQuery({queryKey:["integration",id,"agents"],queryFn:()=>service.getIntegrationAgents(id),enabled:!!id});
export const useIntegrationUsage=(id:string)=>useQuery({queryKey:["integration",id,"usage"],queryFn:()=>service.getIntegrationUsage(id),enabled:!!id});
export const useIntegrationOperations=(id:string,section:string)=>useQuery({queryKey:["integration",id,"operations",section],queryFn:()=>service.getIntegrationOperations(id,section),enabled:!!id&&!!section});
export function useIntegrationActions(id?:string){const qc=useQueryClient(),refresh=()=>{qc.invalidateQueries({queryKey:["integrations"]});qc.invalidateQueries({queryKey:["tools"]});qc.invalidateQueries({queryKey:["tool-catalog"]});qc.invalidateQueries({queryKey:["actions"]});if(id)qc.invalidateQueries({queryKey:["integration",id]})};return {
 create:useMutation({mutationFn:service.createIntegration,onSuccess:refresh}),
 test:useMutation({mutationFn:(connectionId:string)=>service.testIntegration(connectionId),onSuccess:refresh}),
 discover:useMutation({mutationFn:(connectionId:string)=>service.discoverCapabilities(connectionId),onSuccess:refresh}),
 sync:useMutation({mutationFn:(connectionId:string)=>service.synchronizeIntegration(connectionId),onSuccess:refresh}),
 connectMicrosoft:useMutation({mutationFn:service.connectMicrosoft,onSuccess:refresh}),
 capability:useMutation({mutationFn:({connectionId,name,payload}:{connectionId:string,name:string,payload:Record<string,unknown>})=>service.updateCapability(connectionId,name,payload),onSuccess:refresh}),
 disable:useMutation({mutationFn:(connectionId:string)=>service.disableIntegration(connectionId),onSuccess:refresh})};}
