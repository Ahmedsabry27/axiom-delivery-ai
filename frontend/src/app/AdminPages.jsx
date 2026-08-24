import { lazy, Suspense } from "react";

const NativeTools = lazy(() => import("../pages/native/NativeToolsPage"));
const NativeWorkspace = lazy(() => import("../pages/native/NativeWorkspacePage"));
const MCPServers = lazy(() => import("../pages/mcp/MCPServersPage"));
const MCPServerForm = lazy(() => import("../pages/mcp/MCPServerFormPage"));
const MCPServerDetails = lazy(() => import("../pages/mcp/MCPServerDetailsPage"));
const Discovery = lazy(() => import("../pages/discovery/DiscoveryPage"));
const Marketplace = lazy(() => import("../pages/discovery/MarketplacePage"));
const Governance = lazy(() => import("../pages/discovery/GovernancePage"));
const ToolAnalytics = lazy(() => import("../pages/discovery/ToolAnalyticsPage"));

function AdministrationBoundary({ children }) {
  return (
    <Suspense
      fallback={
        <div className="state-message" role="status">
          Loading administration workspace…
        </div>
      }
    >
      {children}
    </Suspense>
  );
}

export function NativeToolsPage() {
  return <AdministrationBoundary><NativeTools /></AdministrationBoundary>;
}

export function NativeWorkspacePage() {
  return <AdministrationBoundary><NativeWorkspace /></AdministrationBoundary>;
}

export function MCPServersPage() {
  return <AdministrationBoundary><MCPServers /></AdministrationBoundary>;
}

export function MCPServerFormPage() {
  return <AdministrationBoundary><MCPServerForm /></AdministrationBoundary>;
}

export function MCPServerDetailsPage() {
  return <AdministrationBoundary><MCPServerDetails /></AdministrationBoundary>;
}

export function DiscoveryPage() {
  return <AdministrationBoundary><Discovery /></AdministrationBoundary>;
}

export function MarketplacePage() {
  return <AdministrationBoundary><Marketplace /></AdministrationBoundary>;
}

export function GovernancePage() {
  return <AdministrationBoundary><Governance /></AdministrationBoundary>;
}

export function ToolAnalyticsPage() {
  return <AdministrationBoundary><ToolAnalytics /></AdministrationBoundary>;
}
