import { getAccessToken } from "../services/auth";

const API_URL = `${import.meta.env.VITE_API_URL}/conversations`;

// --------------------------------------------------
// Helper
// --------------------------------------------------

async function getAuthHeaders() {
  const token = await getAccessToken();

  return {
    Authorization: `Bearer ${token}`,
    "Content-Type": "application/json",
  };
}

// --------------------------------------------------
// Create Conversation
// --------------------------------------------------

export async function createConversation(
  title = "New Conversation"
) {
  const response = await fetch(API_URL, {
    method: "POST",
    headers: await getAuthHeaders(),
    body: JSON.stringify({
      title,
    }),
  });

  if (!response.ok) {
    throw new Error("Failed to create conversation");
  }

  return response.json();
}

// --------------------------------------------------
// Get All Conversations
// --------------------------------------------------

export async function getConversations() {
  const token = await getAccessToken();

  const response = await fetch(API_URL, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Failed to load conversations");
  }

  return response.json();
}

// --------------------------------------------------
// Get Single Conversation
// --------------------------------------------------

export async function getConversation(id) {
  const token = await getAccessToken();

  const response = await fetch(`${API_URL}/${id}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Conversation not found");
  }

  return response.json();
}

// --------------------------------------------------
// Get Messages for a Conversation
// --------------------------------------------------

export async function getMessages(
  conversationId
) {
  const token = await getAccessToken();

  const response = await fetch(
    `${API_URL}/${conversationId}/messages`,
    {
      headers: {
        Authorization: `Bearer ${token}`,
      },
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to load messages"
    );
  }

  return response.json();
}

// --------------------------------------------------
// Delete Conversation
// --------------------------------------------------

export async function deleteConversation(id) {
  const token = await getAccessToken();

  const response = await fetch(`${API_URL}/${id}`, {
    method: "DELETE",
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (!response.ok) {
    throw new Error("Delete failed");
  }

  return true;
}

// --------------------------------------------------
// Update Conversation Title
// --------------------------------------------------

export async function updateConversationTitle(
  id,
  title
) {
  const response = await fetch(
    `${API_URL}/${id}`,
    {
      method: "PATCH",
      headers: await getAuthHeaders(),
      body: JSON.stringify({
        title,
      }),
    }
  );

  if (!response.ok) {
    throw new Error(
      "Failed to update conversation title"
    );
  }

  return response.json();
}