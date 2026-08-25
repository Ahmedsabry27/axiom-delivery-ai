import { useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { getAuthorizedAgents } from "../services/agentService";

import ChatWindow from "../components/chat/ChatWindow";
import ChatInput from "../components/chat/ChatInput";
import CopilotInspector from "../components/copilot/CopilotInspector";
import RequiredInformationCard from "../components/chat/RequiredInformationCard";
import ConversationSidebar from "../components/chat/ConversationSidebar";
import ChatHeader from "../components/chat/ChatHeader";
import DeliveryContextBar from "../components/copilot/DeliveryContextBar";
import { deliveryContexts } from "../components/copilot/deliveryContexts";
import ProposedActionDrawer from "../components/copilot/ProposedActionDrawer";
import { runtimeFailureMessage } from "../utils/runtimePresentation";

import useConversation from "../hooks/useConversation";
import useChat from "../hooks/useChat";

export default function ChatPage() {
  const conversation = useConversation();
  const chat = useChat(conversation);

  const { data: agents = [] } = useQuery({
    queryKey: ["authorized-agents"],
    queryFn: getAuthorizedAgents,
  });

  const [agentId, setAgentId] = useState("");
  const [provider, setProvider] = useState("automatic");
  const [model, setModel] = useState("automatic");
  const [workspace, setWorkspace] = useState("Delivery Management");
  const [deliveryContext,setDeliveryContext]=useState(()=>globalThis.localStorage?.getItem("axiom.copilot.context")||"");
  const [proposal,setProposal]=useState(null);

  const conversationRef = useRef(conversation);
  const chatRef = useRef(chat);

  useEffect(() => {
    conversationRef.current = conversation;
    chatRef.current = chat;
  });

  useEffect(()=>{const open=event=>setProposal(event.detail);globalThis.addEventListener("axiom:propose-action",open);return()=>globalThis.removeEventListener("axiom:propose-action",open)},[]);

  // ---------------------------------------
  // Load selected conversation
  // ---------------------------------------

  useEffect(() => {
    let cancelled = false;
    async function loadConversation() {
      if (!conversationRef.current.selectedConversation) {
        return;
      }

      const messages =
        await conversationRef.current.openConversation(
          conversationRef.current.selectedConversation.id
        );
      if (cancelled) return;

      const normalized =
        chatRef.current.loadMessages(messages);

      const assistant = [...normalized]
        .reverse()
        .find((item) => item.role === "assistant");

      await chatRef.current.restoreRuntime(
        conversationRef.current.selectedConversation.id,
        assistant?.id
      );
    }

    loadConversation();
    return () => { cancelled = true; };
  }, [conversation.selectedConversation]);

  useEffect(() => {
    if (
      !conversation.selectedConversation &&
      !conversation.conversationId
    ) {
      chatRef.current.clearChat();
    }
  }, [
    conversation.selectedConversation,
    conversation.conversationId,
  ]);

  // ---------------------------------------
  // Send message
  // ---------------------------------------

  async function handleSend(message) {
    if (
      chat.activeExecution?.continuation?.kind === "input"
    ) {
      await chat.resumeAgentExecution(
        {
          natural_language: message,
        },
        "natural_language"
      );

      return;
    }

    await chat.handleStream(message, {
      agentId,

      provider:
        agentId || provider === "automatic"
          ? null
          : provider,

      model:
        agentId || model === "automatic"
          ? null
          : model,

      workspace,
      metadata:{delivery_context:deliveryContexts.find(item=>item.id===deliveryContext)||null,response_mode:"structured_delivery"},
    });
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden">
      {/* -------------------------------- */}
      {/* Conversation Sidebar */}
      {/* -------------------------------- */}

      <ConversationSidebar conversation={conversation} />

      {/* -------------------------------- */}
      {/* Chat Workspace */}
      {/* -------------------------------- */}

      <section
        className="
          relative
          flex
          min-h-0
          min-w-0
          flex-1
          flex-col
          overflow-hidden
        "
      >
        <ChatHeader
          agents={agents}
          agentId={agentId}
          setAgentId={setAgentId}
          provider={provider}
          setProvider={setProvider}
          model={model}
          setModel={setModel}
          workspace={workspace}
          setWorkspace={setWorkspace}
          runtime={chat.runtime}
        />
        <DeliveryContextBar selected={deliveryContext} onChange={value=>{setDeliveryContext(value);globalThis.localStorage?.setItem("axiom.copilot.context",value)}}/>

        {/* -------------------------------- */}
        {/* Chat messages */}
        {/* -------------------------------- */}

        <ChatWindow
          messages={chat.messages}
          loading={chat.loading}
          onPromptClick={handleSend}
        />

        {/* -------------------------------- */}
        {/* Required input */}
        {/* -------------------------------- */}

        {chat.runtime.status === "WAITING_FOR_INPUT" && chat.runtime.requiredInput && (
          <div className="shrink-0 border-t border-white/10 p-4">
            <RequiredInformationCard
              request={
                chat.runtime.requiredInput
              }
              onSubmit={(values) =>
                chat.resumeAgentExecution(
                  values,
                  "input"
                )
              }
              onCancel={chat.stopGeneration}
            />
          </div>
        )}

        {/* -------------------------------- */}
        {/* Approval */}
        {/* -------------------------------- */}

        {chat.runtime.status === "WAITING_FOR_APPROVAL" && chat.runtime.approval && (
          <div className="shrink-0 border-t border-amber-300 bg-amber-50 p-4 text-amber-950">
            <p className="font-medium">
              Approval required
            </p>

            <p className="mt-1 text-sm">
              {chat.runtime.approval
                .summary ||
                "A governed business action is waiting for an authorized decision."}
            </p>

            <div className="mt-3 flex gap-2">
              <button
                onClick={() =>
                  chat.decideApproval("approve")
                }
                className="rounded-lg bg-emerald-600 px-4 py-2 text-sm"
              >
                Approve
              </button>

              <button
                onClick={() =>
                  chat.decideApproval("deny")
                }
                className="rounded-lg border border-rose-400 px-4 py-2 text-sm text-rose-800"
              >
                Deny
              </button>
            </div>
          </div>
        )}

        {/* -------------------------------- */}
        {/* Clarification */}
        {/* -------------------------------- */}

        {chat.activeExecution?.continuation?.kind ===
          "clarification" && (
          <div className="shrink-0 flex gap-2 border-t border-white/10 p-4">
            <span className="text-sm">
              {
                chat.activeExecution.continuation
                  .question
              }
            </span>

            {chat.activeExecution.continuation.alternatives.map(
              (choice) => (
                <button
                  key={choice.id}
                  onClick={() =>
                    chat.resumeAgentExecution(
                      {
                        selected_tool:
                          choice.id,
                      },
                      "clarification"
                    )
                  }
                  className="rounded-lg bg-violet-600 px-3 py-2"
                >
                  {choice.label}
                </button>
              )
            )}
          </div>
        )}

        {/* -------------------------------- */}
        {/* Runtime failure */}
        {/* -------------------------------- */}

        {["FAILED","TIMED_OUT","CANCELLED"].includes(chat.runtime.status) && (
          <div role="alert" className="shrink-0 flex items-center justify-between gap-4 border-t border-rose-300 bg-rose-50 p-4">
            <div>
              <p className="text-sm font-medium text-rose-900">
                {runtimeFailureMessage(chat.runtime)}
              </p>

              <p className="mt-1 text-xs text-slate-500">
                Execution ID:{" "}
                {chat.runtime.executionId}
              </p>
            </div>

            {(chat.runtime.error?.retryable ?? false) && <button
              onClick={chat.retryExecution}
              className="rounded-lg border border-rose-400 bg-white px-4 py-2 text-sm font-semibold text-rose-800"
            >
              Retry
            </button>}
          </div>
        )}

        {/* -------------------------------- */}
        {/* Chat input */}
        {/* -------------------------------- */}

        <div className="shrink-0">
          <ChatInput
            onSend={handleSend}
            onStop={chat.stopGeneration}
            loading={chat.loading}
            disabled={chat.runtime.status === "WAITING_FOR_APPROVAL"}
          />
        </div>
      </section>

      {/* -------------------------------- */}
      {/* Execution Inspector */}
      {/* -------------------------------- */}

      <CopilotInspector contextId={deliveryContext} messages={chat.messages} runtime={chat.runtime} onContextChange={value=>{setDeliveryContext(value);globalThis.localStorage?.setItem("axiom.copilot.context",value)}} />
      <ProposedActionDrawer proposal={proposal} onClose={()=>setProposal(null)}/>
    </div>
  );
}
