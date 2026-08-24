import {render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {MemoryRouter} from "react-router-dom";
import {beforeEach,describe,expect,it,vi} from "vitest";
import ToolCatalogPage from "./ToolCatalogPage";
import {getTools} from "../../services/tool.service";
vi.mock("../../services/tool.service",()=>({getTools:vi.fn()}));
const tool={name:"servicenow_incident_search",display_name:"ServiceNow Incident Search",description:"Search approved incidents",category:"it_service_management",provider:"servicenow",version:"1.0.0",enabled:true,permissions:["servicenow.incidents.read"],risk_level:"read",configuration_state:"ready"};
const renderPage=()=>render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter><ToolCatalogPage/></MemoryRouter></QueryClientProvider>);
describe("ToolCatalogPage",()=>{
 beforeEach(()=>getTools.mockReset());
 it("renders real catalog data and refetches for search",async()=>{getTools.mockResolvedValue({items:[tool],total:1,pages:1});renderPage();expect(await screen.findByText("ServiceNow Incident Search")).toBeInTheDocument();await userEvent.type(screen.getByLabelText("Search tools"),"incident");expect(getTools).toHaveBeenCalled()});
 it("renders empty and error states",async()=>{getTools.mockResolvedValueOnce({items:[],total:0,pages:1});const{unmount}=renderPage();expect(await screen.findByText(/No tools match/)).toBeInTheDocument();unmount();getTools.mockRejectedValueOnce(new Error("offline"));renderPage();expect(await screen.findByText(/Unable to load the catalog/)).toBeInTheDocument()});
});
