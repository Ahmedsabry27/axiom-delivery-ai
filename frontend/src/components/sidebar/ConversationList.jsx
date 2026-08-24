import groupConversations from "../../utils/groupConversations";
import ConversationItem from "./ConversationItem";

export default function ConversationList({
  conversations = [],
  loading = false,
  onConversationSelect,
  conversationId,
}) {
  if (loading) {
    return (
      <div className="px-3 py-4 text-sm text-muted-foreground">
        Loading conversations...
      </div>
    );
  }

  // Safety check
  if (!Array.isArray(conversations) || conversations.length === 0) {

    return (

      <div
        className="
          px-4
          py-6
          text-center
          text-sm
          text-muted-foreground
        "
      >

        No conversations yet

        <br />

        Start a new AI workflow 🚀

      </div>

    );

}

  const groups = groupConversations(conversations);

  return (
    <div className="px-3">
      {Object.entries(groups).map(([groupName, items]) => {
        if (!items?.length) return null;

        return (
          <div key={groupName} className="mb-5">
            <p className="mb-2 text-xs font-semibold text-muted-foreground">
              {groupName}
            </p>

            {items.map((conversation) => (
              <ConversationItem
                key={conversation.id}
                conversation={conversation}
                onClick={onConversationSelect}
                isActive={conversation.id === conversationId}
              />
            ))}
          </div>
        );
      })}
    </div>
  );
}