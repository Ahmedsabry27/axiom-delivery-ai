import {beforeEach,describe,expect,it,vi} from "vitest";

describe("Sprint Intelligence mock repository",()=>{
  beforeEach(()=>{
    vi.resetModules();
    vi.stubEnv("VITE_USE_MOCK_DELIVERY_DATA","true");
  });

  it("keeps original commitment separate from scope change",async()=>{
    const {getSprint}=await import("./sprint-intelligence.service");
    const sprint=await getSprint("sprint-24");
    expect(sprint.committed).toBe(82);
    expect(sprint.scopeChange).toBe(8);
    expect(sprint.metrics.predictability.value).toBe(65.85);
  });

  it("supports healthy, at-risk and insufficient-data list states",async()=>{
    const {getSprints}=await import("./sprint-intelligence.service");
    const data=await getSprints();
    expect(data.items.map(item=>item.health)).toEqual(expect.arrayContaining(["GREEN","AMBER","UNKNOWN"]));
  });

  it("provides explainable forecast and anti-pattern evidence",async()=>{
    const {getSprint}=await import("./sprint-intelligence.service");
    const sprint=await getSprint("sprint-24");
    expect(sprint.forecastDetail.method).toMatch(/throughput/i);
    expect(sprint.antiPatterns[0].threshold).toBeTruthy();
    expect(sprint.workItems[0].reasons.length).toBeGreaterThan(0);
  });
});
