import {render,screen} from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import {describe,expect,it} from "vitest";
import InlineRuntimeActivity from "./InlineRuntimeActivity";
const metadata=(status,steps)=>({execution_id:"execution-1",status,steps,tools:[],actions:[],duration_ms:4200});
describe("InlineRuntimeActivity",()=>{
 it("shows a compact running row",()=>{render(<InlineRuntimeActivity metadata={metadata("RUNNING",[{step_id:"tool",type:"tool_started",name:"jira.get_projects",status:"running",sequence:1}])}/>);expect(screen.getByText("Retrieving Jira projects…")).toBeInTheDocument();expect(screen.queryByText("AI Runtime Orchestrator")).not.toBeInTheDocument()});
 it("collapses successful terminal activity and expands accessibly",async()=>{const user=userEvent.setup();render(<InlineRuntimeActivity metadata={metadata("COMPLETED",[{step_id:"tool",type:"tool_completed",name:"jira.get_projects",status:"completed",sequence:1,result_summary:{project_count:12}}])}/>);const button=screen.getByRole("button",{name:/completed 1 steps/i});expect(button).toHaveAttribute("aria-expanded","false");await user.click(button);expect(screen.getByText("Retrieved 12 Jira projects")).toBeInTheDocument()});
 it.each([["FAILED","Analysis could not be completed"],["CANCELLED","Execution cancelled"]])("keeps %s visible",(status,label)=>{render(<InlineRuntimeActivity metadata={metadata(status,[{step_id:"terminal",type:"step",name:"Runtime Execution",status:status.toLowerCase(),sequence:1}])}/>);expect(screen.getByText(label)).toBeInTheDocument()});
 it("keeps waiting approval visible",()=>{render(<InlineRuntimeActivity metadata={metadata("WAITING_FOR_APPROVAL",[{step_id:"approval",type:"approval_required",status:"waiting",sequence:1}])}/>);expect(screen.getByText("Waiting for approval")).toBeInTheDocument()});
});
