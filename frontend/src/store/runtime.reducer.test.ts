import {describe,expect,it,vi} from "vitest";
import {initialRuntimeState,runtimeReducer} from "./runtime.reducer";

const started=()=>runtimeReducer(initialRuntimeState,{type:"started",execution:{execution_id:"runtime-1",workflow_id:"workflow-1",status:"RUNNING",state_version:1}});
const event=(sequence:number,values:Record<string,unknown>={})=>({type:"step",execution_id:"runtime-1",workflow_id:"workflow-1",sequence,state_version:1,aggregate_status:"RUNNING" as const,status:"completed" as const,...values});

describe("authoritative runtime projection",()=>{
  it("discards an obsolete continuation when authoritative state resumes",()=>{
    let state=runtimeReducer(started(),{type:"event",event:event(2,{type:"required_input",aggregate_status:"WAITING_FOR_INPUT",state_version:2,status:"waiting",continuation_id:"old",fields:[{name:"summary"}]})});
    state=runtimeReducer(state,{type:"event",event:event(3,{type:"runtime.resumed",aggregate_status:"RUNNING",state_version:3,status:"completed"})});
    expect(state.requiredInput).toBeNull();
  });
  it("merges one logical planner step and ignores duplicate/out-of-order events",()=>{
    let state=started();
    state=runtimeReducer(state,{type:"event",event:event(2,{step_id:"planner",name:"Planner",status:"running"})});
    state=runtimeReducer(state,{type:"event",event:event(3,{step_id:"planner",name:"Planner",status:"completed"})});
    state=runtimeReducer(state,{type:"event",event:event(3,{step_id:"planner",name:"Duplicate"})});
    state=runtimeReducer(state,{type:"event",event:event(2,{step_id:"planner",name:"Older"})});
    expect(state.steps).toHaveLength(1);expect(state.steps[0].status).toBe("completed");expect(state.lastSequence).toBe(3);
  });

  it.each(["COMPLETED","FAILED","CANCELLED","TIMED_OUT"] as const)("projects terminal %s only from aggregate status",status=>{
    const state=runtimeReducer(started(),{type:"event",event:event(2,{type:`runtime.${status.toLowerCase()}`,aggregate_status:status,state_version:2,status:status.toLowerCase(),final:true,message:"Jira result",error:status==="FAILED"?"Jira failed":undefined})});
    expect(state.status).toBe(status);expect(state.finalResponse).toBe(status==="COMPLETED"?"Jira result":undefined);
  });

  it("does not infer completion from final or component completion",()=>{
    const state=runtimeReducer(started(),{type:"event",event:event(2,{type:"tool_completed",component_type:"tool",component_id:"jira-1",final:true})});
    expect(state.status).toBe("RUNNING");expect(state.tools).toHaveLength(1);
  });

  it.each(["WAITING_FOR_INPUT","WAITING_FOR_APPROVAL"] as const)("keeps %s nonterminal",status=>{
    const type=status==="WAITING_FOR_INPUT"?"required_input":"approval_required";
    const state=runtimeReducer(started(),{type:"event",event:event(2,{type,aggregate_status:status,state_version:2,status:"waiting",continuation_id:"continuation-1"})});
    expect(state.status).toBe(status);expect(status==="WAITING_FOR_INPUT"?state.requiredInput:state.approval).toBeTruthy();expect(state.error).toBeNull();
  });

  it("lets newer SSE beat stale REST and authoritative REST beat local state",()=>{
    let state=runtimeReducer(started(),{type:"event",event:event(2,{type:"runtime.completed",aggregate_status:"COMPLETED",state_version:2,final:true})});
    state=runtimeReducer(state,{type:"hydrate",runtime:{execution_id:"runtime-1",workflow_id:"workflow-1",status:"RUNNING",state_version:1}});
    expect(state.status).toBe("COMPLETED");
    state=runtimeReducer(state,{type:"hydrate",runtime:{execution_id:"runtime-1",workflow_id:"workflow-1",status:"FAILED",state_version:3,error:"Authoritative failure"}});
    expect(state.status).toBe("FAILED");expect(state.error?.message).toBe("Authoritative failure");
  });

  it("does not convert an unknown state to success",()=>{
    const diagnostic=vi.spyOn(console,"error").mockImplementation(()=>undefined);
    const state=runtimeReducer(started(),{type:"event",event:event(2,{aggregate_status:"BROKEN"})});
    expect(state.status).toBe("RUNNING");expect(diagnostic).toHaveBeenCalled();diagnostic.mockRestore();
  });

  it.each([
    ["tool_timed_out","TIMED_OUT","timed_out"],
    ["tool_failed","FAILED","failed"],
    ["action_cancelled","CANCELLED","cancelled"],
  ] as const)("projects Jira child %s without independently rolling up parent",(type,parent,childStatus)=>{
    let state=started();
    state=runtimeReducer(state,{type:"event",event:event(2,{type:type.replace(/_(timed_out|failed|cancelled)$/,"_started"),component_id:"jira-1",name:"jira.create_issue",status:"running"})});
    state=runtimeReducer(state,{type:"event",event:event(3,{type,component_id:"jira-1",name:"jira.create_issue",status:childStatus})});
    expect(state.status).toBe("RUNNING");expect((type.startsWith("action")?state.actions:state.tools)[0].status).toBe(childStatus);
    state=runtimeReducer(state,{type:"event",event:event(4,{type:`runtime.${parent.toLowerCase()}`,aggregate_status:parent,state_version:2,final:true})});
    expect(state.status).toBe(parent);
  });
});
