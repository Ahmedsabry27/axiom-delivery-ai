export default function createConversationTitle(
  message
) {
  const title = message
    .trim()
    .replace(/\s+/g, " ");

  if (/^(yes|no|ok|okay|sure|continue|approve|deny)$/i.test(title)) {
    return "Axiom Request";
  }

  if (title.length <= 50) {
    return title;
  }

  return title.substring(0, 50) + "...";
}
