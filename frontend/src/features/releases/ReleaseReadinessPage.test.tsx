import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import ReleaseDetailsPage from "./ReleaseDetailsPage";

function renderReadiness(path = "/releases/rel-001/readiness") {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/releases/:releaseId/:tab" element={<ReleaseDetailsPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Release Readiness", () => {
  it("resolves release context from the URL and renders the calculated demo state", () => {
    renderReadiness();
    expect(screen.getByRole("link", { name: "AX Platform 1.0" })).toHaveAttribute("href", "/releases/rel-001");
    expect(screen.getAllByText("87%").length).toBeGreaterThan(0);
    expect(screen.getAllByText("CONDITIONAL GO").length).toBeGreaterThan(0);
    expect(screen.getByText("20 / 22 evidence items verified")).toBeInTheDocument();
    expect(screen.getAllByText("PENDING").length).toBeGreaterThan(0);
  });

  it("opens readiness criterion details", async () => {
    const user = userEvent.setup();
    renderReadiness();
    await user.click(screen.getByRole("button", { name: /Security Approval/i }));
    expect(screen.getByRole("dialog", { name: /Security Approval/i })).toBeInTheDocument();
    expect(screen.getByText("Security Review AX-184")).toBeInTheDocument();
  });

  it("validates, confirms, and records a conditional human decision", () => {
    renderReadiness();
    fireEvent.click(screen.getAllByRole("button", { name: "Record Decision" })[0]);
    const dialog = screen.getByRole("dialog", { name: "Record release decision" });
    const conditions = within(dialog).getByRole("textbox", { name: "Conditions" });
    fireEvent.change(conditions, { target: { value: "" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Continue" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("Add at least one release condition");
    fireEvent.change(conditions, { target: { value: "Security approval before deployment" } });
    fireEvent.click(within(dialog).getByRole("button", { name: "Continue" }));
    expect(within(dialog).getByText("Confirm release decision")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm decision" }));
    expect(screen.getByRole("status")).toHaveTextContent("Decision recorded successfully: CONDITIONAL GO");
    expect(screen.getAllByText("CONDITIONAL GO").length).toBeGreaterThan(2);
  });

  it("requires rationale for a No-Go decision", () => {
    renderReadiness();
    fireEvent.click(screen.getAllByRole("button", { name: "Record Decision" })[0]);
    const dialog = screen.getByRole("dialog", { name: "Record release decision" });
    fireEvent.click(within(dialog).getByRole("radio", { name: "NO-GO" }));
    fireEvent.click(within(dialog).getByRole("button", { name: "Continue" }));
    expect(within(dialog).getByRole("alert")).toHaveTextContent("rationale is required");
  });

  it("shows a release-not-found state instead of falling back to another tenant record", () => {
    renderReadiness("/releases/unknown-release/readiness");
    expect(screen.getByRole("heading", { name: "Release not found" })).toBeInTheDocument();
    expect(screen.queryByText("AX Platform 1.0")).not.toBeInTheDocument();
  });

  it("does not expose decision controls to an unauthorized release viewer", () => {
    renderReadiness("/releases/rel-002/readiness");
    expect(screen.queryByRole("button", { name: "Record Decision" })).not.toBeInTheDocument();
    expect(screen.getByText("You do not have permission to record this release decision.")).toBeInTheDocument();
  });

  it("cleans up dialogs and supports repeated independent mounts", () => {
    for (let iteration = 0; iteration < 2; iteration += 1) {
      const view = renderReadiness();
      fireEvent.click(screen.getAllByRole("button", { name: "Record Decision" })[0]);
      expect(screen.getByRole("dialog", { name: "Record release decision" })).toBeInTheDocument();
      view.unmount();
      expect(screen.queryByRole("dialog", { name: "Record release decision" })).not.toBeInTheDocument();
    }
  });
});
