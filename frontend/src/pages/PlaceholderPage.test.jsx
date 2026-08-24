import { MemoryRouter } from "react-router-dom";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import PlaceholderPage from "./PlaceholderPage";
describe("feature placeholder",()=>{it("describes planned capabilities without fake functionality",()=>{render(<MemoryRouter><PlaceholderPage title="Sprints"/></MemoryRouter>);expect(screen.getByText("Coming soon")).toBeInTheDocument();expect(screen.getByText("Velocity trends")).toBeInTheDocument();expect(screen.getByRole("link",{name:/Command Center/i})).toHaveAttribute("href","/command-center");});});
