import {useQuery} from "@tanstack/react-query";import {getSprint,getSprints} from "../services/sprint-intelligence.service";
export const useSprints=()=>useQuery({queryKey:["delivery","sprints"],queryFn:({signal})=>getSprints(signal),retry:false,staleTime:30000});
export const useSprint=(id:string)=>useQuery({queryKey:["delivery","sprints",id],queryFn:({signal})=>getSprint(id,signal),enabled:Boolean(id),retry:false,staleTime:30000});
