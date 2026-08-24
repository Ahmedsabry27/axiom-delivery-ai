import {render,screen} from "@testing-library/react";
import {describe,expect,it} from "vitest";
import RuntimeExecutionCard from "./RuntimeExecutionCard";

describe("RuntimeExecutionCard authoritative terminal UX",()=>{
  it.each([
    ["COMPLETED","Completed"],
    ["FAILED","Failed"],
    ["CANCELLED","Cancelled"],
    ["TIMED_OUT","Timed out"],
  ])("renders %s explicitly without an in-progress duration",(status,label)=>{
    const {container}=render(<RuntimeExecutionCard metadata={{status,execution_id:"runtime-1",workflow_id:"workflow-1",duration_ms:1800,steps:[]}}/>);
    expect(screen.getAllByText(new RegExp(label,"i")).length).toBeGreaterThan(0);
    expect(screen.getByText("1.8 s")).toBeInTheDocument();
    expect(screen.queryByText("In progress")).not.toBeInTheDocument();
    expect(container.querySelector(".animate-spin")).toBeNull();
  });

  it("shows in progress only for an active runtime",()=>{
    render(<RuntimeExecutionCard metadata={{status:"RUNNING",workflow_id:"workflow-1",steps:[]}}/>);
    expect(screen.getByText("In progress")).toBeInTheDocument();
  });

  it("does not fabricate zero duration",()=>{
    render(<RuntimeExecutionCard metadata={{status:"FAILED",workflow_id:"workflow-1",steps:[]}}/>);
    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("0 ms")).not.toBeInTheDocument();
  });
});
