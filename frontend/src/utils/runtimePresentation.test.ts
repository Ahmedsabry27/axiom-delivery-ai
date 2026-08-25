import {describe,expect,it} from "vitest";
import {formatRuntimeDuration,runtimeFailureMessage} from "./runtimePresentation";

describe("formatRuntimeDuration",()=>{
  it.each([[624,"624 ms"],[1800,"1.8 s"],[74000,"1m 14s"],[undefined,"—"]])("formats %s",(value,expected)=>expect(formatRuntimeDuration(value)).toBe(expected));
  it("preserves an actual zero",()=>expect(formatRuntimeDuration(0)).toBe("0 ms"));
});

describe("runtimeFailureMessage",()=>{
  it("explains an unapproved production model instead of appearing unresponsive",()=>{
    expect(runtimeFailureMessage({status:"FAILED",error:{code:"BUDGET_ENFORCEMENT_BLOCKED",message:"MODEL_NOT_APPROVED"}})).toContain("has not been approved");
  });
  it("preserves safe runtime failures",()=>expect(runtimeFailureMessage({status:"FAILED",error:{message:"Provider unavailable"}})).toBe("Provider unavailable"));
});
