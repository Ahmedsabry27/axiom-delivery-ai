import type { ReleaseNotes } from "../types";

export const mockReleaseNotesMap: Record<string, ReleaseNotes> = {
  "rel-001": {
    id: "rn-rel-001",
    releaseId: "REL-2026-010",
    summary:
      "AX Platform 1.0 delivers the first production-ready MVP for AI-assisted delivery monitoring and governance. The release introduces enhanced Command Center visibility, Copilot investigation workflows, human-controlled interventions, release readiness assessment and improved audit traceability. It also includes stability, authorization, performance and security improvements identified during SIT and UAT.",
    items: [
      // ==================== NEW FEATURES ====================
      {
        id: "rn-001",
        jira: {
          key: "AX-601",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-601",
        },
        category: "FEATURE",
        title: "Release Readiness Criteria",
        description:
          "Introduces structured release gates for code completion, SIT, UAT, regression, security, CAB, monitoring, rollback and support readiness. Each criterion can be marked as passed, pending, failed, missing evidence, waived or conditional.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
        businessImpact: "Provides a standardized framework for evaluating whether a release is safe for production deployment.",
        validationStatus: "SIT PASSED, UAT PASSED, Regression PASSED",
      },
      {
        id: "rn-002",
        jira: {
          key: "AX-602",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-602",
        },
        category: "FEATURE",
        title: "Release Readiness Score",
        description:
          "Calculates overall release readiness percentage from verified release evidence, blocking criteria, conditions and exceptions. Scores are weighted to reflect mandatory vs optional criteria and blocked vs pending status.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
        businessImpact: "Enables Release Managers to quickly assess the overall health of a release through a single numeric metric.",
        validationStatus: "SIT PASSED, UAT PASSED",
      },
      {
        id: "rn-003",
        jira: {
          key: "AX-603",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-603",
        },
        category: "FEATURE",
        title: "AI Release Recommendation",
        description:
          "Generates explainable GO, CONDITIONAL GO, NO-GO or INSUFFICIENT EVIDENCE recommendations based on release evidence, blocking criteria and conditions. The recommendation is transparent and human-readable but does not override human authority.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
        businessImpact: "Provides Release Managers with a consistent and explainable AI-generated assessment before final Go / No-Go decision.",
        validationStatus: "SIT PASSED, UAT PASSED, Regression PASSED",
      },
      {
        id: "rn-004",
        jira: {
          key: "AX-604",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-604",
        },
        category: "FEATURE",
        title: "Human Go / No-Go Governance",
        description:
          "Provides an auditable decision workflow where authorized release owners record the final production decision. Captures decision owner, decision, rationale, conditions and timestamp for full traceability and audit compliance.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
        businessImpact: "Ensures clear accountability and audit evidence for production release approval.",
        validationStatus: "SIT PASSED, UAT PASSED",
      },
      {
        id: "rn-005",
        jira: {
          key: "AX-405",
          type: "Story",
          epicKey: "AX-EP02",
          url: "https://jira.example.com/browse/AX-405",
        },
        category: "FEATURE",
        title: "Command Center Attention Item Prioritization",
        description:
          "Enhanced attention item ranking to surface critical delivery risks and blocked dependencies more prominently in the Command Center dashboard.",
        component: "Command Center",
        owner: "AX Intelligence",
        status: "DONE",
        businessImpact: "Helps teams identify and resolve the most critical delivery blockers faster.",
      },
      {
        id: "rn-006",
        jira: {
          key: "AX-420",
          type: "Story",
          epicKey: "AX-EP05",
          url: "https://jira.example.com/browse/AX-420",
        },
        category: "FEATURE",
        title: "Copilot Evidence Investigation",
        description:
          "Extends Copilot to collect, synthesize and present delivery evidence across testing, governance, operational and security domains in a unified investigation workflow.",
        component: "Copilot",
        owner: "AX Intelligence",
        status: "DONE",
        businessImpact: "Enables Release Managers to gather evidence more efficiently.",
      },
      // ==================== ENHANCEMENTS ====================
      {
        id: "rn-007",
        jira: {
          key: "AX-542",
          type: "Task",
          url: "https://jira.example.com/browse/AX-542",
        },
        category: "ENHANCEMENT",
        title: "Enhanced Copilot Evidence Presentation",
        description:
          "Improved evidence cards within Copilot investigations to display source, confidence, timestamp and ownership more clearly. Added visual indicators for evidence verification status.",
        component: "Copilot",
        owner: "AX Intelligence",
        status: "DONE",
        businessImpact: "Improves investigation traceability and decision confidence.",
      },
      {
        id: "rn-008",
        jira: {
          key: "AX-558",
          type: "Task",
          url: "https://jira.example.com/browse/AX-558",
        },
        category: "ENHANCEMENT",
        title: "Command Center Attention Prioritization",
        description:
          "Improved attention-item ranking to surface critical delivery risks and blocked dependencies more prominently based on impact and age.",
        component: "Command Center",
        owner: "AX Intelligence",
        status: "DONE",
        businessImpact: "Helps teams focus on the most impactful work first.",
      },
      {
        id: "rn-009",
        jira: {
          key: "AX-563",
          type: "Task",
          url: "https://jira.example.com/browse/AX-563",
        },
        category: "ENHANCEMENT",
        title: "Improved Evidence Filter & Search",
        description:
          "Enhanced evidence filtering and search capabilities to support filtering by category, owner, status and date range.",
        component: "Evidence",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-010",
        jira: {
          key: "AX-571",
          type: "Task",
          url: "https://jira.example.com/browse/AX-571",
        },
        category: "ENHANCEMENT",
        title: "Release Readiness Modal Responsiveness",
        description:
          "Improved mobile and tablet responsiveness for the release readiness assessment modal and drawer components.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-011",
        jira: {
          key: "AX-575",
          type: "Task",
          url: "https://jira.example.com/browse/AX-575",
        },
        category: "ENHANCEMENT",
        title: "Decision History Filtering",
        description:
          "Added ability to filter release decision history by decision type, owner and date range.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-012",
        jira: {
          key: "AX-578",
          type: "Task",
          url: "https://jira.example.com/browse/AX-578",
        },
        category: "ENHANCEMENT",
        title: "Readiness Criteria Export",
        description:
          "Added ability to export release readiness criteria and assessment results as CSV or PDF for audit and stakeholder communication.",
        component: "Release Governance",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-013",
        jira: {
          key: "AX-582",
          type: "Task",
          url: "https://jira.example.com/browse/AX-582",
        },
        category: "ENHANCEMENT",
        title: "Approval Workflow Notifications",
        description:
          "Enhanced notification system to alert relevant stakeholders when approval actions are required.",
        component: "Approvals",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-014",
        jira: {
          key: "AX-588",
          type: "Task",
          url: "https://jira.example.com/browse/AX-588",
        },
        category: "ENHANCEMENT",
        title: "Audit Event Detail Enrichment",
        description:
          "Improved audit event logging to include additional context such as user role, team affiliation and impact classification.",
        component: "Audit",
        owner: "AX Platform",
        status: "DONE",
      },
      {
        id: "rn-015",
        jira: {
          key: "AX-591",
          type: "Task",
          url: "https://jira.example.com/browse/AX-591",
        },
        category: "ENHANCEMENT",
        title: "Release Portfolio Table Customization",
        description:
          "Added ability to customize which columns are visible in the release portfolio table view.",
        component: "Releases",
        owner: "AX Platform",
        status: "DONE",
      },
      // ==================== BUG FIXES ====================
      {
        id: "rn-016",
        jira: {
          key: "AX-487",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-487",
        },
        category: "BUG_FIX",
        title: "Incorrect readiness status after evidence refresh",
        severity: "HIGH",
        description:
          "The readiness view could continue showing the previous criterion state after new evidence was submitted. This resulted in stale readiness scores being displayed to users.",
        resolution:
          "Readiness state is now recalculated immediately after evidence updates. Cache invalidation was added to ensure fresh state is fetched.",
        component: "Release Readiness",
        status: "FIXED",
        validationStatus: "Regression Passed",
      },
      {
        id: "rn-017",
        jira: {
          key: "AX-492",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-492",
        },
        category: "BUG_FIX",
        title: "Cross-tenant release evidence visible in relationship query",
        severity: "CRITICAL",
        description:
          "A potential security issue where evidence from one tenant could be visible in release relationship queries from another tenant under specific conditions.",
        resolution:
          "Tenant-scoped relationship validation was strengthened and negative tenant-access scenarios were added to regression tests.",
        component: "Release Governance",
        status: "FIXED",
        validationStatus: "Security Regression Passed",
      },
      {
        id: "rn-018",
        jira: {
          key: "AX-498",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-498",
        },
        category: "BUG_FIX",
        title: "Long evidence titles overflowed mobile investigation drawer",
        severity: "MEDIUM",
        description:
          "Evidence titles longer than 64 characters would overflow the mobile investigation drawer, making the UI inaccessible.",
        resolution:
          "Implemented text truncation with ellipsis and tooltip on mobile layouts for evidence titles.",
        component: "Copilot",
        status: "FIXED",
        validationStatus: "Responsive Playwright Passed",
      },
      {
        id: "rn-019",
        jira: {
          key: "AX-503",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-503",
        },
        category: "BUG_FIX",
        title: "Decision history timestamp displayed using inconsistent timezone formatting",
        severity: "MEDIUM",
        description:
          "Decision history timestamps were formatted inconsistently across different views, sometimes showing UTC and sometimes local time without clear indication.",
        resolution:
          "Implemented consistent UTC-based formatting with user-local timezone display option.",
        component: "Release Governance",
        status: "FIXED",
        validationStatus: "E2E Passed",
      },
      {
        id: "rn-020",
        jira: {
          key: "AX-509",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-509",
        },
        category: "BUG_FIX",
        title: "Release filter state reset when returning from release details",
        severity: "MEDIUM",
        description:
          "When navigating back from a release detail view to the release portfolio, the previously applied filters were lost.",
        resolution:
          "Implemented client-side filter state persistence using URL query parameters.",
        component: "Releases",
        status: "FIXED",
        validationStatus: "E2E Passed",
      },
      {
        id: "rn-021",
        jira: {
          key: "AX-515",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-515",
        },
        category: "BUG_FIX",
        title: "Approval modal did not validate required fields before submission",
        severity: "HIGH",
        description:
          "Users could submit the approval modal with empty rationale field, leading to incomplete audit records.",
        resolution:
          "Added client-side and server-side validation for required fields before submission is allowed.",
        component: "Approvals",
        status: "FIXED",
        validationStatus: "E2E Passed",
      },
      {
        id: "rn-022",
        jira: {
          key: "AX-521",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-521",
        },
        category: "BUG_FIX",
        title: "Blocked criteria notification not sent when criterion status changed",
        severity: "HIGH",
        description:
          "When a criterion status changed from passed to blocked, affected stakeholders were not notified.",
        resolution:
          "Implemented criterion status change detection and notification dispatch.",
        component: "Release Governance",
        status: "FIXED",
        validationStatus: "Regression Passed",
      },
      {
        id: "rn-023",
        jira: {
          key: "AX-527",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-527",
        },
        category: "BUG_FIX",
        title: "Release readiness PDF export did not preserve formatting",
        severity: "LOW",
        description:
          "PDF export of release readiness assessment lost styling and tables were rendered incorrectly.",
        resolution:
          "Improved PDF export template formatting and table layout.",
        component: "Release Governance",
        status: "FIXED",
        validationStatus: "Regression Passed",
      },
      // ==================== TECHNICAL CHANGES ====================
      {
        id: "rn-024",
        jira: {
          key: "AX-605",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-605",
        },
        category: "TECHNICAL",
        title: "End-to-End Runtime Tracing",
        description:
          "Introduces a consistent trace identifier across Request → Orchestrator → Agent → Model → Tool → Result. Enables end-to-end observability of release deployment operations and AI Copilot investigation workflows.",
        component: "Runtime",
        owner: "AX Platform",
        status: "DONE",
        validationStatus: "SIT PASSED",
      },
      {
        id: "rn-025",
        jira: {
          key: "AX-607",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-607",
        },
        category: "TECHNICAL",
        title: "AI Model Usage Monitoring",
        description:
          "Adds model, token, cost, latency, success, retry and failure monitoring across deployed models.",
        component: "Monitoring",
        owner: "AX Platform",
        status: "DONE",
        validationStatus: "SIT PASSED",
      },
      // ==================== SECURITY IMPROVEMENTS ====================
      {
        id: "rn-026",
        jira: {
          key: "AX-606",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-606",
        },
        category: "SECURITY",
        title: "Authorization Hardening",
        description:
          "Strengthened validation for role-based access, tenant isolation, tool permissions, approval permissions and administration permissions. Added comprehensive testing for edge cases and negative scenarios.",
        component: "Security",
        owner: "AX Platform",
        status: "DONE",
        validationStatus: "Security Regression Passed",
      },
      {
        id: "rn-027",
        jira: {
          key: "AX-609",
          type: "Story",
          epicKey: "AX-EP06",
          url: "https://jira.example.com/browse/AX-609",
        },
        category: "SECURITY",
        title: "Security Review Controls",
        description:
          "Validated secret handling, safe logging, PII handling, prompt-injection controls, data isolation, retention and output filtering.",
        component: "Security",
        owner: "AX Platform",
        status: "DONE",
        validationStatus: "Security Regression Passed",
      },
      // ==================== PERFORMANCE IMPROVEMENTS ====================
      {
        id: "rn-028",
        jira: {
          key: "AX-571",
          type: "Task",
          url: "https://jira.example.com/browse/AX-571",
        },
        category: "PERFORMANCE",
        title: "Reduced Copilot investigation latency",
        description:
          "Improved evidence retrieval and orchestration processing, reducing median investigation response latency from 2.8s to 1.9s (32% improvement).",
        component: "Copilot",
        owner: "AX Platform",
        status: "DONE",
        businessImpact: "Faster investigation workflows improve user experience and decision speed.",
      },
      // ==================== KNOWN ISSUES ====================
      {
        id: "rn-029",
        jira: {
          key: "AX-611",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-611",
        },
        category: "KNOWN_ISSUE",
        title: "Monitoring validation may take up to 30 seconds after deployment",
        component: "Observability",
        severity: "LOW",
        status: "KNOWN_ISSUE",
        description:
          "Readiness monitoring status may remain temporarily pending while production telemetry initialization completes.",
        workaround:
          "Refresh the release assessment after telemetry initialization (approximately 30 seconds after deployment).",
        targetFix: "AX Platform 1.0.1",
        relatedCriterionId: "ax-610",
      },
      {
        id: "rn-030",
        jira: {
          key: "AX-612",
          type: "Bug",
          url: "https://jira.example.com/browse/AX-612",
        },
        category: "KNOWN_ISSUE",
        title: "Evidence search does not index historical evidence from prior releases",
        component: "Evidence",
        severity: "LOW",
        status: "KNOWN_ISSUE",
        description:
          "The evidence search feature only indexes evidence from the current and previous release. Historical evidence from releases older than two versions may not appear in search results.",
        workaround:
          "Use the evidence detail view to locate older evidence or filter by date range.",
        targetFix: "AX Platform 1.1",
      },
    ],
    deploymentNotes: {
      window: "04 Oct 2026 · 22:00–23:30",
      strategy: "Rolling deployment",
      expectedDowntime: "None expected",
      requiresDatabaseMigration: true,
      migrationHeadHash: "c5a8e3d0f216",
      featureFlags: ["release-readiness-enabled", "ai-evaluation-enabled", "copilot-enhanced-enabled"],
      requiresPostDeploymentValidation: true,
    },
    configurationChanges: {
      newEnvironmentVariables: ["COPILOT_MODEL_ENDPOINT", "EVIDENCE_CACHE_TTL", "READINESS_EVAL_TIMEOUT"],
      featureFlags: ["release-readiness-enabled", "ai-evaluation-enabled", "copilot-enhanced-enabled"],
      infrastructureChanges: "No destructive infrastructure changes",
      databaseChanges: "1 schema migration (evidence_index table)",
    },
    dependencies: [
      { name: "AWS Bedrock", status: "Available" },
      { name: "PostgreSQL", status: "Migration required" },
      { name: "Cognito", status: "No change" },
      { name: "Monitoring", status: "Dashboard validation required" },
      { name: "Azure Monitor", status: "Telemetry streaming required" },
    ],
    impactedComponents: [
      "Command Center",
      "Copilot",
      "Release Management",
      "Governance",
      "Audit",
      "Runtime Orchestrator",
      "Monitoring",
      "Evidence",
    ],
    impactedPersonas: [
      "Release Managers",
      "Product Owners",
      "Delivery Leads",
      "Administrators",
      "Engineering",
      "Operations / SRE",
      "Support Teams",
      "CAB / Change Management",
    ],
    validationSummary: [
      { label: "Unit Tests", status: "PASS", count: "509 / 509" },
      { label: "Frontend Tests", status: "PASS", count: "72 / 72" },
      { label: "Responsive Playwright", status: "PASS", count: "6 / 6" },
      { label: "Authenticated E2E", status: "PASS", count: "8 / 8" },
      { label: "Regression", status: "PASS", count: "428 / 428" },
      { label: "Security Scan", status: "PASS", detail: "0 critical, 0 high findings" },
      { label: "Production Build", status: "PASS" },
    ],
    jiraTraceability: {
      totalItems: 34,
      linkedItems: 34,
      epicCoverage: [
        { epicKey: "AX-EP06", epicTitle: "Release Readiness MVP", itemCount: 18 },
        { epicKey: "AX-EP05", epicTitle: "Copilot Evidence & Investigation", itemCount: 8 },
        { epicKey: "AX-EP02", epicTitle: "Command Center", itemCount: 5 },
        { epicKey: "Technical", epicTitle: "Technical Hardening", itemCount: 3 },
      ],
    },
  },
  "rel-002": {
    id: "rn-rel-002",
    releaseId: "REL-2026-011",
    summary:
      "AX Platform 1.1 expands release governance with reusable readiness templates, richer portfolio insights and faster evidence review. This UAT candidate also includes security and performance hardening, with one known export issue still under investigation.",
    items: [
      { id: "rn-101", jira: { key: "AX-641", type: "Story", epicKey: "AX-EP07", url: "https://jira.example.com/browse/AX-641" }, category: "FEATURE", title: "Reusable readiness templates", description: "Allows release managers to create readiness assessments from governed templates by product, environment and release type.", component: "Release Governance", owner: "AX Platform", status: "DONE", businessImpact: "Reduces setup effort and makes release gates consistent across delivery teams.", validationStatus: "SIT PASSED · UAT IN PROGRESS" },
      { id: "rn-102", jira: { key: "AX-648", type: "Story", epicKey: "AX-EP07", url: "https://jira.example.com/browse/AX-648" }, category: "FEATURE", title: "Portfolio release health trends", description: "Adds readiness, blocker and decision trends to the release portfolio for early risk identification.", component: "Releases", owner: "AX Intelligence", status: "DONE", businessImpact: "Gives programme leaders a forward-looking view of release risk.", validationStatus: "SIT PASSED · UAT PENDING" },
      { id: "rn-103", jira: { key: "AX-652", type: "Task", url: "https://jira.example.com/browse/AX-652" }, category: "ENHANCEMENT", title: "Evidence bulk verification", description: "Enables authorized reviewers to verify multiple evidence records from a single review queue.", component: "Evidence", owner: "Quality Engineering", status: "DONE", validationStatus: "SIT PASSED" },
      { id: "rn-104", jira: { key: "AX-659", type: "Bug", url: "https://jira.example.com/browse/AX-659" }, category: "BUG_FIX", title: "Readiness filters reset after drawer navigation", description: "Returning from a readiness detail drawer cleared the active portfolio filters.", resolution: "Persisted filter state in the release route search parameters.", component: "Release Governance", status: "FIXED", severity: "MEDIUM", validationStatus: "REGRESSION PASSED" },
      { id: "rn-105", jira: { key: "AX-663", type: "Task", url: "https://jira.example.com/browse/AX-663" }, category: "SECURITY", title: "Evidence download authorization hardening", description: "Adds resource-level authorization checks and audit events to all evidence download operations.", component: "Security", owner: "Information Security", status: "DONE", validationStatus: "SECURITY REVIEW PENDING" },
      { id: "rn-106", jira: { key: "AX-668", type: "Task", url: "https://jira.example.com/browse/AX-668" }, category: "PERFORMANCE", title: "Faster release portfolio loading", description: "Introduces batched readiness aggregation and response caching for large release portfolios.", component: "Releases", owner: "Platform Engineering", status: "DONE", businessImpact: "Reduces median portfolio load time from 2.1s to 1.2s.", validationStatus: "LOAD TEST PASSED" },
      { id: "rn-107", jira: { key: "AX-671", type: "Bug", url: "https://jira.example.com/browse/AX-671" }, category: "KNOWN_ISSUE", title: "PDF export may omit long condition notes", description: "Condition text longer than two pages can be truncated in the UAT PDF export.", component: "Release Governance", severity: "MEDIUM", status: "KNOWN_ISSUE", workaround: "Use CSV export or open the readiness assessment to review the full condition text.", targetFix: "AX Platform 1.1.1" },
    ],
    deploymentNotes: { window: "18 Oct 2026 · 19:00–20:00", strategy: "UAT rolling deployment", expectedDowntime: "None expected", requiresDatabaseMigration: true, migrationHeadHash: "9b41fd8207aa", featureFlags: ["readiness-templates", "portfolio-health-trends"], requiresPostDeploymentValidation: true },
    configurationChanges: { newEnvironmentVariables: ["READINESS_TEMPLATE_CACHE_TTL"], featureFlags: ["readiness-templates", "portfolio-health-trends"], infrastructureChanges: "Adds a dedicated cache policy for portfolio aggregates", databaseChanges: "Adds readiness_template and template_criterion tables" },
    dependencies: [{ name: "PostgreSQL", status: "Migration required" }, { name: "Azure Monitor", status: "UAT dashboard pending" }, { name: "Jira", status: "Available" }],
    impactedComponents: ["Release Governance", "Releases", "Evidence", "Security"],
    impactedPersonas: ["Release Managers", "Delivery Leads", "Quality Engineering", "Information Security"],
    validationSummary: [{ label: "Unit Tests", status: "PASS", count: "536 / 536" }, { label: "SIT", status: "PASS", count: "118 / 118" }, { label: "UAT", status: "PENDING", count: "21 / 34" }, { label: "Security Review", status: "PENDING", detail: "Authorization evidence awaiting sign-off" }, { label: "PDF Export Regression", status: "FAIL", count: "1 / 18 failed" }],
    jiraTraceability: { totalItems: 7, linkedItems: 7, epicCoverage: [{ epicKey: "AX-EP07", epicTitle: "Release Governance Expansion", itemCount: 2 }, { epicKey: "Delivery", epicTitle: "Quality and Hardening", itemCount: 5 }] },
  },
  "rel-003": {
    id: "rn-rel-003",
    releaseId: "REL-2026-009",
    summary: "AX Platform 0.9.5 is a completed maintenance release focused on stability, audit accuracy and production observability. All planned fixes were deployed successfully and post-deployment validation passed.",
    items: [
      { id: "rn-201", jira: { key: "AX-574", type: "Bug", url: "https://jira.example.com/browse/AX-574" }, category: "BUG_FIX", title: "Duplicate audit events during retry", description: "Transient API retries could write the same governance audit event twice.", resolution: "Added idempotency keys to the audit event ingestion path.", component: "Audit", owner: "AX Platform", status: "FIXED", severity: "HIGH", validationStatus: "PRODUCTION VERIFIED" },
      { id: "rn-202", jira: { key: "AX-579", type: "Bug", url: "https://jira.example.com/browse/AX-579" }, category: "BUG_FIX", title: "Stale blocker count on release cards", description: "Release cards did not immediately reflect blockers resolved from the detail view.", resolution: "Invalidated the portfolio cache after blocker state changes.", component: "Releases", status: "FIXED", severity: "MEDIUM", validationStatus: "REGRESSION PASSED" },
      { id: "rn-203", jira: { key: "AX-583", type: "Task", url: "https://jira.example.com/browse/AX-583" }, category: "PERFORMANCE", title: "Reduced evidence query latency", description: "Adds targeted indexes for release, criterion and verification-status evidence queries.", component: "Evidence", owner: "Platform Engineering", status: "DONE", businessImpact: "Improves p95 evidence query latency by 38%.", validationStatus: "PRODUCTION VERIFIED" },
      { id: "rn-204", jira: { key: "AX-587", type: "Task", url: "https://jira.example.com/browse/AX-587" }, category: "TECHNICAL", title: "Improved trace correlation for background jobs", description: "Propagates release trace identifiers through asynchronous evidence processing jobs.", component: "Runtime", owner: "AX Platform", status: "DONE", validationStatus: "OBSERVABILITY CHECK PASSED" },
      { id: "rn-205", jira: { key: "AX-590", type: "Task", url: "https://jira.example.com/browse/AX-590" }, category: "SECURITY", title: "Sanitized connector error logging", description: "Redacts connector tokens and sensitive query parameters before application errors are persisted.", component: "Security", owner: "Information Security", status: "DONE", validationStatus: "SECURITY SCAN PASSED" },
    ],
    deploymentNotes: { window: "22 Sep 2026 · 21:00–21:42", strategy: "Rolling deployment", expectedDowntime: "None observed", requiresDatabaseMigration: true, migrationHeadHash: "702f38ad1e64", requiresPostDeploymentValidation: true },
    configurationChanges: { infrastructureChanges: "No infrastructure changes", databaseChanges: "Added two non-blocking evidence indexes" },
    dependencies: [{ name: "PostgreSQL", status: "Migration completed" }, { name: "Azure Monitor", status: "Validated" }],
    impactedComponents: ["Audit", "Releases", "Evidence", "Runtime", "Security"],
    impactedPersonas: ["Release Managers", "Auditors", "Operations / SRE"],
    validationSummary: [{ label: "Regression", status: "PASS", count: "391 / 391" }, { label: "Security Scan", status: "PASS", detail: "0 critical, 0 high findings" }, { label: "Post-deployment Smoke Tests", status: "PASS", count: "24 / 24" }],
    jiraTraceability: { totalItems: 5, linkedItems: 5, epicCoverage: [{ epicKey: "Maintenance", epicTitle: "0.9.5 Production Hardening", itemCount: 5 }] },
  },
  "rel-004": {
    id: "rn-rel-004",
    releaseId: "REL-2026-012",
    summary: "AX Platform 1.2 is in planning. The provisional scope introduces policy simulation, cross-release dependency mapping and configurable executive reporting; details and deployment requirements will be refined as stories pass solution review.",
    items: [
      { id: "rn-301", jira: { key: "AX-701", type: "Story", epicKey: "AX-EP08", url: "https://jira.example.com/browse/AX-701" }, category: "FEATURE", title: "Release policy simulation", description: "Lets governance teams preview how proposed policy changes would affect active and upcoming releases before publishing them.", component: "Release Governance", owner: "AX Platform", status: "DEFERRED", businessImpact: "Reduces the risk of unintended release blocks from policy changes.", validationStatus: "SOLUTION REVIEW PENDING" },
      { id: "rn-302", jira: { key: "AX-706", type: "Story", epicKey: "AX-EP08", url: "https://jira.example.com/browse/AX-706" }, category: "FEATURE", title: "Cross-release dependency map", description: "Visualizes service, change and deployment dependencies across releases in the portfolio.", component: "Releases", owner: "AX Intelligence", status: "DEFERRED", businessImpact: "Helps programme teams identify sequencing conflicts earlier.", validationStatus: "DESIGN IN PROGRESS" },
      { id: "rn-303", jira: { key: "AX-711", type: "Story", epicKey: "AX-EP08", url: "https://jira.example.com/browse/AX-711" }, category: "ENHANCEMENT", title: "Configurable executive release digest", description: "Adds configurable sections, schedules and recipient groups to executive release summaries.", component: "Reporting", owner: "AX Platform", status: "DEFERRED", validationStatus: "ACCEPTANCE CRITERIA DRAFT" },
      { id: "rn-304", jira: { key: "AX-718", type: "Task", url: "https://jira.example.com/browse/AX-718" }, category: "TECHNICAL", title: "Versioned governance policy schema", description: "Introduces a versioned policy contract to support simulation, comparison and safe rollback.", component: "Governance Runtime", owner: "Platform Engineering", status: "DEFERRED", validationStatus: "TECHNICAL SPIKE PLANNED" },
    ],
    deploymentNotes: { window: "02 Nov 2026 · provisional", strategy: "To be confirmed", expectedDowntime: "To be assessed", requiresDatabaseMigration: false, featureFlags: ["policy-simulation", "dependency-map"], requiresPostDeploymentValidation: true },
    configurationChanges: { featureFlags: ["policy-simulation", "dependency-map"], infrastructureChanges: "Under architecture review", databaseChanges: "Schema impact under assessment" },
    dependencies: [{ name: "Architecture Review", status: "Pending" }, { name: "Product Scope Approval", status: "Pending" }],
    impactedComponents: ["Release Governance", "Releases", "Reporting", "Governance Runtime"],
    impactedPersonas: ["Release Managers", "Programme Leads", "Governance Administrators", "Executives"],
    validationSummary: [{ label: "Solution Review", status: "PENDING", detail: "2 of 4 stories reviewed" }, { label: "Threat Model", status: "PENDING", detail: "Workshop scheduled" }, { label: "Test Plan", status: "PENDING", detail: "Draft in progress" }],
    jiraTraceability: { totalItems: 4, linkedItems: 4, epicCoverage: [{ epicKey: "AX-EP08", epicTitle: "Intelligent Portfolio Governance", itemCount: 3 }, { epicKey: "Architecture", epicTitle: "Platform Foundations", itemCount: 1 }] },
  },
};

export function getMockReleaseNotesById(releaseId: string | undefined) {
  return mockReleaseNotesMap[releaseId ?? "rel-001"];
}
