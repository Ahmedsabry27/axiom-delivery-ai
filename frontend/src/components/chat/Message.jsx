import AssistantMessage from "./AssistantMessage";
import UserMessage from "./UserMessage";

export default function Message({ message }) {
  if (!message) return null;

  if (message.role === "user") {
    return <UserMessage message={message} />;
  }

  return <AssistantMessage message={message} />;
}