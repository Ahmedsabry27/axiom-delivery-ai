import { beforeEach, describe, expect, it, vi } from "vitest";

describe("delivery command center repository", () => {
  beforeEach(() => vi.resetModules());
  it("uses mock delivery data by default", async () => {
    vi.stubEnv("VITE_USE_MOCK_DELIVERY_DATA", "true");
    const service = await import("./delivery-command-center.service");
    const data = await service.getDeliveryCommandCenterData();
    expect(data.portfolioHealth.value).toBe(84);
    expect(data.deliveryTrend).toHaveLength(12);
  });
});
