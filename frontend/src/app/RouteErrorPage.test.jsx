import { describe, expect, it } from "vitest";

import { isStaleChunkError } from "./staleChunkRecovery";

describe("route error recovery", () => {
  it("recognizes a removed deployment chunk", () => {
    expect(
      isStaleChunkError(
        new TypeError(
          "Failed to fetch dynamically imported module: https://example.test/assets/Page-old.js",
        ),
      ),
    ).toBe(true);
  });

  it("does not treat ordinary route failures as stale chunks", () => {
    expect(isStaleChunkError(new Error("Request failed with status 403"))).toBe(false);
  });
});
