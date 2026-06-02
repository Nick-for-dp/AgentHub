import { http } from './http';
export async function getCurrentConversation(agentCode) {
    const { data } = await http.get('/conversations/current', {
        params: { agent_code: agentCode },
    });
    return data.data;
}
export async function createConversation(agentCode, title) {
    const { data } = await http.post('/conversations', {
        agent_code: agentCode,
        title,
    });
    return data.data;
}
export async function getConversation(conversationId) {
    const { data } = await http.get(`/conversations/${conversationId}`);
    return data.data;
}
export async function getConversationMessages(conversationId) {
    const { data } = await http.get(`/conversations/${conversationId}/messages`);
    return data.data;
}
export async function archiveConversation(conversationId) {
    const { data } = await http.patch(`/conversations/${conversationId}`, {
        status: 'ARCHIVED',
    });
    return data.data;
}
