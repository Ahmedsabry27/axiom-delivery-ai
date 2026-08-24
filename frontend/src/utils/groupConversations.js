export default function groupConversations(conversations) {
  const groups = {
    Today: [],
    Yesterday: [],
    "Last 7 Days": [],
    "Last 30 Days": [],
    Older: [],
  };

  const today = new Date();
  today.setHours(0, 0, 0, 0);

  conversations.forEach((conversation) => {
    const updated = new Date(conversation.updated_at);

    const date = new Date(updated);
    date.setHours(0, 0, 0, 0);

    const diffDays = Math.floor(
      (today - date) / (1000 * 60 * 60 * 24)
    );

    if (diffDays === 0) {
      groups.Today.push(conversation);
    } else if (diffDays === 1) {
      groups.Yesterday.push(conversation);
    } else if (diffDays <= 7) {
      groups["Last 7 Days"].push(conversation);
    } else if (diffDays <= 30) {
      groups["Last 30 Days"].push(conversation);
    } else {
      groups.Older.push(conversation);
    }
  });

  return groups;
}