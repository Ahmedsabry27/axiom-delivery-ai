import {
  createBrowserRouter,
  Navigate,
} from "react-router-dom";
import { lazy, Suspense } from "react";


import EnterpriseLayout from "../components/layout/EnterpriseLayout";

// Route pages are intentionally lazy so chat syntax highlighting, charts, and
// administration dependencies do not inflate the application entry chunk.
// eslint-disable-next-line react-refresh/only-export-components
const ChatPage=lazy(()=>import("../pages/ChatPage"));
// eslint-disable-next-line react-refresh/only-export-components
const DashboardPage=lazy(()=>import("../pages/dashboard/DashboardPage"));
// eslint-disable-next-line react-refresh/only-export-components
const MyDayPage=lazy(()=>import("../pages/my-day/MyDayPage"));
// eslint-disable-next-line react-refresh/only-export-components
const SprintPortfolioPage=lazy(()=>import("../pages/sprints/SprintPortfolioPage"));
// eslint-disable-next-line react-refresh/only-export-components
const SprintDetailPage=lazy(()=>import("../pages/sprints/SprintDetailPage"));
const portfolioPage=name=>lazy(()=>import("../pages/portfolio/PortfolioPages").then(module=>({default:module[name]})));
const PortfolioOverview=portfolioPage("PortfolioOverview"),ProgrammesPage=portfolioPage("ProgrammesPage"),ProgrammeDetailPage=portfolioPage("ProgrammeDetailPage"),ProjectsPage=portfolioPage("ProjectsPage"),ProjectDetailPage=portfolioPage("ProjectDetailPage"),InvestmentsPage=portfolioPage("InvestmentsPage"),MilestonesPage=portfolioPage("MilestonesPage"),OutcomesPage=portfolioPage("OutcomesPage"),PortfolioInsightsPage=portfolioPage("InsightsPage");
// eslint-disable-next-line react-refresh/only-export-components
const RAIDPage=lazy(()=>import("../pages/raid/RAIDPage"));
// eslint-disable-next-line react-refresh/only-export-components
const DependencyIntelligencePage=lazy(()=>import("../pages/dependencies/DependencyIntelligencePage"));
// eslint-disable-next-line react-refresh/only-export-components
const WorkflowsPage=lazy(()=>import("../pages/workflows/WorkflowsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const WorkflowCreatePage=lazy(()=>import("../pages/workflows/WorkflowCreatePage"));
// eslint-disable-next-line react-refresh/only-export-components
const WorkflowWorkspacePage=lazy(()=>import("../pages/workflows/WorkflowWorkspacePage"));
// Route-level lazy components intentionally live beside the router configuration.
// eslint-disable-next-line react-refresh/only-export-components
const AgentsPage=lazy(()=>import("../pages/agents/AgentsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const AgentCreatePage=lazy(()=>import("../pages/agents/AgentCreatePage"));
// eslint-disable-next-line react-refresh/only-export-components
const AgentWorkspacePage=lazy(()=>import("../pages/agents/AgentWorkspacePage"));
// eslint-disable-next-line react-refresh/only-export-components
const AgentExecutionDetailsPage=lazy(()=>import("../pages/agents/AgentDetailsPage").then(module=>({default:module.AgentExecutionDetailsPage})));
const deferred=Component=><Suspense fallback={<main className="p-8" aria-live="polite">Loading page…</main>}><Component/></Suspense>;
// eslint-disable-next-line react-refresh/only-export-components
const ActionsPage=lazy(()=>import("../pages/actions/ActionsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const ReleasesPage=lazy(()=>import("../features/releases/ReleasesPage"));
// eslint-disable-next-line react-refresh/only-export-components
const ReleaseDetailsPage=lazy(()=>import("../features/releases/ReleaseDetailsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const ApprovalsPage=lazy(()=>import("../pages/approvals/ApprovalsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const MeetingsPage=lazy(()=>import("../pages/meetings/MeetingsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const CeremonyPages=lazy(()=>import("../pages/ceremonies/CeremonyPages"));
// eslint-disable-next-line react-refresh/only-export-components
const AuditPage=lazy(()=>import("../pages/audit/AuditPage"));
// eslint-disable-next-line react-refresh/only-export-components
const SettingsPage=lazy(()=>import("../pages/settings/SettingsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const KnowledgePage=lazy(()=>import("../pages/knowledge/KnowledgePage"));
// eslint-disable-next-line react-refresh/only-export-components
const ToolCatalogPage=lazy(()=>import("../pages/tools/ToolCatalogPage"));
// eslint-disable-next-line react-refresh/only-export-components
const ToolDetailsPage=lazy(()=>import("../pages/tools/ToolDetailsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const IntegrationsPage=lazy(()=>import("../pages/tools/IntegrationsPage"));
// eslint-disable-next-line react-refresh/only-export-components
const IntegrationDetailPage=lazy(()=>import("../pages/tools/IntegrationDetailPage"));
// eslint-disable-next-line react-refresh/only-export-components
const ModelPortfolioPage=lazy(()=>import("../pages/models/ModelWorkspace").then(module=>({default:module.ModelPortfolioPage})));
// eslint-disable-next-line react-refresh/only-export-components
const ModelDetailPage=lazy(()=>import("../pages/models/ModelWorkspace").then(module=>({default:module.ModelDetailPage})));
// eslint-disable-next-line react-refresh/only-export-components
const ModelRegisterPage=lazy(()=>import("../pages/models/ModelWorkspace").then(module=>({default:module.ModelRegisterPage})));
// eslint-disable-next-line react-refresh/only-export-components
const ToolExecutionsPage=lazy(()=>import("../pages/tools/ToolExecutionsPage"));
const governancePage=name=>lazy(()=>import("../pages/governance/GovernanceOperationsPages").then(module=>({default:module[name]})));
const GovernanceDashboard=governancePage("GovernanceDashboard"),PoliciesPage=governancePage("PoliciesPage"),PolicyDetailPage=governancePage("PolicyDetailPage"),PermissionsPage=governancePage("PermissionsPage"),AccessReviewsPage=governancePage("AccessReviewsPage"),AuditExplorerPage=governancePage("AuditExplorerPage"),DataControlsPage=governancePage("DataControlsPage"),AIOperationsDashboard=governancePage("AIOperationsDashboard"),ExecutionsPage=governancePage("ExecutionsPage"),EvaluationsPage=governancePage("EvaluationsPage"),CostsPage=governancePage("CostsPage"),IncidentsPage=governancePage("IncidentsPage"),GovernedDetailPage=governancePage("GovernedDetailPage");
import NotFoundPage from "../pages/NotFoundPage";
import DesignSystemPage from "../pages/dev/DesignSystemPage";
const adminPage=name=>lazy(()=>import("./AdminPages").then(module=>({default:module[name]})));
const DiscoveryPage=adminPage("DiscoveryPage"),GovernancePage=adminPage("GovernancePage"),MarketplacePage=adminPage("MarketplacePage"),MCPServerDetailsPage=adminPage("MCPServerDetailsPage"),MCPServerFormPage=adminPage("MCPServerFormPage"),MCPServersPage=adminPage("MCPServersPage"),NativeToolsPage=adminPage("NativeToolsPage"),NativeWorkspacePage=adminPage("NativeWorkspacePage"),ToolAnalyticsPage=adminPage("ToolAnalyticsPage");


export const router = createBrowserRouter([

  {
    path: "/",

    element: deferred(EnterpriseLayout),


    children: [


      // Default landing page
      {
        index: true,

        element: (
          <Navigate
            to="/command-center"
            replace
          />
        ),

      },



      {
        path: "command-center",

        element: <DashboardPage />,

        handle: {
          title: "Command Center",
          icon: "dashboard",
        },

      },
      { path: "dashboard", element: <Navigate to="/command-center" replace /> },
      { path: "my-day", element: deferred(MyDayPage) },
      { path: "portfolio", element: deferred(PortfolioOverview) },
      { path: "portfolio/programmes", element: deferred(ProgrammesPage) },
      { path: "portfolio/programmes/:programmeId", element: deferred(ProgrammeDetailPage) },
      { path: "portfolio/projects", element: deferred(ProjectsPage) },
      { path: "portfolio/projects/:projectId", element: deferred(ProjectDetailPage) },
      { path: "portfolio/investments", element: deferred(InvestmentsPage) },
      { path: "portfolio/milestones", element: deferred(MilestonesPage) },
      { path: "portfolio/outcomes", element: deferred(OutcomesPage) },
      { path: "portfolio/insights", element: deferred(PortfolioInsightsPage) },
      { path: "sprints", element: deferred(SprintPortfolioPage), handle:{title:"Sprint Intelligence"} },
      { path: "sprints/:sprintId", element: deferred(SprintDetailPage), handle:{title:"Sprint Intelligence"} },
      { path: "releases", element: deferred(ReleasesPage), handle:{title:"Releases"} },
      { path: "releases/:releaseId", element: deferred(ReleaseDetailsPage), handle:{title:"Release details"} },
      { path: "releases/:releaseId/:tab", element: deferred(ReleaseDetailsPage), handle:{title:"Release details"} },
      { path: "raid", element: deferred(RAIDPage) },
      { path: "raid/:raidId", element: deferred(RAIDPage) },
      { path: "dependencies", element: deferred(DependencyIntelligencePage), handle:{title:"Dependency Intelligence"} },
      { path: "dependencies/:dependencyId", element: deferred(DependencyIntelligencePage), handle:{title:"Dependency Intelligence"} },
      { path: "meetings/ceremonies", element: deferred(CeremonyPages), handle:{title:"Ceremony Intelligence"} },
      { path: "meetings/ceremonies/templates", element: deferred(CeremonyPages), handle:{title:"Ceremony Templates"} },
      { path: "meetings/ceremonies/templates/:templateId", element: deferred(CeremonyPages), handle:{title:"Ceremony Template"} },
      { path: "meetings/ceremonies/:ceremonyId", element: <Navigate to="overview" replace/> },
      { path: "meetings/ceremonies/:ceremonyId/:tab", element: deferred(CeremonyPages), handle:{title:"Ceremony Intelligence"} },
      { path: "meetings", element: deferred(MeetingsPage), handle:{title:"Meeting Intelligence"} },
      { path: "meetings/new", element: deferred(MeetingsPage), handle:{title:"New Meeting"} },
      { path: "meetings/:meetingId/review", element: deferred(MeetingsPage), handle:{title:"Review Meeting"} },
      { path: "meetings/:meetingId", element: deferred(MeetingsPage), handle:{title:"Meeting Intelligence"} },
      { path: "knowledge/lessons", element: deferred(KnowledgePage), handle:{title:"Lessons Learned"} },
      { path: "knowledge/lessons/:lessonId", element: deferred(KnowledgePage), handle:{title:"Lesson"} },
      { path: "approvals", element: deferred(ApprovalsPage) },
      { path: "approvals/submitted", element: deferred(ApprovalsPage) },
      { path: "approvals/history", element: deferred(ApprovalsPage) },
      { path: "approvals/delegations", element: deferred(ApprovalsPage) },
      { path: "approvals/:approvalId", element: deferred(ApprovalsPage) },
      { path: "approvals/:approvalId/:tab", element: deferred(ApprovalsPage) },
      { path: "models", element: deferred(ModelPortfolioPage) },
      { path: "models/catalog", element: deferred(ModelPortfolioPage) },
      { path: "models/register", element: deferred(ModelRegisterPage) },
      { path: "models/:modelId", element: deferred(ModelDetailPage) },
      { path: "models/:modelId/:tab", element: deferred(ModelDetailPage) },
      { path: "models/:modelId", element: deferred(GovernedDetailPage) },
      { path: "governance", element: deferred(GovernanceDashboard) },
      { path: "governance/policies", element: deferred(PoliciesPage) },
      { path: "governance/policies/:policyId", element: deferred(PolicyDetailPage) },
      { path: "governance/permissions", element: deferred(PermissionsPage) },
      { path: "governance/access-reviews", element: deferred(AccessReviewsPage) },
      { path: "governance/audit", element: deferred(AuditExplorerPage) },
      { path: "governance/audit/:eventId", element: deferred(GovernedDetailPage) },
      { path: "governance/data-controls", element: deferred(DataControlsPage) },
      { path: "ai-operations", element: deferred(AIOperationsDashboard) },
      { path: "ai-operations/executions", element: deferred(ExecutionsPage) },
      { path: "ai-operations/executions/:executionId", element: deferred(GovernedDetailPage) },
      { path: "ai-operations/evaluations", element: deferred(EvaluationsPage) },
      { path: "ai-operations/evaluations/:evaluationId", element: deferred(GovernedDetailPage) },
      { path: "ai-operations/costs", element: deferred(CostsPage) },
      { path: "ai-operations/budgets/:budgetId", element: deferred(GovernedDetailPage) },
      { path: "ai-operations/incidents", element: deferred(IncidentsPage) },
      { path: "dev/design-system", element: import.meta.env.DEV ? <DesignSystemPage /> : <NotFoundPage /> },



      {
        path: "chat",

        element: <Navigate to="/copilot" replace />,

        handle: {
          title: "Chat",
          icon: "chat",
        },

      },
      { path: "chat/:conversationId", element: <Navigate to="/copilot" replace /> },
      { path: "copilot", element: <ChatPage />, handle: { title: "AI Copilot", icon: "chat" } },
      { path: "copilot/:conversationId", element: <ChatPage />, handle: { title: "AI Copilot", icon: "chat" } },



      {
        path: "workflows",

        element: <WorkflowsPage />,

        handle: {
          title: "Workflows",
          icon: "workflow",
        },

      },
      { path: "workflows/new", element: deferred(WorkflowCreatePage) },
      { path: "workflows/builder", element: <Navigate to="/workflows/new" replace /> },
      { path: "workflows/:workflowId", element: deferred(WorkflowWorkspacePage) },
      { path: "workflows/:workflowId/:tab", element: deferred(WorkflowWorkspacePage) },
      { path: "workflows/:workflowId/runs/:runId", element: deferred(WorkflowWorkspacePage) },



      {
        path: "agents",

        element: deferred(AgentsPage),

        handle: {
          title: "Agents",
          icon: "agent",
        },

      },
      { path: "agents/new", element: deferred(AgentCreatePage) },
      { path: "agents/:agentId", element: deferred(AgentWorkspacePage) },
      { path: "agents/:agentId/:tab", element: deferred(AgentWorkspacePage) },
      { path: "agents/:agentId/executions/:executionId", element: deferred(AgentExecutionDetailsPage) },



      {
        path: "actions",

        element: <ActionsPage />,

        handle: {
          title: "Actions",
          icon: "action",
        },

      },
      { path: "actions/:actionId", element: <ActionsPage /> },



      {
        path: "audit",

        element: <AuditPage />,

        handle: {
          title: "Audit",
          icon: "audit",
        },

      },
      { path: "knowledge", element: <KnowledgePage /> },
      { path: "knowledge/search", element: deferred(KnowledgePage) },
      { path: "knowledge/library", element: deferred(KnowledgePage) },
      { path: "knowledge/evidence", element: deferred(KnowledgePage) },
      { path: "knowledge/evidence/:id", element: deferred(KnowledgePage) },
      { path: "knowledge/decisions", element: deferred(KnowledgePage) },
      { path: "knowledge/decisions/:decisionId", element: deferred(KnowledgePage) },
      { path: "knowledge/templates", element: deferred(KnowledgePage) },
      { path: "knowledge/sources", element: deferred(KnowledgePage) },
      { path: "knowledge/items/:id", element: <Navigate to="overview" replace/> },
      { path: "knowledge/items/:id/:tab", element: deferred(KnowledgePage) },
      { path: "tools", element: <ToolCatalogPage /> },
      { path: "tools/:name", element: <ToolDetailsPage /> },
      { path: "integrations", element: <IntegrationsPage /> },
      { path: "integrations/catalog", element: <IntegrationsPage /> },
      { path: "integrations/new", element: <IntegrationsPage /> },
      { path: "integrations/:connectionId", element: <IntegrationDetailPage /> },
      { path: "integrations/:connectionId/:tab", element: <IntegrationDetailPage /> },
      { path: "integrations/:connectionId/runs/:runId", element: <IntegrationDetailPage /> },
      { path: "tool-executions", element: <ToolExecutionsPage /> },
      { path: "native-tools", element: <NativeToolsPage /> },
      { path: "native-tools/:family", element: <NativeWorkspacePage /> },
      { path: "mcp-servers", element: <MCPServersPage /> },
      { path: "mcp-servers/new", element: <MCPServerFormPage /> },
      { path: "mcp-servers/:serverId", element: <MCPServerDetailsPage /> },
      { path: "discovery", element: <DiscoveryPage /> },
      { path: "tool-marketplace", element: <MarketplacePage /> },
      { path: "tool-governance", element: <GovernancePage /> },
      { path: "tool-analytics", element: <ToolAnalyticsPage /> },



      {
        path: "settings",

        element: <SettingsPage />,

        handle: {
          title: "Settings",
          icon: "settings",
        },

      },
      { path: "settings/:category", element: deferred(SettingsPage), handle: { title: "Settings" } },


      // Unknown routes
      {
        path: "*",

        element: <NotFoundPage />,

      },


    ],

  },

]);
