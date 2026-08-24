import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import Sidebar from "./Sidebar";

describe("Sidebar",()=>{
  it("renders grouped routes with the active Command Center state",()=>{
    render(<MemoryRouter initialEntries={["/command-center"]}><Sidebar collapsed={false} onCollapsedChange={vi.fn()}/></MemoryRouter>);
    expect(screen.getByText("My Work")).toBeInTheDocument();
    expect(screen.getByRole("link",{name:/Command Center/i})).toHaveAttribute("aria-current","page");
    expect(screen.getByRole("link",{name:/AI Copilot/i})).toHaveAttribute("href","/copilot");
    expect(screen.getByText("Axiom")).toBeInTheDocument();
    expect(screen.getByRole("img",{name:"Axiom monogram"})).toHaveTextContent("A");
  });
  it("keeps the Axiom monogram readable when collapsed",()=>{
    render(<MemoryRouter><Sidebar collapsed onCollapsedChange={vi.fn()}/></MemoryRouter>);
    expect(screen.getByRole("img",{name:"Axiom monogram"})).toHaveTextContent("A");
    expect(screen.queryByText("Delivery AI")).not.toBeInTheDocument();
  });
});
