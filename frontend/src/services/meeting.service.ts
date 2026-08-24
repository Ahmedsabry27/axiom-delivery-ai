import api from "./api";
import {mockFindingsByMeeting,mockMeetingById,mockMeetings,mockTranscriptByMeeting} from "../pages/meetings/data/mockMeetings";
import {isDeliveryMockMode} from "../config/deliveryDataMode";

export type MeetingFinding={id:string;meetingId:string;type:string;title:string;description:string;reviewStatus:string;confidence:number;suggestedOwnerId?:string|null;dueDate?:string|null;priority?:string|null;impact?:string|null;proposalId?:string|null;version:number;evidence:Array<{segmentId:string;startOffset:number;endOffset:number;excerpt:string}>};
export type Meeting={id:string;title:string;meetingType:string;status:string;description:string;organizerId?:string;scheduledStart?:string;timezone:string;projectId?:string;version:number;metadata:Record<string,unknown>;findingCounts:Record<string,number>;needsReview:number;createdAt:string;updatedAt:string};
export type Transcript={transcript:{id:string;sourceType:string;characterCount:number}|null;segments:Array<{id:string;sequence:number;speaker:string;startTime?:string;text:string}>};
type Page<T>={items:T[];total:number;page:number};

export const listMeetings=(params?:Record<string,string>)=>isDeliveryMockMode()?Promise.resolve((()=>{const search=params?.search?.toLowerCase(),status=params?.status;const items=mockMeetings.filter(item=>(!status||item.status===status)&&(!search||`${item.title} ${item.description}`.toLowerCase().includes(search)));return {items,total:items.length,page:1};})()):api.get<Page<Meeting>>("/api/meetings",{params}).then(r=>r.data);
export const createMeeting=(payload:unknown)=>api.post<Meeting>("/api/meetings",payload).then(r=>r.data);
export const getMeeting=(id:string)=>isDeliveryMockMode()?Promise.resolve(mockMeetingById(id)):api.get<Meeting>(`/api/meetings/${id}`).then(r=>r.data);
export const addMeetingTranscript=(id:string,payload:unknown)=>api.post(`/api/meetings/${id}/transcript`,payload).then(r=>r.data);
export const analyseMeeting=(id:string)=>api.post<Meeting>(`/api/meetings/${id}/analyse`).then(r=>r.data);
export const getMeetingTranscript=(id:string)=>isDeliveryMockMode()?Promise.resolve(mockTranscriptByMeeting(id)):api.get<Transcript>(`/api/meetings/${id}/transcript`).then(r=>r.data);
export const getMeetingFindings=(id:string)=>isDeliveryMockMode()?Promise.resolve({items:mockFindingsByMeeting(id)}):api.get<{items:MeetingFinding[]}>(`/api/meetings/${id}/findings`).then(r=>r.data);
export const reviewMeetingFinding=(meetingId:string,findingId:string,decision:string,payload:unknown)=>api.post<MeetingFinding>(`/api/meetings/${meetingId}/findings/${findingId}/${({accepted:"accept",rejected:"reject",merged:"merge"} as Record<string,string>)[decision.toLowerCase()] ?? decision.toLowerCase()}`,payload).then(r=>r.data);
export const proposeMeetingFinding=(meetingId:string,findingId:string)=>api.post<MeetingFinding>(`/api/meetings/${meetingId}/findings/${findingId}/proposal`).then(r=>r.data);
export const generateMeetingArtifact=(id:string,type:"minutes"|"executive-summary")=>api.post(`/api/meetings/${id}/${type}`).then(r=>r.data);
