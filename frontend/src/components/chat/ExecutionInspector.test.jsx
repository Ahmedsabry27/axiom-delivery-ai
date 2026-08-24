import {fireEvent,render,screen} from "@testing-library/react";
import {describe,expect,it} from "vitest";
import ExecutionInspector from "./ExecutionInspector";
import {initialRuntimeState} from "../../store/runtime.reducer";

describe("ExecutionInspector",()=>{
  it("renders authoritative identity, resolved provider/model, and duration",()=>{
    render(<ExecutionInspector runtime={{...initialRuntimeState,executionId:"runtime-1",workflowId:"workflow-1",status:"TIMED_OUT",startedAt:"2026-08-12T10:00:00Z",finishedAt:"2026-08-12T10:00:02Z",durationMs:1800,metrics:{provider:"bedrock",model:"amazon.nova-lite-v1:0"}}}/>);
    expect(screen.getByText("Timed out")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button",{name:"Context"}));
    expect(screen.getAllByText("runtime-1").length).toBeGreaterThan(0);
    expect(screen.getByText("workflow-1")).toBeInTheDocument();
    expect(screen.getByText("bedrock")).toBeInTheDocument();
    expect(screen.getByText("amazon.nova-lite-v1:0")).toBeInTheDocument();
    expect(screen.getByText("1.8 s")).toBeInTheDocument();
  });
});
