import {render,screen} from "@testing-library/react";
import {describe,expect,it} from "vitest";
import AssistantMessage from "./AssistantMessage";

describe("AssistantMessage runtime result",()=>{
  it("shows a successful result only for authoritative COMPLETED",()=>{
    const {rerender}=render(<AssistantMessage message={{text:"Created Jira issue OPS-1",metadata:{execution_id:"runtime-1",workflow_id:"workflow-1",status:"FAILED",steps:[]}}}/>);
    expect(screen.queryByText("Created Jira issue OPS-1")).not.toBeInTheDocument();
    rerender(<AssistantMessage message={{text:"Created Jira issue OPS-1",metadata:{execution_id:"runtime-1",workflow_id:"workflow-1",status:"COMPLETED",steps:[]}}}/>);
    expect(screen.getByText("Created Jira issue OPS-1")).toBeInTheDocument();
  });
});
