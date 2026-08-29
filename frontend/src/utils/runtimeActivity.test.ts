import {describe,expect,it} from "vitest";
import {runtimeActivity,safeActivityLabel} from "./runtimeActivity";
import type {RuntimeEvent} from "../types/runtime";
const event=(overrides:Partial<RuntimeEvent>):RuntimeEvent=>({type:"step",execution_id:"execution-1",sequence:1,status:"completed",...overrides} as RuntimeEvent);
describe("runtime activity presentation",()=>{
 it("maps canonical events to safe labels",()=>{expect(safeActivityLabel(event({name:"Agent Selected",agent:"Jira Delivery Agent"}))).toBe("Selected Jira Delivery Agent");expect(safeActivityLabel(event({type:"approval_required"}))).toBe("Waiting for approval")});
 it("deduplicates updates and orders committed sequences",()=>{const items=runtimeActivity([event({step_id:"agent",sequence:3,name:"Agent Selected",agent:"Jira Delivery Agent"}),event({step_id:"request",sequence:1,name:"Request Received"}),event({step_id:"agent",sequence:2,name:"Agent Selected",status:"running"})],"RUNNING");expect(items.map(item=>item.label)).toEqual(["Understood the request","Selected Jira Delivery Agent"]);expect(items[1].state).toBe("completed")});
 it("settles running rows after a terminal snapshot",()=>{expect(runtimeActivity([event({status:"running",name:"Planner"})],"CANCELLED")[0].state).toBe("completed")});
 it("never renders raw internal names as fallback",()=>{expect(safeActivityLabel(event({name:"WORKFLOW_NODE_RESOLVED"}))).toBe("Runtime activity recorded")});
});
