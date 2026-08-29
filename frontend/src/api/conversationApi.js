import api from "../services/api";

const API_URL = "/conversations";

// --------------------------------------------------
// Create Conversation
// --------------------------------------------------

export async function createConversation(
  title = "New Conversation"
) {
  const response = await api.post(API_URL, { title });
  return response.data;
}

// --------------------------------------------------
// Get All Conversations
// --------------------------------------------------

export async function getConversations() {
  const response = await api.get(API_URL);
  return response.data;
}

// --------------------------------------------------
// Get Single Conversation
// --------------------------------------------------

export async function getConversation(id) {
  const response = await api.get(`${API_URL}/${id}`);
  return response.data;
}

// --------------------------------------------------
// Get Messages for a Conversation
// --------------------------------------------------

export async function getMessages(
  conversationId
) {
  const response = await api.get(`${API_URL}/${conversationId}/messages`);
  return response.data;
}

// --------------------------------------------------
// Delete Conversation
// --------------------------------------------------

export async function deleteConversation(id) {
  await api.delete(`${API_URL}/${id}`);
  return true;
}

// --------------------------------------------------
// Update Conversation Title
// --------------------------------------------------

export async function updateConversationTitle(
  id,
  title
) {
  const response = await api.patch(`${API_URL}/${id}`, { title });
  return response.data;
}
