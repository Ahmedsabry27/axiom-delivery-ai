export const productConfig = Object.freeze({
  name: "Axiom Delivery AI",
  shortName: "Axiom",
  category: "Enterprise Delivery Intelligence",
  tagline: "Evidence-led delivery. Confident decisions.",
  description: "An AI-powered delivery intelligence platform for programme visibility, proactive risk management, governance automation, and evidence-backed decision-making.",
});

export const pageTitle = (pageName) => pageName ? `${pageName} | ${productConfig.name}` : productConfig.name;
