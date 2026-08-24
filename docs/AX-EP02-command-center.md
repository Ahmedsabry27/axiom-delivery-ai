# AX-EP02 — Delivery Command Center and My Day

The epic is implemented as two authenticated routes: `/command-center` for portfolio-level delivery intelligence and `/my-day` for the current user's agenda and briefings.

Demo data is synthetic and is enabled unless `VITE_USE_MOCK_DELIVERY_DATA=false`. Both pages use `DeliveryRepository`; switching the flag routes reads to `/api/delivery/command-center` and `/api/delivery/my-day`. Backend responses are tenant-scoped through the existing authentication dependency.

Portfolio health uses weighted project (25%), release (25%), risk (20%), dependency (15%) and milestone (15%) components. Available components are reweighted when at least three exist; fewer components produce `UNKNOWN`. Sprint predictability prefers story points and falls back to item counts. Attention priority is deterministic and exposes impact, urgency, critical-path and age factors.

Actions are intentionally safe: the UI creates only an internal proposal for review and explicitly states that no external system is updated. The current backend foundation exposes no external-write endpoint. Recommendation evidence remains visible before action.
