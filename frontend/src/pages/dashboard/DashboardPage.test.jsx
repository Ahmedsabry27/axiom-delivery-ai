import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { MemoryRouter } from "react-router-dom";
import DashboardPage from "./DashboardPage";
import { mockDeliveryCommandCenterData } from "../../services/delivery-command-center.service";

vi.mock("../../hooks/useAuth",()=>({default:()=>({user:{givenName:"Ahmed"}})}));
vi.mock("recharts",()=>({ResponsiveContainer:({children})=><div>{children}</div>,LineChart:({children})=><div>{children}</div>,Line:()=>null,CartesianGrid:()=>null,Legend:()=>null,Tooltip:()=>null,XAxis:()=>null,YAxis:()=>null}));
const repository=vi.fn();
vi.mock("../../services/delivery-command-center.service",async(importOriginal)=>{const original=await importOriginal();return {...original,getDeliveryCommandCenterData:(args)=>repository(args),isUsingMockDeliveryData:()=>true};});
const renderPage=()=>render(<MemoryRouter><QueryClientProvider client={new QueryClient({defaultOptions:{queries:{retry:false}}})}><DashboardPage/></QueryClientProvider></MemoryRouter>);

describe("Command Center",()=>{
  beforeEach(()=>repository.mockReset());
  it("renders KPI cards and opens attention details",async()=>{repository.mockResolvedValue(mockDeliveryCommandCenterData);renderPage();expect(screen.getByLabelText(/loading command center/i)).toBeInTheDocument();expect(await screen.findByText("Portfolio Health")).toBeInTheDocument();expect(screen.getByText("Sprint Predictability")).toBeInTheDocument();fireEvent.click(screen.getAllByRole("button",{name:"View"})[0]);expect(screen.getByRole("dialog",{name:"Payment API dependency"})).toBeInTheDocument();});
  it("reviews a recommendation without executing it",async()=>{repository.mockResolvedValue(mockDeliveryCommandCenterData);renderPage();await screen.findByText("AI Recommendations");fireEvent.click(screen.getAllByRole("button",{name:"Take Action"})[0]);expect(screen.getByText(/No external system will be updated/i)).toBeInTheDocument();fireEvent.click(screen.getByRole("button",{name:"Create proposal"}));expect(screen.getByRole("status")).toHaveTextContent("No external action was executed");});
  it("shows an error and retries",async()=>{repository.mockRejectedValueOnce(new Error("offline")).mockResolvedValueOnce(mockDeliveryCommandCenterData);renderPage();expect(await screen.findByRole("alert")).toBeInTheDocument();fireEvent.click(screen.getByRole("button",{name:/retry/i}));await waitFor(()=>expect(screen.getByText("Portfolio Health")).toBeInTheDocument());});
  it("renders the empty state",async()=>{repository.mockResolvedValue(null);renderPage();expect(await screen.findByText("No delivery data yet")).toBeInTheDocument();});
});
