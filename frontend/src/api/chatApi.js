import { getAccessToken } from "../services/auth";

const API_URL = `${import.meta.env.VITE_API_URL}/chat`;

console.log("API URL:", API_URL);

/**
 * ----------------------------------------
 * Synchronous Chat
 * ----------------------------------------
 */
export async function sendMessage({
  message,
  conversationId,
  previousResponseId = null,
}) {
  const payload = {
    message,
    conversation_id: conversationId,
    previous_response_id: previousResponseId,
  };

  // Get Cognito Access Token
  const token = await getAccessToken();

  const response = await fetch(API_URL, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const error = await response.text();

    throw new Error(
      error || "Failed to communicate with backend"
    );
  }

  return response.json();
}

/**
 * ----------------------------------------
 * Streaming Chat (SSE)
 * ----------------------------------------
 */
export async function streamMessage({
  message,
  conversationId,
  previousResponseId = null,
  signal,
  onStart,
  onDelta,
  onCompleted,
  onError,
}) {
  const payload = {
    message,
    conversation_id: conversationId,
    previous_response_id: previousResponseId,
  };

  // Get Cognito Access Token
  const token = await getAccessToken();

  const response = await fetch(`${API_URL}/stream`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${token}`,
      "Content-Type": "application/json",
      Accept: "text/event-stream",
    },
    body: JSON.stringify(payload),
    signal,
  });

  if (!response.ok) {
    throw new Error(await response.text());
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();

  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();

    if (done) break;

    buffer += decoder.decode(value, {
      stream: true,
    });

    const events = buffer.split("\n\n");
    buffer = events.pop() || "";

    for (const event of events) {
      if (!event.startsWith("data:")) continue;

      const json = event.replace("data:", "").trim();

      if (!json) continue;

      const data = JSON.parse(json);

      switch (data.type) {
        case "start":
          onStart?.();
          break;

        case "delta":
          onDelta?.(data.text);
          break;

        case "completed":
          onCompleted?.(data.response_id);
          break;

        case "error":
          onError?.(data.message);
          break;

        default:
          break;
      }
    }
  }
}