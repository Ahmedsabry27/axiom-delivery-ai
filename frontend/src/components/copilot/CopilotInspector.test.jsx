import {fireEvent,render,screen} from "@testing-library/react";
import {describe,expect,it,vi} from "vitest";
import {initialRuntimeState} from "../../store/runtime.reducer";
import CopilotInspector from "./CopilotInspector";

describe("CopilotInspector",()=>{
  it("shows persisted context, authorized evidence and safe runtime activity",()=>{
    const messages=[{id:"m1",metadata:{structured_response:{evidence:[{id:"ev-1",title:"Sprint snapshot",summary:"Authorized excerpt",sourceType:"Jira",freshness:"Current"}]}}}];
    const runtime={...initialRuntimeState,steps:[{id:"s1",name:"Evidence retrieved",status:"completed"}]};
    render(<CopilotInspector contextId="project-payments" messages={messages} runtime={runtime} onContextChange={vi.fn()}/>);
    expect(screen.getByText("Payments Platform")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Evidence"}));
    expect(screen.getByText("Sprint snapshot")).toBeInTheDocument();
    expect(screen.getByText("Authorized excerpt")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Activity"}));
    expect(screen.getByText("Evidence retrieved")).toBeInTheDocument();
    expect(screen.getByText(/Private reasoning/)).toBeInTheDocument();
  });
});
