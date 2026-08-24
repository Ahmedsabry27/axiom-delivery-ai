import api from "./api";



/**
 * Create new conversation
 */
export async function createConversation(
  title = "New Conversation"
) {

  const response =
    await api.post(
      "/api/conversations",
      {
        title,
      }
    );


  return response.data;

}





/**
 * Get all conversations
 */
export async function getConversations() {

  const response =
    await api.get(
      "/api/conversations"
    );


  return response.data;

}





/**
 * Get conversation messages
 */
export async function getConversationMessages(
  conversationId
) {


  const response =
    await api.get(
      `/api/conversations/${conversationId}/messages`
    );


  return response.data;

}





/**
 * Add message to conversation
 * (Useful for runtime persistence)
 */
export async function addConversationMessage(
  conversationId,
  payload
) {


  const response =
    await api.post(
      `/api/conversations/${conversationId}/messages`,
      payload
    );


  return response.data;

}





/**
 * Rename conversation
 */
export async function renameConversation(
  conversationId,
  title
) {


  const response =
    await api.patch(
      `/api/conversations/${conversationId}`,
      {
        title,
      }
    );


  return response.data;

}





/**
 * Delete conversation
 */
export async function deleteConversation(
  conversationId
) {


  await api.delete(
    `/api/conversations/${conversationId}`
  );


  return true;

}





/**
 * Get single conversation
 */
export async function getConversation(
  conversationId
) {


  const response =
    await api.get(
      `/api/conversations/${conversationId}`
    );


  return response.data;

}





/**
 * Update conversation metadata
 * (workflow/runtime information)
 */
export async function updateConversationMetadata(
  conversationId,
  metadata
) {


  const response =
    await api.patch(
      `/api/conversations/${conversationId}/metadata`,
      metadata
    );


  return response.data;

}