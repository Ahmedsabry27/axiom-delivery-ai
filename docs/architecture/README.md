# Axiom Delivery AI architecture pack

This pack documents the evidence-based current architecture and a clearly separated target AWS reference architecture for technical, security, governance, onboarding and deployment reviews.

Current state: React/Vite on AWS-hosted static delivery, Cognito authentication, FastAPI on ECS Fargate, private RDS PostgreSQL, durable governed AI runtime, integrations, approvals/actions and audit. Target state adds high availability, end-to-end TLS, account security services, alerting and tested recovery. Proposed elements are dashed and never presented as implemented.

## Diagram catalogue

| # | View | PNG | SVG | Source |
|---|---|---|---|---|
| 00 | Platform context | [PNG](png/00-platform-context.png) | [SVG](svg/00-platform-context.svg) | [JSON](source/00-platform-context.json) |
| 01 | Current platform | [PNG](png/01-current-platform-architecture.png) | [SVG](svg/01-current-platform-architecture.svg) | [JSON](source/01-current-platform-architecture.json) |
| 02 | Target AWS | [PNG](png/02-target-aws-architecture.png) | [SVG](svg/02-target-aws-architecture.svg) | [JSON](source/02-target-aws-architecture.json) |
| 03 | AWS network | [PNG](png/03-aws-network-architecture.png) | [SVG](svg/03-aws-network-architecture.svg) | [JSON](source/03-aws-network-architecture.json) |
| 04 | Frontend | [PNG](png/04-frontend-architecture.png) | [SVG](svg/04-frontend-architecture.svg) | [JSON](source/04-frontend-architecture.json) |
| 05 | Backend services | [PNG](png/05-backend-service-architecture.png) | [SVG](svg/05-backend-service-architecture.svg) | [JSON](source/05-backend-service-architecture.json) |
| 06 | AI runtime | [PNG](png/06-ai-runtime-architecture.png) | [SVG](svg/06-ai-runtime-architecture.svg) | [JSON](source/06-ai-runtime-architecture.json) |
| 07 | Agents and tools | [PNG](png/07-agent-and-tool-architecture.png) | [SVG](svg/07-agent-and-tool-architecture.svg) | [JSON](source/07-agent-and-tool-architecture.json) |
| 08 | Data | [PNG](png/08-data-architecture.png) | [SVG](svg/08-data-architecture.svg) | [JSON](source/08-data-architecture.json) |
| 09 | Security | [PNG](png/09-security-and-authorization.png) | [SVG](svg/09-security-and-authorization.svg) | [JSON](source/09-security-and-authorization.json) |
| 10 | Integrations | [PNG](png/10-integration-architecture.png) | [SVG](svg/10-integration-architecture.svg) | [JSON](source/10-integration-architecture.json) |
| 11 | Knowledge/evidence | [PNG](png/11-knowledge-and-evidence.png) | [SVG](svg/11-knowledge-and-evidence.svg) | [JSON](source/11-knowledge-and-evidence.json) |
| 12 | Approval/action | [PNG](png/12-approval-and-action-flow.png) | [SVG](svg/12-approval-and-action-flow.svg) | [JSON](source/12-approval-and-action-flow.json) |
| 13 | Observability | [PNG](png/13-observability-and-operations.png) | [SVG](svg/13-observability-and-operations.svg) | [JSON](source/13-observability-and-operations.json) |
| 14 | CI/CD | [PNG](png/14-cicd-deployment.png) | [SVG](svg/14-cicd-deployment.svg) | [JSON](source/14-cicd-deployment.json) |
| 15 | Backup/recovery | [PNG](png/15-backup-recovery.png) | [SVG](svg/15-backup-recovery.svg) | [JSON](source/15-backup-recovery.json) |
| 16 | Runtime sequence | [PNG](png/16-runtime-request-sequence.png) | [SVG](svg/16-runtime-request-sequence.svg) | [JSON](source/16-runtime-request-sequence.json) |
| 17 | Copilot evidence sequence | [PNG](png/17-copilot-evidence-sequence.png) | [SVG](svg/17-copilot-evidence-sequence.svg) | [JSON](source/17-copilot-evidence-sequence.json) |
| 18 | Approved action sequence | [PNG](png/18-approved-action-sequence.png) | [SVG](svg/18-approved-action-sequence.svg) | [JSON](source/18-approved-action-sequence.json) |

[Architecture contact sheet](png/architecture-contact-sheet.png)

## Supporting analysis

- [Inventory](architecture-inventory.md)
- [Assumptions](architecture-assumptions.md)
- [AWS services](aws-service-inventory.md)
- [Traceability](architecture-traceability.md)
- [Non-functional architecture](non-functional-architecture.md)
- [Gap analysis](architecture-gap-analysis.md)
- [Outcome](AX-ARCH-01-outcome.md)

## Reproduce and validate

```bash
python3 docs/architecture/scripts/generate_architecture.py
node docs/architecture/scripts/render_architecture.mjs
# macOS fallback when Chromium sandboxing is unavailable:
bash docs/architecture/scripts/render_architecture.sh
python3 docs/architecture/scripts/validate_architecture.py
```

The renderer uses the repository's existing Playwright development dependency. Diagram tooling is isolated under `docs/architecture`; application dependencies are unchanged. AWS services use a consistent AWS-orange service tile and AWS boundary convention. Solid borders indicate evidenced elements; dashed borders indicate proposed or unknown elements.

Last generated: 2026-08-24. Repository commit: `73b4a14`.

Known limitations: accepted SLO/RTO/RPO, production account topology, recovery evidence and final frontend hosting choice remain unresolved; see assumptions and gap analysis.
