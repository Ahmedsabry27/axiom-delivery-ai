# Demonstration data relationships

```mermaid
flowchart LR
  P[Enterprise Transformation Portfolio FY27] --> CX[Customer Experience Modernisation]
  P --> CORE[Core Platform Resilience]
  P --> OPS[Operations Automation]
  CORE --> ID[Identity Modernisation]
  CX --> CLAIMS[Digital Claims Portal]
  ID --> SENT[Sentinel / Identity Sprint 14]
  SENT --> WI[IDAM-241 Token Exchange]
  ID --> DEP[DEP-017 Identity API]
  DEP --> WI
  DEP --> MS[Identity Integration Complete]
  MS --> REL[Atlas 3.2]
  DEP --> RISK[RISK-008]
  RISK --> REL
  P --> OUT[SO-02 Platform Resilience]
  OUT --> CORE
  EVID[Demo evidence] --> DEP
  EVID --> REL
```

Every identifier is deterministic UUIDv5. The validator checks hierarchy counts, two endpoints per dependency, demo classification, and reconciliation of programme totals to £18.40M approved, £8.15M actual, and £19.25M forecast.
