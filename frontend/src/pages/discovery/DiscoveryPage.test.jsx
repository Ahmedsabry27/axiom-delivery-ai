import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {beforeEach,describe,expect,it,vi} from "vitest";
import {discoverTools} from "../../services/discovery.service";
import DiscoveryPage from "./DiscoveryPage";
vi.mock("../../services/discovery.service",()=>({discoverTools:vi.fn()}));
const renderPage=()=>render(<QueryClientProvider client={new QueryClient({defaultOptions:{mutations:{retry:false}}})}><DiscoveryPage/></QueryClientProvider>);
describe("DiscoveryPage",()=>{
 beforeEach(()=>discoverTools.mockReset());
 it("renders ranked real-API simulation results",async()=>{
  discoverTools.mockResolvedValue({outcome:"selected",confidence:"high",strategy_version:"1.0.0",duration_ms:12,explanation:"Authorized hybrid ranking.",selected:{display_name:"Deployment Report"},candidates:[{tool_name:"deployment_report",display_name:"Deployment Report",source:"native",category:"operations",health:"healthy",success_rate:.98,expected_latency_ms:420,estimated_cost:.1,score:.91,component_scores:{semantic:.8,lexical:.7,input:1}}],missing_inputs:[]});
  renderPage();await userEvent.click(screen.getByRole("button",{name:/Simulate discovery/i}));
  expect((await screen.findAllByText("Deployment Report")).length).toBeGreaterThan(0);
  expect(screen.getByText("selected")).toBeInTheDocument();
  expect(discoverTools).toHaveBeenCalledWith(expect.objectContaining({environment:"production"}),true)
 });
 it("shows safe no-match state",async()=>{
  discoverTools.mockResolvedValue({outcome:"no_matching_tool",confidence:"low",strategy_version:"1.0.0",duration_ms:4,explanation:"No authorized match.",selected:null,candidates:[],missing_inputs:[]});renderPage();
  await userEvent.click(screen.getByRole("button",{name:/Simulate discovery/i}));
  expect(await screen.findByText(/No authorized matching tool/i)).toBeInTheDocument()
 })
});
