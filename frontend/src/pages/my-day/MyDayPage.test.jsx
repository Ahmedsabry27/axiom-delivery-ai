import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import MyDayPage from "./MyDayPage";

vi.mock("../../hooks/useAuth", () => ({ default: () => ({ user: { givenName: "Ahmed" } }) }));
vi.mock("../../services/delivery-command-center.service", () => ({
  getMyDayData: vi.fn().mockResolvedValue({ focusScore: 0 }),
}));

describe("My Day partial responses", () => {
  it("renders safely when item and briefing collections are omitted", async () => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <MemoryRouter>
        <QueryClientProvider client={client}>
          <MyDayPage />
        </QueryClientProvider>
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Today’s focus" })).toBeInTheDocument();
    expect(screen.getByText("Briefings")).toBeInTheDocument();
    expect(screen.getByText("0")).toBeInTheDocument();
  });
});
