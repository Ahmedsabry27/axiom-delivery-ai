import {fireEvent,render,screen,waitFor} from "@testing-library/react";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {beforeEach,describe,expect,it,vi} from "vitest";
import {governanceApi} from "../../services/governance.service";
import {AIOperationsDashboard,CostsPage,GovernanceDashboard,PoliciesPage,PolicyDetailPage} from "./GovernanceOperationsPages";

vi.mock("../../services/governance.service",()=>({governanceApi:{overview:vi.fn(),policies:vi.fn(),policy:vi.fn(),simulate:vi.fn(),operations:vi.fn(),costs:vi.fn(),budgets:vi.fn()}}));
const api=vi.mocked(governanceApi);

describe("Governance and AI Operations",()=>{
  beforeEach(()=>vi.clearAllMocks());

  it("renders persisted governance measures and preserves missing values",async()=>{
    api.overview.mockResolvedValue({summary:{policy_compliance:75,open_governance_findings:2,access_reviews_due:1,approval_compliance:null,audit_coverage:98},attention:[],human_oversight:{recommendations_generated:null,executed_without_required_approval:0},sources:["governance_policies","audit_logs"]});
    render(<MemoryRouter><GovernanceDashboard/></MemoryRouter>);
    expect(screen.getByRole("heading",{name:"Governance"})).toBeInTheDocument();
    expect(await screen.findByText("75")).toBeInTheDocument();
    expect(screen.getAllByText("Not available").length).toBeGreaterThan(0);
    expect(screen.getByText(/governance_policies, audit_logs/)).toBeInTheDocument();
  });

  it("shows a retryable error state",async()=>{
    api.overview.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce({summary:{policy_compliance:null},attention:[],human_oversight:{},sources:[]});
    render(<MemoryRouter><GovernanceDashboard/></MemoryRouter>);
    expect(await screen.findByRole("alert")).toHaveTextContent("Governed data could not be loaded");
    fireEvent.click(screen.getByRole("button",{name:"Retry"}));
    await waitFor(()=>expect(api.overview).toHaveBeenCalledTimes(2));
  });

  it("shows a truthful empty policy state",async()=>{
    api.policies.mockResolvedValue({items:[],total:0});
    render(<MemoryRouter><PoliciesPage/></MemoryRouter>);
    expect(await screen.findByText("No records")).toBeInTheDocument();
    expect(screen.getByText(/No persisted records/)).toBeInTheDocument();
  });

  it("runs a draft simulation without presenting activation controls",async()=>{
    api.policy.mockResolvedValue({id:"policy-1",name:"Approved Models",description:"",category:"MODEL_ALLOWLIST",version:2,status:"DRAFT",priority:10,conditions:{classification:"CONFIDENTIAL"},effect:{decision:"ALLOW"},reason_codes:[],created_by:"author"});
    api.simulate.mockResolvedValue({current_decision:{decision:"BLOCK"},proposed_decision:{decision:"ALLOW"},changed_behavior:true});
    render(<MemoryRouter initialEntries={["/governance/policies/policy-1"]}><Routes><Route path="/governance/policies/:policyId" element={<PolicyDetailPage/>}/></Routes></MemoryRouter>);
    fireEvent.click(await screen.findByRole("button",{name:"Run simulation"}));
    expect(await screen.findByText(/changed_behavior/)).toBeInTheDocument();
    expect(screen.queryByRole("button",{name:/activate/i})).not.toBeInTheDocument();
  });

  it("renders operations telemetry without inventing unavailable metrics",async()=>{
    api.operations.mockResolvedValue({summary:{ai_executions:12,success_rate:91.7,p95_latency:null,estimated_cost:null,open_incidents:1},charts:{executions:[],latency:[],tokens:[],cost:[]},attention:[],sources:["runtime_executions","ai_usage_records"]});
    render(<MemoryRouter><AIOperationsDashboard/></MemoryRouter>);
    expect(await screen.findByText("12")).toBeInTheDocument();
    expect(screen.getAllByText("Not available")).toHaveLength(2);
    expect(screen.getByText(/missing measures are never converted to zero/i)).toBeInTheDocument();
  });

  it("shows settled spend, reservations, blocks, and reconciliation without inventing forecast",async()=>{
    api.costs.mockResolvedValue({current_spend:"1.25",active_reservations:"0.40",budget:"10.00",forecast:null,cost_per_execution:"0.25",blocked_calls:2,reconciliation_issues:1,forecast_method:"Unavailable"});
    api.budgets.mockResolvedValue({items:[{id:"budget-1",scope_type:"TENANT",hard_limit:"10.00",currency:"USD"}],total:1});
    render(<MemoryRouter><CostsPage/></MemoryRouter>);
    expect(await screen.findByText("1.25")).toBeInTheDocument();
    expect(screen.getByText("0.40")).toBeInTheDocument();
    expect(screen.getByText("Blocked Calls")).toBeInTheDocument();
    expect(screen.getByText("Reconciliation Issues")).toBeInTheDocument();
    expect(screen.getByText("Not available")).toBeInTheDocument();
  });
});
