import type { DeliveryCommandCenterData, MyDayData } from "../types/delivery";
import { createDeliveryRepository } from "./delivery.repository";
import {isDeliveryMockMode} from "../config/deliveryDataMode";

export const mockDeliveryCommandCenterData: DeliveryCommandCenterData = {
  generatedAt: new Date().toISOString(),
  portfolioHealth: { label: "Portfolio Health", value: 84, unit: "%", status: "Healthy", detail: "Healthy", change: 3, changeLabel: "vs last period", definition: "Weighted project, release, risk, dependency and milestone health.", route: "/portfolio" },
  sprintPredictability: { label: "Sprint Predictability", value: 87, unit: "%", status: "On Track", detail: "On Track", change: 5, changeLabel: "vs last period", definition: "Completed originally committed scope divided by originally committed scope.", route: "/sprints" },
  openRisks: { label: "Open Risks", value: 12, status: "Critical", detail: "3 Critical", change: -2, changeLabel: "vs last period", definition: "Open risks, prioritised by probability, impact and age.", route: "/raid" },
  dependencies: { label: "Dependencies", value: 17, status: "Warning", detail: "2 Critical", change: 1, changeLabel: "vs last period", definition: "Open cross-team dependencies; critical-path items are highlighted.", route: "/dependencies" },
  contexts: [{id:"portfolio-all",name:"Enterprise Delivery",type:"Portfolio"},{id:"programme-digital",name:"Digital Experience",type:"Programme"},{id:"project-onboarding",name:"Customer Onboarding",type:"Project"}],
  deliveryTrend: [
    { period: "P1", portfolioHealth: 72, sprintPredictability: 75, commitmentAchievement: 70 },
    { period: "P2", portfolioHealth: 74, sprintPredictability: 78, commitmentAchievement: 73 },
    { period: "P3", portfolioHealth: 77, sprintPredictability: 76, commitmentAchievement: 75 },
    { period: "P4", portfolioHealth: 76, sprintPredictability: 81, commitmentAchievement: 78 },
    { period: "P5", portfolioHealth: 80, sprintPredictability: 83, commitmentAchievement: 79 },
    { period: "P6", portfolioHealth: 82, sprintPredictability: 82, commitmentAchievement: 81 },
    { period: "P7", portfolioHealth: 81, sprintPredictability: 85, commitmentAchievement: 84 },
    { period: "P8", portfolioHealth: 84, sprintPredictability: 87, commitmentAchievement: 86 },
    { period: "P9", portfolioHealth: 82, sprintPredictability: 85, commitmentAchievement: 83 },
    { period: "P10", portfolioHealth: 85, sprintPredictability: 86, commitmentAchievement: 84 },
    { period: "P11", portfolioHealth: 83, sprintPredictability: 88, commitmentAchievement: 86 },
    { period: "P12", portfolioHealth: 84, sprintPredictability: 87, commitmentAchievement: 88 },
  ],
  attentionItems: [
    { id: "att-1", item: "Payment API dependency", type: "Risk", impact: "High", status: "Open", owner: "Maya Chen", dueDate: "2026-08-16", description: "The payment provider contract is blocking end-to-end validation for Release 24.8.", score: 94, scoreBreakdown:["High delivery impact +35","Due within 2 days +25","Release critical path +24","Unresolved two periods +10"] },
    { id: "att-2", item: "UAT sign-off", type: "Action", impact: "High", status: "Overdue", owner: "Omar Ali", dueDate: "2026-08-12", description: "Business acceptance remains outstanding for the customer onboarding release." },
    { id: "att-3", item: "SIT environment", type: "Dependency", impact: "Medium", status: "Open", owner: "Sara Nabil", dueDate: "2026-08-18", description: "Intermittent environment failures are reducing the integration test pass rate." },
  ],
  recommendations: [
    { id: "rec-1", title: "Escalate the Payment API dependency", priority: "Critical", explanation: "The dependency has remained unresolved for two reporting periods and now threatens the release date.", affectedArea: "Release 24.8", evidenceCount: 6, confidence: 94, status:"New", evidence:[{id:"ev-1",tenantId:"demo",sourceType:"RAID record",sourceSystem:"MANUAL",sourceRecordId:"RAID-104",title:"Payment API dependency",summary:"Critical path dependency; target date 16 Aug."}] },
    { id: "rec-2", title: "Schedule the UAT sign-off meeting", priority: "High", explanation: "All entry criteria are complete, but stakeholder approval is overdue.", affectedArea: "Customer Onboarding", evidenceCount: 4, confidence: 89 },
    { id: "rec-3", title: "Investigate recurring SIT failures", priority: "Medium", explanation: "Failure patterns indicate a shared environment issue rather than isolated test defects.", affectedArea: "Sprint 18", evidenceCount: 11, confidence: 82 },
  ],
};

export const mockMyDayData: MyDayData = { generatedAt:new Date().toISOString(), focusScore:82, items:[
  {id:"day-1",title:"Review Payment API escalation",kind:"Attention",time:"09:30",priority:"Critical",context:"Release 24.8",summary:"Decision needed before today’s provider checkpoint."},
  {id:"day-2",title:"Customer onboarding stand-up",kind:"Meeting",time:"10:00",priority:"Medium",context:"Customer Onboarding",summary:"Three blockers and the UAT sign-off are on the agenda."},
  {id:"day-3",title:"Approve UAT exit",kind:"Approval",dueDate:"2026-08-14",priority:"High",context:"Customer Onboarding",summary:"Evidence pack is complete and awaiting delivery-owner approval."},
  {id:"day-4",title:"Confirm SIT environment owner",kind:"Action",dueDate:"2026-08-15",priority:"High",context:"Sprint 18",summary:"Assign an owner for recurring integration environment failures."}
], briefings:[{id:"brief-1",title:"Morning delivery briefing",summary:"Portfolio health is stable at 84%. Payment API and UAT sign-off are the two decisions most likely to change today’s outlook.",evidenceCount:10}] };

export async function getDeliveryCommandCenterData({ signal, contextId }: { signal?: AbortSignal; contextId?: string } = {}): Promise<DeliveryCommandCenterData> {
  const repository = createDeliveryRepository(isDeliveryMockMode(), mockDeliveryCommandCenterData);
  return repository.getCommandCenter(signal, contextId);
}
export async function getMyDayData({signal}:{signal?:AbortSignal}={}) { return createDeliveryRepository(isDeliveryMockMode(),mockDeliveryCommandCenterData,mockMyDayData).getMyDay(signal); }

export const isUsingMockDeliveryData = isDeliveryMockMode;
