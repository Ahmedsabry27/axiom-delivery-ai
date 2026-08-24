import {describe,expect,it} from "vitest";
import {normalizePortfolioWorkspace} from "./portfolio.service";

describe("portfolio response normalization",()=>{
  it("renders partial and stale payloads without throwing",()=>{
    const result=normalizePortfolioWorkspace({generatedAt:"2026-08-20T00:00:00Z"});
    expect(result.health.score).toBeNull();
    expect(result.health.status).toBe("UNKNOWN");
    expect(result.programmes).toEqual([]);
    expect(result.projects).toEqual([]);
  });
});
