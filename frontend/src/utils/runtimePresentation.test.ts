import {describe,expect,it} from "vitest";
import {formatRuntimeDuration} from "./runtimePresentation";

describe("formatRuntimeDuration",()=>{
  it.each([[624,"624 ms"],[1800,"1.8 s"],[74000,"1m 14s"],[undefined,"—"]])("formats %s",(value,expected)=>expect(formatRuntimeDuration(value)).toBe(expected));
  it("preserves an actual zero",()=>expect(formatRuntimeDuration(0)).toBe("0 ms"));
});
