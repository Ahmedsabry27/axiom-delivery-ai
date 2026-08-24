import {render,screen} from "@testing-library/react";
import {MemoryRouter} from "react-router-dom";
import {describe,expect,it} from "vitest";
import {Button,PageHeader,StatePanel,StatusBadge,Tabs} from ".";

describe("Axiom design system",()=>{
  it("renders semantic status text and unknown safely",()=>{render(<><StatusBadge value="Healthy"/><StatusBadge value={undefined}/></>);expect(screen.getByText("Healthy")).toBeInTheDocument();expect(screen.getByText("Unknown")).toBeInTheDocument()});
  it("exposes button disabled state",()=>{render(<Button disabled>Save changes</Button>);expect(screen.getByRole("button")).toBeDisabled()});
  it("provides landmarks and current tab",()=>{render(<MemoryRouter><PageHeader title="Models" breadcrumbs={[{label:"Administration",to:"/settings"}]}/><Tabs items={[{label:"Overview",to:"/models",active:true}]}/></MemoryRouter>);expect(screen.getByRole("heading",{name:"Models"})).toBeInTheDocument();expect(screen.getByRole("link",{name:"Overview"})).toHaveAttribute("aria-current","page")});
  it("announces errors",()=>{render(<StatePanel kind="error" title="Unavailable" description="Try again"/>);expect(screen.getByRole("alert")).toHaveTextContent("Unavailable")});
});
