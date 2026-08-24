import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import Sidebar from "../../components/layout/Sidebar";
import ReleaseDetailsPage from "./ReleaseDetailsPage";
import ReleasesPage from "./ReleasesPage";

describe("Releases module", () => {
  it("renders the portfolio view and release data", () => {
    render(
      <MemoryRouter initialEntries={["/releases"]}>
        <Routes>
          <Route path="/releases" element={<ReleasesPage />} />
          <Route path="/releases/:releaseId" element={<ReleasesPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByRole("heading", { name: "Releases" })).toBeInTheDocument();
    expect(screen.getByText("AX Platform 1.0")).toBeInTheDocument();
    expect(screen.getByText("v1.0.0")).toBeInTheDocument();
    expect(screen.getByText("20 / 22")).toBeInTheDocument();
    expect(screen.getAllByText("Ready for decision").length).toBeGreaterThan(0);
  });

  it("keeps release readiness nested under a selected release instead of as a top-level sidebar item", () => {
    render(
      <MemoryRouter initialEntries={["/releases/rel-001/readiness"]}>
        <Routes>
          <Route path="/releases/:releaseId/:tab" element={<ReleaseDetailsPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText("Release readiness")).toBeInTheDocument();
    render(
      <MemoryRouter initialEntries={["/releases/rel-001/readiness"]}>
        <Sidebar
          collapsed={false}
          onCollapsedChange={() => undefined}
          onNavigate={() => undefined}
        />
      </MemoryRouter>
    );

    expect(screen.queryByRole("link", { name: "Release Readiness" })).not.toBeInTheDocument();
  });

  it("shows release-specific model usage on the hardening route", () => {
    render(
      <MemoryRouter initialEntries={["/releases/rel-001/hardening"]}>
        <Routes><Route path="/releases/:releaseId/:tab" element={<ReleaseDetailsPage />} /></Routes>
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { name: "Model & token monitoring" })).toBeInTheDocument();
    expect(screen.getByText("2.84M tokens", { exact: false })).toBeInTheDocument();
  });
});
