import { describe, expect, it } from "vitest";
import { normalizeCommandCenterData, normalizeMyDayData } from "./delivery.repository";

describe("delivery response normalization", () => {
  it("makes an empty command-center response safe to render", () => {
    const data = normalizeCommandCenterData({});

    expect(data.portfolioHealth.label).toBe("Portfolio Health");
    expect(data.sprintPredictability.label).toBe("Sprint Predictability");
    expect(data.openRisks.label).toBe("Open Risks");
    expect(data.dependencies.label).toBe("Dependencies");
    expect(data.deliveryTrend).toEqual([]);
    expect(data.attentionItems).toEqual([]);
    expect(data.recommendations).toEqual([]);
    expect(data.contexts).toEqual([]);
  });

  it("preserves provided metrics while filling partial metric fields", () => {
    const data = normalizeCommandCenterData({
      portfolioHealth: { value: 72 },
    });

    expect(data.portfolioHealth).toMatchObject({
      label: "Portfolio Health",
      value: 72,
      status: "UNKNOWN",
    });
  });

  it("makes empty and malformed My Day collections safe to render", () => {
    expect(normalizeMyDayData(undefined)).toMatchObject({
      focusScore: 0,
      items: [],
      briefings: [],
    });
    expect(normalizeMyDayData({ items: undefined, briefings: undefined })).toMatchObject({
      items: [],
      briefings: [],
    });
  });
});
