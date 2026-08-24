import { describe, expect, it } from "vitest";
import { pageTitle, productConfig } from "./product";

describe("product identity",()=>{
  it("defines the Axiom identity centrally",()=>{
    expect(productConfig.name).toBe("Axiom Delivery AI");
    expect(productConfig.tagline).toBe("Evidence-led delivery. Confident decisions.");
  });
  it("builds contextual browser titles",()=>{
    expect(pageTitle("Command Center")).toBe("Command Center | Axiom Delivery AI");
    expect(pageTitle()).toBe("Axiom Delivery AI");
  });
});
