# Axiom delivery metric catalogue

The versioned source of truth is `backend/app/delivery/metrics.py`. Clients can inspect definitions through authenticated `GET /api/delivery/metric-definitions`.

All calculations return missing/unknown when required inputs are absent or denominators are zero. They never turn missing evidence into a misleading zero.

| Metric | Formula | Direction |
|---|---|---|
| Portfolio Health | Project 30% + release 25% + risk 20% + dependency 15% + milestone 10% | Higher is better |
| Sprint Predictability | Completed originally committed scope / originally committed scope × 100 | Higher is better |
| Commitment Achievement | Completed committed work / committed work × 100 | Higher is better |
| Velocity | Completed story points per sprint | Contextual |
| Carryover Rate | Incomplete originally committed work / originally committed work × 100 | Lower is better |
| Cycle Time | Work completed − work started | Lower is better |
| Lead Time | Work completed − work created/requested | Lower is better |
| Blocked Work Ratio | Blocked active work / active work × 100 | Lower is better |
| Average Blocker Age | Total active-blocker age / active blocker count | Lower is better |
| Backlog Readiness | Ready items / assessed items × 100 across acceptance criteria, estimate, dependencies, design, testability, and Definition of Ready | Higher is better |
| Defect Rate | Defects / configured work-item, release, or story-point denominator | Lower is better |
| Escaped Defect Rate | Production defects / total defects × 100 | Lower is better |
| Dependency Age | Current date − identified/blocked date | Lower is better |
| Risk Exposure | Probability score × impact score | Lower is better |
| Release Readiness | Configured completion across code, SIT, UAT, regression, performance, security, CAB, business approval, rollback, monitoring, and support | Higher is better |

Thresholds are initial defaults and remain configurable contract fields. Release readiness is a future contract only; AX-EP01 does not make automated release decisions.
