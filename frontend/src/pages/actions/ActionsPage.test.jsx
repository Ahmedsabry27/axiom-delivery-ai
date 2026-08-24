import {render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {QueryClient,QueryClientProvider} from "@tanstack/react-query";
import {MemoryRouter,Route,Routes} from "react-router-dom";
import {beforeEach,describe,expect,it,vi} from "vitest";
import ActionsPage from "./ActionsPage";

const mocks=vi.hoisted(()=>({getActions:vi.fn(),getAction:vi.fn(),createAction:vi.fn(),submitAction:vi.fn(),executeAction:vi.fn(),verifyAction:vi.fn(),cancelAction:vi.fn()}));
vi.mock("../../services/action.service",()=>mocks);
const action={id:"action-1",actionType:"CREATE_RAID_ITEM",title:"Register supplier risk",description:"Evidence-backed intervention",origin:"USER",requesterId:"requester",targetSystem:"INTERNAL",payload:{item_type:"RISK"},status:"PENDING_APPROVAL",riskLevel:"MEDIUM",policyVersion:1,version:1,createdAt:"2026-08-15T08:00:00Z",updatedAt:"2026-08-15T08:00:00Z",evidence:[{id:"ev-1",title:"Supplier review",sourceSystem:"AXIOM",capturedAt:"2026-08-15T07:00:00Z"}],approvals:[],executions:[],auditTrail:[],availableTransitions:["CANCEL"]};
function setup(path="/actions"){return render(<QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><MemoryRouter initialEntries={[path]}><Routes><Route path="/actions" element={<ActionsPage/>}/><Route path="/actions/:actionId" element={<ActionsPage/>}/><Route path="/approvals" element={<p>Approval route</p>}/></Routes></MemoryRouter></QueryClientProvider>)}
beforeEach(()=>{Object.values(mocks).forEach(mock=>mock.mockReset());mocks.getActions.mockResolvedValue({items:[action],total:1,page:1});mocks.getAction.mockResolvedValue(action);});

describe("Action Center",()=>{
  it("uses the platform warm theme",async()=>{const {container}=setup();expect(await screen.findByText("Register supplier risk")).toBeInTheDocument();expect(container.querySelector("main")).toHaveClass("bg-[#faf8f5]","text-[#202020]");});
  it("renders lifecycle controls and opens an evidence-backed action",async()=>{setup();expect(await screen.findByText("Register supplier risk")).toBeInTheDocument();expect(screen.getByText("Awaiting approval")).toBeInTheDocument();await userEvent.click(screen.getByText("Register supplier risk"));expect(await screen.findByText("Supplier review")).toBeInTheDocument();expect(screen.getByText(/Approved payload/)).toBeInTheDocument();});
  it("shows a safe empty state",async()=>{mocks.getActions.mockResolvedValue({items:[],total:0,page:1});setup();expect(await screen.findByText("No actions in this view")).toBeInTheDocument();});
});
