import { useEffect, useReducer, useRef, useState } from "react";

import { updateConversationTitle } from "../services/conversationService";
import { startExecution } from "../services/chat.service";
import { approveRuntime, cancelRuntime, continueRuntime, continueRuntimeMessage, denyRuntime, getConversationRuntime, getRuntime, subscribeRuntime } from "../services/runtime.service";
import { initialRuntimeState, runtimeReducer } from "../store/runtime.reducer";
import createConversationTitle from "../utils/createConversationTitle";

const timestamp = () => new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
const terminalStatuses = new Set(["COMPLETED","FAILED","CANCELLED","TIMED_OUT"]);

export default function useChat(conversation) {
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [responseId, setResponseId] = useState(null);
  const [activeExecution,setActiveExecution]=useState(null);
  const [runtime,dispatchRuntime]=useReducer(runtimeReducer,initialRuntimeState);
  const runtimeRef = useRef(null);
  const executionRef = useRef(null);
  const lastRequestRef=useRef(null);
  const consumedContinuationsRef = useRef(new Set());
  // Runtime events are an external subscription; synchronizing their authoritative
  // snapshot into view state is the purpose of this effect.
  useEffect(()=>{
    if(!runtime.executionId)return;
    // eslint-disable-next-line react-hooks/set-state-in-effect -- runtime is an external SSE snapshot
    setActiveExecution(current=>current?.execution_id===runtime.executionId?{...current,status:runtime.status,continuation:runtime.status==="WAITING_FOR_INPUT"?runtime.requiredInput:runtime.status==="WAITING_FOR_APPROVAL"?runtime.approval:null}:current);
    setMessages(current=>current.map(message=>message.metadata?.execution_id===runtime.executionId?{...message,text:runtime.status==="COMPLETED"?(runtime.finalResponse||message.text):message.text,metadata:{...message.metadata,execution_id:runtime.executionId,workflow_id:runtime.workflowId,status:runtime.status,state_version:runtime.stateVersion,last_sequence:runtime.lastSequence,steps:runtime.steps,tools:runtime.tools,actions:runtime.actions,agent:runtime.selectedAgent?.name,agent_id:runtime.selectedAgent?.id,provider:runtime.selectedAgent?.provider||runtime.metrics.provider,model:runtime.selectedAgent?.model||runtime.metrics.model,duration_ms:runtime.durationMs,error:runtime.error?.message}}:message));
    if(terminalStatuses.has(runtime.status))setLoading(false);
  },[runtime]);

  function connectRuntime(assistantId, execution) {
    runtimeRef.current?.();
    executionRef.current = execution.execution_id;
    runtimeRef.current = subscribeRuntime(
      execution.execution_id,
      (event) => applyEvent(assistantId, execution, event),
      () => void reconcileRuntime(execution.execution_id, assistantId),
    );
  }

  function applyEvent(assistantId,execution,event){
    if(executionRef.current!==event.execution_id)return;
    if (
      (event.type === "required_input" || event.type === "approval_required") &&
      consumedContinuationsRef.current.has(event.continuation_id)
    ) {
      return;
    }
    dispatchRuntime({type:"event",event});
    if(event.aggregate_status?.startsWith("WAITING_"))setLoading(false);
    if(event.final&&terminalStatuses.has(event.aggregate_status)){void reconcileRuntime(execution.execution_id,assistantId);runtimeRef.current?.();runtimeRef.current=null;executionRef.current=null;}
  }

  async function reconcileRuntime(executionId,assistantId){
    try{const authoritative=await getRuntime(executionId);if(executionRef.current&&executionRef.current!==executionId)return;dispatchRuntime({type:"hydrate",runtime:authoritative});setActiveExecution(current=>current?{...current,...authoritative,assistant_id:assistantId}:current);}
    catch(error){console.error("Unable to reconcile authoritative runtime state",error);}
  }

  function loadMessages(data) {
    const normalized=(data || []).map(message=>({...message,text:message.text??message.content,timestamp:message.timestamp??(message.created_at?new Date(message.created_at).toLocaleTimeString([], {hour:"2-digit",minute:"2-digit"}):undefined)}));
    setMessages(normalized);
    setResponseId([...(data || [])].reverse().find((message) => message.role === "assistant")?.response_id ?? null);
    return normalized;
  }

  async function handleStream(userMessage, options={}) {
    if (!userMessage?.trim() || loading) return;
    let assistantId = null;
    lastRequestRef.current={message:userMessage,options};
    try {
      runtimeRef.current?.();
      consumedContinuationsRef.current.clear();
      const conversationId = await conversation.ensureConversation();
      const active = conversation.conversations.find((item) => item.id === conversationId);
      if (active?.title === "New Conversation") {
        try {
          await updateConversationTitle(
            conversationId,
            createConversationTitle(userMessage),
          );
          await conversation.refreshConversations();
        } catch (error) {
          // Renaming is cosmetic. A transient title failure must never prevent
          // the user's prompt from reaching the governed runtime.
          console.warn("Unable to update conversation title", error);
        }
      }

      assistantId = crypto.randomUUID();
      setMessages((current) => [...current,
        { id: crypto.randomUUID(), role: "user", text: userMessage, timestamp: timestamp() },
        { id: assistantId, role: "assistant", text: "", timestamp: timestamp(), metadata: { status: "RUNNING", steps: [] } },
      ]);
      setLoading(true);
      const execution = await startExecution({ message: userMessage, conversation_id: conversationId, agent_id: options.agentId||null, provider:options.provider||null, model:options.model||null, workspace_id:options.workspace||null, metadata:options.metadata||null });
      setResponseId(execution.execution_id);
      setMessages(current=>current.map(message=>message.id===assistantId?{...message,metadata:{...message.metadata,execution_id:execution.execution_id,workflow_id:execution.workflow_id}}:message));
      setActiveExecution({...execution,agent_id:options.agentId||null,assistant_id:assistantId});
      dispatchRuntime({type:"started",execution});
      connectRuntime(assistantId, execution);
    } catch (error) {
      console.error("Unable to start runtime execution", error);
      if (assistantId) {
        failExecution(
          assistantId,
          error instanceof Error ? error.message : "Unable to start runtime execution",
        );
      }
      setLoading(false);
    }
  }

  async function resumeAgentExecution(values, mode="structured"){
    if(!activeExecution?.continuation)return;
    const continuationId = activeExecution.continuation.continuation_id;
    consumedContinuationsRef.current.add(continuationId);
    setLoading(true);
    try{
      const response=mode==="natural_language"
        ? await continueRuntimeMessage(activeExecution.execution_id,continuationId,String(values.natural_language||""))
        : await continueRuntime(activeExecution.execution_id,continuationId,values);
      const handedOff=response?.outcome==="new_request";
      const next=handedOff?response.execution:response;
      const resumed={...next,...(handedOff?{}:{agent_id:activeExecution.agent_id}),assistant_id:activeExecution.assistant_id,continuation:null};
      setActiveExecution(resumed);
      if(handedOff){
        runtimeRef.current?.();
        runtimeRef.current=null;
        executionRef.current=next.execution_id;
        setMessages(current=>current.map(item=>item.id===activeExecution.assistant_id?{
          ...item,
          metadata:{...item.metadata,execution_id:next.execution_id,workflow_id:next.workflow_id,status:next.status},
        }:item));
      }
      await reconcileRuntime(next.execution_id,activeExecution.assistant_id);
      connectRuntime(activeExecution.assistant_id, resumed);
    }catch(error){
      if(error?.response?.status===409){
        const authoritative=await getRuntime(activeExecution.execution_id);
        const reconciled={...activeExecution,...authoritative,continuation:null};
        setActiveExecution(reconciled);
        await reconcileRuntime(activeExecution.execution_id,activeExecution.assistant_id);
        if(authoritative.status==="RUNNING"){
          setLoading(true);
          connectRuntime(activeExecution.assistant_id,reconciled);
        }else{
          setLoading(false);
        }
        return;
      }
      consumedContinuationsRef.current.delete(continuationId);
      setLoading(false);
      throw error;
    }
  }

  async function decideApproval(decision){
    const continuation=activeExecution?.continuation;if(!continuation)return;
    consumedContinuationsRef.current.add(continuation.continuation_id);
    const fn=decision==="approve"?approveRuntime:denyRuntime;
    const next=await fn(activeExecution.execution_id,continuation.continuation_id);
    const resumed={...activeExecution,...next,continuation:null};
    setActiveExecution(resumed);
    if(decision==="approve"){
      setLoading(true);
      await reconcileRuntime(next.execution_id,activeExecution.assistant_id);
      connectRuntime(activeExecution.assistant_id, resumed);
    }else{
      await reconcileRuntime(next.execution_id,activeExecution.assistant_id);
      setLoading(false);
    }
  }

  function failExecution(assistantId, description) {
    if(executionRef.current){void reconcileRuntime(executionRef.current,assistantId);return;}
    setMessages((current) => current.map((message) => message.id === assistantId ? {
      ...message,
      text: "Axiom Runtime failed.",
      metadata: { ...message.metadata, status: "FAILED", steps: [...(message.metadata?.steps || []), { id: "runtime-error", name: "Runtime Execution", description, status: "failed", timestamp: new Date().toISOString() }] },
    } : message));
    setLoading(false);
  }

  function stopGeneration() {
    const executionId = executionRef.current;
    if (executionId) {
      void cancelRuntime(executionId).then(()=>reconcileRuntime(executionId,activeExecution?.assistant_id)).catch((error) => console.error("Runtime cancellation failed", error));
    }
  }

  function clearChat() {runtimeRef.current?.();runtimeRef.current=null;executionRef.current=null;setMessages([]); setResponseId(null); setLoading(false);dispatchRuntime({type:"reset"});setActiveExecution(null);consumedContinuationsRef.current.clear(); }
  function retryExecution(){const request=lastRequestRef.current;if(request&&!loading)return handleStream(request.message,request.options);}
  async function restoreRuntime(conversationId,assistantId){
    runtimeRef.current?.();runtimeRef.current=null;executionRef.current=null;dispatchRuntime({type:"reset"});const execution=await getConversationRuntime(conversationId);if(!execution)return;
    const restoredAssistantId=assistantId||crypto.randomUUID();
    if(!assistantId)setMessages(current=>[...current,{id:restoredAssistantId,role:"assistant",text:"",timestamp:timestamp(),metadata:{status:execution.status?.toUpperCase()||"RUNNING",execution_id:execution.execution_id,workflow_id:execution.workflow_id,steps:[]}}]);
    setMessages(current=>current.map(message=>message.id===restoredAssistantId?{...message,metadata:{...message.metadata,execution_id:execution.execution_id,workflow_id:execution.workflow_id}}:message));
    executionRef.current=execution.execution_id;setActiveExecution({...execution,assistant_id:restoredAssistantId});dispatchRuntime({type:"started",execution});dispatchRuntime({type:"hydrate",runtime:execution});if(!terminalStatuses.has(execution.status))runtimeRef.current=subscribeRuntime(execution.execution_id,event=>applyEvent(restoredAssistantId,execution,event),()=>void reconcileRuntime(execution.execution_id,restoredAssistantId));
  }
  useEffect(() => () => runtimeRef.current?.(), []);
  return { messages, loading, responseId, activeExecution, runtime, loadMessages, clearChat, restoreRuntime, handleStream, handleSend: handleStream, retryExecution, resumeAgentExecution, decideApproval, stopGeneration };
}
