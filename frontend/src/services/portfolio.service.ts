import api from "./api";
import {mockPortfolioWorkspace} from "../pages/portfolio/mockPortfolio";
import {isDeliveryMockMode} from "../config/deliveryDataMode";

export type Health={score:number|null;status:string};
export type Programme={id:string;portfolioId:string;name:string;description:string;status:string;health:Health;confidence:number|null;sponsor:string;manager:string;strategicTheme:string;approvedBudget:string|null;actualSpend:string|null;forecast:string|null;currency:string|null;activeProjects:number;atRiskProjects:number;criticalRaid:number;overdueDependencies:number;updatedAt:string};
export type Project={id:string;programmeId:string;name:string;programme:string;description:string;status:string;health:Health;confidence:number|null;manager:string;strategicTheme:string;approvedBudget:string|null;actualSpend:string|null;forecast:string|null;currency:string|null;criticalRaid:number;overdueDependencies:number;milestones:number;nextRelease:string|null;evidenceCount:number;updatedAt:string};
export type StrategicOutcome={id:string;portfolioId:string;name:string;status:string;targetValue:string|null;currentValue:string|null;unit:string|null;targetDate:string|null;confidence:number|null;owner:string;links:Array<{entityType:string;entityId:string;contribution:number|null}>;updatedAt:string};
export type PortfolioWorkspace={generatedAt:string;source:string;freshness:string;portfolios:{id:string;name:string;status:string;updatedAt:string}[];health:Health&{partial:boolean;version:string;factors:Record<string,number>;weights:Record<string,number>};programmes:Programme[];projects:Project[];outcomes:StrategicOutcome[];milestones:Array<Record<string,unknown>>;attention:Array<Record<string,unknown>>;insights:Array<Record<string,unknown>>;sprints:Array<Record<string,unknown>>;releases:Array<Record<string,unknown>>;workItems:Array<Record<string,unknown>>;investment:{authorized:boolean;currencies:string[];aggregationAllowed:boolean;notice:string}};

const emptyHealth:PortfolioWorkspace["health"]={score:null,status:"UNKNOWN",partial:false,version:"portfolio-health-v1",factors:{},weights:{project:.25,release:.25,risk:.2,dependency:.15,milestone:.15}};

export function normalizePortfolioWorkspace(value:Partial<PortfolioWorkspace>|null|undefined):PortfolioWorkspace{
  const data=value||{};
  return {
    generatedAt:data.generatedAt||new Date().toISOString(),
    source:data.source||"Source unavailable",
    freshness:data.freshness||"Unknown",
    portfolios:Array.isArray(data.portfolios)?data.portfolios:[],
    health:{...emptyHealth,...(data.health||{}),factors:data.health?.factors||{},weights:data.health?.weights||emptyHealth.weights},
    programmes:Array.isArray(data.programmes)?data.programmes:[],
    projects:Array.isArray(data.projects)?data.projects:[],
    outcomes:Array.isArray(data.outcomes)?data.outcomes:[],
    milestones:Array.isArray(data.milestones)?data.milestones:[],
    attention:Array.isArray(data.attention)?data.attention:[],
    insights:Array.isArray(data.insights)?data.insights:[],
    sprints:Array.isArray(data.sprints)?data.sprints:[],
    releases:Array.isArray(data.releases)?data.releases:[],
    workItems:Array.isArray(data.workItems)?data.workItems:[],
    investment:{authorized:true,currencies:[],aggregationAllowed:true,notice:"Investment source coverage is unavailable.",...(data.investment||{})},
  };
}

export const isUsingMockPortfolioData=isDeliveryMockMode;

export async function getPortfolioWorkspace(signal?:AbortSignal){
  if(isUsingMockPortfolioData())return {...mockPortfolioWorkspace,generatedAt:new Date().toISOString()};
  return normalizePortfolioWorkspace((await api.get<Partial<PortfolioWorkspace>>("/api/delivery/portfolio",{signal})).data);
}
