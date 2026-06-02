/**
 * Admin API 函数。
 *
 * 所有 /admin/* 请求默认携带 HttpOnly Cookie session。
 * 后端会校验认证（get_current_subject）+ 管理授权（require_admin_permission）。
 */
import { http } from './http';
// ======================== Agents ========================
export async function listAgents() {
    const { data } = await http.get('/admin/agents');
    return data.data;
}
export async function createAgent(payload) {
    const { data } = await http.post('/admin/agents', payload);
    return data.data;
}
export async function updateAgent(id, payload) {
    const { data } = await http.put(`/admin/agents/${id}`, payload);
    return data.data;
}
// ======================== Org Units ========================
export async function listOrgUnits() {
    const { data } = await http.get('/admin/org-units');
    return data.data;
}
/** 将知识库绑定到 Agent（Agent-KB 多对多关系） */
export async function bindKnowledgeBase(agentId, knowledgeBaseId, priority = 100) {
    const { data } = await http.post(`/admin/agents/${agentId}/knowledge-bases`, { knowledge_base_id: knowledgeBaseId, priority });
    return data.data;
}
/** 查询 Agent 已绑定的知识库列表 */
export async function listAgentKnowledgeBases(agentId) {
    const { data } = await http.get(`/admin/agents/${agentId}/knowledge-bases`);
    return data.data;
}
/** 解除 Agent 与知识库的绑定 */
export async function unbindKnowledgeBase(agentId, knowledgeBaseId) {
    await http.delete(`/admin/agents/${agentId}/knowledge-bases/${knowledgeBaseId}`);
}
// ======================== Knowledge Bases ========================
export async function listKnowledgeBases() {
    const { data } = await http.get('/admin/knowledge-bases');
    return data.data;
}
export async function createKnowledgeBase(payload) {
    const { data } = await http.post('/admin/knowledge-bases', payload);
    return data.data;
}
// ======================== Documents ========================
export async function listDocuments() {
    const { data } = await http.get('/admin/documents');
    return data.data;
}
export async function createDocument(payload) {
    const { data } = await http.post('/admin/documents', payload);
    return data.data;
}
// ======================== API Keys ========================
export async function listApiKeys() {
    const { data } = await http.get('/admin/api-keys');
    return data.data;
}
export async function issueApiKeyByPhone(payload) {
    const { data } = await http.post('/admin/api-keys/by-phone', payload);
    return data.data;
}
// ======================== Invocation Records ========================
export async function listInvocationRecords(filter = {}) {
    const params = {};
    if (filter.agent_id)
        params.agent_id = filter.agent_id;
    if (filter.agent_code)
        params.agent_code = filter.agent_code;
    if (filter.status)
        params.status = filter.status;
    if (filter.api_key_id)
        params.api_key_id = filter.api_key_id;
    if (filter.created_from)
        params.created_from = filter.created_from;
    if (filter.created_to)
        params.created_to = filter.created_to;
    if (filter.page)
        params.page = filter.page;
    if (filter.page_size)
        params.page_size = filter.page_size;
    const { data } = await http.get('/admin/invocation-records', { params });
    return data.data;
}
// ======================== Sales Leads ========================
export async function listSalesLeads(filter = {}) {
    const params = {};
    if (filter.keyword)
        params.keyword = filter.keyword;
    if (filter.status)
        params.status = filter.status;
    if (filter.agent_code)
        params.agent_code = filter.agent_code;
    if (filter.region)
        params.region = filter.region;
    if (filter.has_contact !== undefined)
        params.has_contact = filter.has_contact;
    if (filter.created_from)
        params.created_from = filter.created_from;
    if (filter.created_to)
        params.created_to = filter.created_to;
    if (filter.page)
        params.page = filter.page;
    if (filter.page_size)
        params.page_size = filter.page_size;
    const { data } = await http.get('/admin/leads', { params });
    return data.data;
}
