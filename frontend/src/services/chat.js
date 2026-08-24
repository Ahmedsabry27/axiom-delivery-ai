import api from "../services/api";


export async function sendMessage(
  message,
  conversationId = null
) {

  const response =
    await api.post(
      "/api/conversations/message",
      {
        message,
        conversation_id: conversationId,
      }
    );


  return response.data;

}