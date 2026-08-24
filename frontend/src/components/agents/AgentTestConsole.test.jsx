import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import AgentTestConsole from "./AgentTestConsole";
import { testAgent, resumeAgent } from "../../services/agentService";

vi.mock("../../services/agentService",()=>({testAgent:vi.fn(),resumeAgent:vi.fn(),cancelAgentExecution:vi.fn()}));

describe("AgentTestConsole",()=>{
  beforeEach(()=>vi.clearAllMocks());
  it("runs the persisted agent and displays linkage",async()=>{
    testAgent.mockResolvedValue({execution_id:"exec-1",status:"succeeded",correlation_id:"corr-1",result:{message:"Verified result"}});
    render(<AgentTestConsole agent={{uuid:"agent-1",published_version:3}}/>);
    fireEvent.click(screen.getByRole("button",{name:/run test/i}));
    expect(await screen.findByText(/Verified result/)).toBeInTheDocument();
    expect(screen.getByText(/exec-1/)).toBeInTheDocument();
    expect(testAgent).toHaveBeenCalledWith("agent-1",expect.objectContaining({message:"Generate a deployment report"}));
  });
  it("renders schema input and resumes the same execution",async()=>{
    testAgent.mockResolvedValue({execution_id:"exec-2",status:"waiting_for_input",correlation_id:"corr-2",continuation:{kind:"input",resume_token:"opaque-token",missing_fields:["project_name"]}});
    resumeAgent.mockResolvedValue({execution_id:"exec-2",status:"succeeded",correlation_id:"corr-2",result:{message:"Deployment Report"}});
    render(<AgentTestConsole agent={{uuid:"agent-1",published_version:1}}/>);
    fireEvent.click(screen.getByRole("button",{name:/run test/i}));
    const input=await screen.findByLabelText(/project name/i);fireEvent.change(input,{target:{value:"Copilot"}});
    fireEvent.click(screen.getByRole("button",{name:/resume execution/i}));
    await waitFor(()=>expect(resumeAgent).toHaveBeenCalledWith("exec-2","input",{resume_token:"opaque-token",response:{project_name:"Copilot"}}));
    expect(await screen.findByText(/Deployment Report/)).toBeInTheDocument();
  });
});
