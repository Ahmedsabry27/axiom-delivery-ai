import { useState } from "react";

import Sidebar from "../sidebar/Sidebar";
import Header from "./Header";

import ChatWindow from "../chat/ChatWindow";
import Composer from "../chat/Composer";

import useConversations from "../../hooks/useConversation";

import {
  getConversationMessages,
} from "../../services/conversationService";

export default function MainLayout() {
  // --------------------------------------------------
  // Sidebar state
  // --------------------------------------------------

  const [sidebarCollapsed, setSidebarCollapsed] =
    useState(false);

  // --------------------------------------------------
  // Chat state
  // --------------------------------------------------

  const [messages, setMessages] = useState([]);

  const [loading, setLoading] = useState(false);

  const [conversationId, setConversationId] =
    useState(null);

  const {
    conversations,
    loading: conversationsLoading,
    refreshConversations,
  } = useConversations();

  // --------------------------------------------------
  // New Chat
  // --------------------------------------------------

  function handleNewChat() {
    setMessages([]);
    setConversationId(null);
  }

  // --------------------------------------------------
  // Select Conversation
  // --------------------------------------------------

  async function handleConversationSelect(
    conversation
  ) {
    try {
      setLoading(true);

      const data =
        await getConversationMessages(
          conversation.id
        );

      setConversationId(
        conversation.id
      );

      setMessages(
        data
      );
    } catch (error) {
      console.error(
        "Failed loading conversation",
        error
      );
    } finally {
      setLoading(false);
    }
  }

  // --------------------------------------------------
  // Render
  // --------------------------------------------------

  return (
    <div
      className="
        flex
        h-screen
        w-full
        min-w-0
        overflow-hidden
        bg-background
      "
    >
      {/* ==================================================
          Sidebar
      ================================================== */}

      <Sidebar
        collapsed={
          sidebarCollapsed
        }
        onCollapsedChange={
          setSidebarCollapsed
        }

        conversations={
          conversations
        }
        loading={
          conversationsLoading
        }
        onConversationSelect={
          handleConversationSelect
        }
        onNewChat={
          handleNewChat
        }
        conversationId={
          conversationId
        }
      />

      {/* ==================================================
          Application Content
      ================================================== */}

      <div
        className="
          flex
          min-w-0
          min-h-0
          flex-1
          flex-col
          overflow-hidden
          transition-all
          duration-300
          ease-in-out
        "
      >
        {/* Header */}

        <Header />

        {/* ==================================================
            Main Chat Area
        ================================================== */}

        <main
          className="
            flex
            min-h-0
            min-w-0
            flex-1
            flex-col
            overflow-hidden
          "
        >
          {/* Messages */}

          <div
            className="
              min-h-0
              min-w-0
              flex-1
              overflow-hidden
            "
          >
            <ChatWindow
              messages={
                messages
              }
              loading={
                loading
              }
            />
          </div>

          {/* Composer */}

          <div
            className="
              shrink-0
              border-t
              bg-background
            "
          >
            <Composer
              setMessages={
                setMessages
              }
              loading={
                loading
              }
              setLoading={
                setLoading
              }
              conversationId={
                conversationId
              }
              setConversationId={
                setConversationId
              }
              refreshConversations={
                refreshConversations
              }
            />
          </div>
        </main>
      </div>
    </div>
  );
}