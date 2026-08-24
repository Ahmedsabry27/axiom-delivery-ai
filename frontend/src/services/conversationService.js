import api from "./api";



/**
 * Create new conversation
 */
export async function createConversation(
  title = "New Conversation"
) {

  const response =
    await api.post(
      "/conversations",
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
      "/conversations"
    );


  return response.data;


}







/**
 * Get conversation details
 */
export async function getConversation(
  conversationId
){

  const response =
    await api.get(
      `/conversations/${conversationId}`
    );


  return response.data;

}








/**
 * Get messages inside conversation
 */
export async function getConversationMessages(
  conversationId
){

  const response =
    await api.get(
      `/conversations/${conversationId}/messages`
    );


  return response.data;

}








/**
 * Update conversation title
 */
export async function updateConversationTitle(
  conversationId,
  title
){

  const response =
    await api.patch(
      `/conversations/${conversationId}`,
      {
        title,
      }
    );


  return response.data;

}

export async function updateConversation(conversationId, changes){
  const response=await api.patch(`/conversations/${conversationId}`,changes);
  return response.data;
}







/**
 * Delete conversation
 */
export async function deleteConversation(
  conversationId
){


  const response =
    await api.delete(
      `/conversations/${conversationId}`
    );


  return response.data;


}







/**
 * Archive conversation
 * (future enterprise feature)
 */
export async function archiveConversation(
  conversationId
){

  const response =
    await api.patch(
      `/conversations/${conversationId}/archive`
    );


  return response.data;

}







/**
 * Search conversations
 * (future enterprise feature)
 */
export async function searchConversations(
  query
){


  const response =
    await api.get(
      "/conversations/search",
      {
        params:{
          q:query
        }
      }
    );


  return response.data;

}
