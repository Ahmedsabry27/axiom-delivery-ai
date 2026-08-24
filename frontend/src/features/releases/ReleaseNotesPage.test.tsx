import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import ReleaseDetailsPage from "./ReleaseDetailsPage";
import ReleaseNotesPage from "./ReleaseNotesPage";
import { mockReleaseNotesMap } from "./data/mockReleaseNotes";
import { mockReleases } from "./data/mockReleases";

function renderRoute(path = "/releases/rel-001/release-notes") {
  return render(<MemoryRouter initialEntries={[path]}><Routes><Route path="/releases/:releaseId/:tab" element={<ReleaseDetailsPage />} /></Routes></MemoryRouter>);
}

describe("Release Notes", () => {
  it("resolves the selected release and marks the child tab active", () => {
    renderRoute();
    expect(screen.getByRole("link", { name: "Release Notes" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByText("AX Platform 1.0 · v1.0.0 · PROD")).toBeInTheDocument();
    expect(screen.getByText("34 / 34")).toBeInTheDocument();
  });

  it("searches by Jira key and filters categories", () => {
    renderRoute();
    const search = screen.getByRole("textbox", { name: "Search release notes" });
    fireEvent.change(search, { target: { value: "AX-603" } });
    expect(screen.getByText("AI Release Recommendation")).toBeInTheDocument();
    expect(screen.queryByText("Release Readiness Criteria")).not.toBeInTheDocument();
    fireEvent.change(search, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: "Known Issues" }));
    expect(screen.getByText("Monitoring validation may take up to 30 seconds after deployment")).toBeInTheDocument();
    expect(screen.queryByText("AI Release Recommendation")).not.toBeInTheDocument();
  });

  it("opens item details with Jira and readiness links", () => {
    renderRoute();
    fireEvent.click(screen.getByRole("button", { name: /AI Release Recommendation/i }));
    const dialog = screen.getByRole("dialog", { name: "AI Release Recommendation" });
    expect(within(dialog).getByRole("link", { name: "Open in Jira" })).toHaveAttribute("href", "https://jira.example.com/browse/AX-603");
    expect(within(dialog).getAllByRole("link", { name: "View Readiness" }).every((link) => link.getAttribute("href") === "/releases/rel-001/readiness")).toBe(true);
  });

  it("does not create a broken Jira link when a URL is unavailable", () => {
    const item = mockReleaseNotesMap["rel-001"].items[0];
    const originalUrl = item.jira.url;
    item.jira.url = undefined;
    render(<MemoryRouter><ReleaseNotesPage release={{ ...mockReleases[0], releaseNotes: mockReleaseNotesMap["rel-001"] }} /></MemoryRouter>);
    expect(screen.getAllByText("AX-601").length).toBeGreaterThan(0);
    expect(screen.queryByRole("link", { name: "Open AX-601 in Jira" })).not.toBeInTheDocument();
    item.jira.url = originalUrl;
  });

  it("provides release-specific notes for the remaining demo releases", () => {
    const { unmount } = renderRoute("/releases/rel-002/release-notes");
    expect(screen.getByText("AX Platform 1.1 · v1.1.0 · UAT")).toBeInTheDocument();
    expect(screen.getByText("Reusable readiness templates")).toBeInTheDocument();
    expect(screen.getByText("7 / 7")).toBeInTheDocument();
    unmount();

    renderRoute("/releases/rel-003/release-notes");
    expect(screen.getByText("Duplicate audit events during retry")).toBeInTheDocument();
    expect(screen.getByText("5 / 5")).toBeInTheDocument();
  });
});
