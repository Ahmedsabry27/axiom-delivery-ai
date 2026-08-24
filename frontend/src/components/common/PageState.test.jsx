import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { AccessDenied, PageEmpty, PageError, PageLoading, TableSkeleton } from "./PageState";
describe("shared page states",()=>{
  it("renders accessible loading and empty states",()=>{const {rerender}=render(<PageLoading/>);expect(screen.getByLabelText("Loading page")).toHaveAttribute("aria-busy","true");rerender(<TableSkeleton/>);expect(screen.getByLabelText("Loading table")).toBeInTheDocument();rerender(<PageEmpty title="No records" description="Nothing matched."/>);expect(screen.getByRole("heading",{name:"No records"})).toBeInTheDocument();});
  it("supports error retry and access messages",()=>{const retry=vi.fn();const {rerender}=render(<PageError correlationId="AX-1" onRetry={retry}/>);fireEvent.click(screen.getByRole("button",{name:/retry/i}));expect(retry).toHaveBeenCalledOnce();expect(screen.getByText("Reference: AX-1")).toBeInTheDocument();rerender(<AccessDenied forbidden/>);expect(screen.getByText("Access restricted")).toBeInTheDocument();});
});
