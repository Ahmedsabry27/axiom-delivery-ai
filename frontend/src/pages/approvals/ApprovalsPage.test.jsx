import {render,screen} from "@testing-library/react";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {beforeEach,describe,expect,it,vi} from "vitest";
import ApprovalsPage from "./ApprovalsPage";

const mocks=vi.hoisted(()=>({getApprovals:vi.fn(),getApproval:vi.fn(),decideApproval:vi.fn(),delegateApproval:vi.fn()}));
vi.mock("../../services/action.service",()=>mocks);
const approval={id:"approval-1",proposedActionId:"action-1",actionVersion:1,requesterId:"requester",assignedApproverId:"approver",riskLevel:"MEDIUM",status:"PENDING",safeActionSummary:{title:"Register supplier risk",actionType:"CREATE_RAID_ITEM"},separationOfDuties:true,createdAt:"2026-08-15T08:00:00Z",expiresAt:"2026-08-22T08:00:00Z",decisions:[],capabilities:{canView:true,canApprove:true,canReject:true,canRequestChanges:true,canDelegate:false},action:{title:"Register supplier risk",description:"Evidence-backed intervention",actionType:"CREATE_RAID_ITEM",targetSystem:"INTERNAL",payload:{item_type:"RISK"},evidence:[{id:"ev-1",title:"Supplier review",sourceSystem:"AXIOM",capturedAt:"2026-08-15T07:00:00Z"}]}};
function setup(path="/approvals/approval-1"){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[path]}><Routes><Route path="/approvals" element={<ApprovalsPage/>}/><Route path="/approvals/:approvalId" element={<ApprovalsPage/>}/><Route path="/actions" element={<p>Actions</p>}/></Routes></MemoryRouter></QueryClientProvider>)}
beforeEach(()=>{Object.values(mocks).forEach(mock=>mock.mockReset());mocks.getApprovals.mockResolvedValue({items:[approval],total:1,page:1});mocks.getApproval.mockResolvedValue(approval);});

describe("Approval Inbox",()=>{
  it("places evidence, exact payload, and human decisions in one view",async()=>{setup();expect(await screen.findByText("What will change")).toBeInTheDocument();expect(screen.getByText("Supplier review")).toBeInTheDocument();expect(screen.getByText("Exact approved payload")).toBeInTheDocument();expect(screen.getByRole("button",{name:/Approve/})).toBeInTheDocument();expect(screen.getByText("Separation of duties")).toBeInTheDocument();});
  it("renders requester or read-only access without decision controls",async()=>{mocks.getApproval.mockResolvedValue({...approval,capabilities:{...approval.capabilities,canApprove:false,canReject:false,canRequestChanges:false}});setup();expect(await screen.findByText("read-only access",{exact:false})).toBeInTheDocument();expect(screen.queryByRole("button",{name:/Approve/})).not.toBeInTheDocument();});
});
