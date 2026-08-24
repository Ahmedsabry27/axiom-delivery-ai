import {useQuery} from "@tanstack/react-query";
import {getPortfolioWorkspace,normalizePortfolioWorkspace} from "../services/portfolio.service";
export const usePortfolio=()=>useQuery({queryKey:["delivery","portfolio"],queryFn:({signal})=>getPortfolioWorkspace(signal),select:normalizePortfolioWorkspace,staleTime:30_000,retry:false});
