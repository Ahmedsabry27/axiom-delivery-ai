import {
  Sidebar as UISidebar,
  SidebarContent,
} from "@/components/ui/sidebar";

import SidebarHeader from "./SidebarHeader";
import ConversationList from "./ConversationList";
import SidebarFooter from "./SidebarFooter";

export default function Sidebar({
  conversations,
  loading,
  onConversationSelect,
  onNewChat,
  conversationId,
}) {
  return (
    <UISidebar>
      <SidebarHeader
        onNewChat={onNewChat}
      />

      <SidebarContent>
        <ConversationList
          conversations={conversations}
          loading={loading}
          onConversationSelect={onConversationSelect}
          conversationId={conversationId}
        />
      </SidebarContent>

      <SidebarFooter />
    </UISidebar>
  );
}