/**
 * Admin API 函数。
 *
 * 所有 /admin/* 请求默认携带 HttpOnly Cookie session。
 * 后端会校验认证（get_current_subject）+ 管理授权（require_admin_permission）。
 */
import { http } from './http'
import type {
  Agent,
  AgentBusinessFollowupPage,
  AgentCreate,
  AgentKnowledgeBaseBind,
  AgentUpdate,
  AnalyticsFilter,
  APIKeyIssued,
  APIKeyRecord,
  APIResponse,
  DAUItem,
  DocumentCreate,
  DocumentRead,
  InvocationRecordFilter,
  InvocationRecordPage,
  KnowledgeBase,
  KnowledgeBaseCreate,
  OrgUnit,
  SalesLeadFilter,
  SalesLeadPage,
  UserChatDurationPage,
  UserMessageCountPage,
} from './types'

// ======================== Agents ========================

export async function listAgents() {
  const { data } = await http.get<APIResponse<Agent[]>>('/admin/agents')
  return data.data
}

export async function createAgent(payload: AgentCreate) {
  const { data } = await http.post<APIResponse<Agent>>('/admin/agents', payload)
  return data.data
}

export async function updateAgent(id: string, payload: AgentUpdate) {
  const { data } = await http.put<APIResponse<Agent>>(`/admin/agents/${id}`, payload)
  return data.data
}

// ======================== Org Units ========================

export async function listOrgUnits() {
  const { data } = await http.get<APIResponse<OrgUnit[]>>('/admin/org-units')
  return data.data
}

/** 将知识库绑定到 Agent（Agent-KB 多对多关系） */
export async function bindKnowledgeBase(
  agentId: string,
  knowledgeBaseId: string,
  priority = 100,
) {
  const { data } = await http.post<APIResponse<Record<string, string>>>(
    `/admin/agents/${agentId}/knowledge-bases`,
    { knowledge_base_id: knowledgeBaseId, priority },
  )
  return data.data
}

/** 查询 Agent 已绑定的知识库列表 */
export async function listAgentKnowledgeBases(agentId: string) {
  const { data } = await http.get<APIResponse<AgentKnowledgeBaseBind[]>>(
    `/admin/agents/${agentId}/knowledge-bases`,
  )
  return data.data
}

/** 解除 Agent 与知识库的绑定 */
export async function unbindKnowledgeBase(agentId: string, knowledgeBaseId: string) {
  await http.delete(`/admin/agents/${agentId}/knowledge-bases/${knowledgeBaseId}`)
}

// ======================== Knowledge Bases ========================

export async function listKnowledgeBases() {
  const { data } = await http.get<APIResponse<KnowledgeBase[]>>('/admin/knowledge-bases')
  return data.data
}

export async function createKnowledgeBase(payload: KnowledgeBaseCreate) {
  const { data } = await http.post<APIResponse<KnowledgeBase>>('/admin/knowledge-bases', payload)
  return data.data
}

// ======================== Documents ========================

export async function listDocuments() {
  const { data } = await http.get<APIResponse<DocumentRead[]>>('/admin/documents')
  return data.data
}

export async function createDocument(payload: DocumentCreate) {
  const { data } = await http.post<APIResponse<DocumentRead>>('/admin/documents', payload)
  return data.data
}

// ======================== API Keys ========================

export async function listApiKeys() {
  const { data } = await http.get<APIResponse<APIKeyRecord[]>>('/admin/api-keys')
  return data.data
}

export async function issueApiKeyByPhone(payload: {
  phone: string
  name: string
  scopes: string[]
}) {
  const { data } = await http.post<APIResponse<APIKeyIssued>>(
    '/admin/api-keys/by-phone',
    payload,
  )
  return data.data
}

// ======================== Invocation Records ========================

export async function listInvocationRecords(filter: InvocationRecordFilter = {}) {
  const params: Record<string, string | number> = {}
  if (filter.agent_id) params.agent_id = filter.agent_id
  if (filter.agent_code) params.agent_code = filter.agent_code
  if (filter.status) params.status = filter.status
  if (filter.api_key_id) params.api_key_id = filter.api_key_id
  if (filter.created_from) params.created_from = filter.created_from
  if (filter.created_to) params.created_to = filter.created_to
  if (filter.page) params.page = filter.page
  if (filter.page_size) params.page_size = filter.page_size
  const { data } = await http.get<APIResponse<InvocationRecordPage>>(
    '/admin/invocation-records',
    { params },
  )
  return data.data
}

// ======================== Sales Leads ========================

export async function listSalesLeads(filter: SalesLeadFilter = {}) {
  const params: Record<string, string | number> = {}
  if (filter.keyword) params.keyword = filter.keyword
  if (filter.status) params.status = filter.status
  if (filter.created_from) params.created_from = filter.created_from
  if (filter.created_to) params.created_to = filter.created_to
  if (filter.page) params.page = filter.page
  if (filter.page_size) params.page_size = filter.page_size
  const { data } = await http.get<APIResponse<SalesLeadPage>>('/admin/leads', { params })
  return data.data
}

// ======================== Analytics ========================

function _analyticsParams(filter: AnalyticsFilter): Record<string, string | number> {
  const params: Record<string, string | number> = {}
  if (filter.created_from) params.created_from = filter.created_from
  if (filter.created_to) params.created_to = filter.created_to
  if (filter.agent_code) params.agent_code = filter.agent_code
  if (filter.user_id) params.user_id = filter.user_id
  if (filter.org_unit_id) params.org_unit_id = filter.org_unit_id
  if (filter.page) params.page = filter.page
  if (filter.page_size) params.page_size = filter.page_size
  return params
}

export async function fetchDailyActiveUsers(filter: AnalyticsFilter = {}) {
  const { data } = await http.get<APIResponse<DAUItem[]>>(
    '/admin/analytics/daily-active-users',
    { params: _analyticsParams(filter) },
  )
  return data.data
}

export async function fetchUserMessageCounts(filter: AnalyticsFilter = {}) {
  const { data } = await http.get<APIResponse<UserMessageCountPage>>(
    '/admin/analytics/user-message-counts',
    { params: _analyticsParams(filter) },
  )
  return data.data
}

export async function fetchUserChatDuration(filter: AnalyticsFilter = {}) {
  const { data } = await http.get<APIResponse<UserChatDurationPage>>(
    '/admin/analytics/user-chat-duration',
    { params: _analyticsParams(filter) },
  )
  return data.data
}

export async function fetchAgentBusinessFollowups(filter: AnalyticsFilter = {}) {
  const { data } = await http.get<APIResponse<AgentBusinessFollowupPage>>(
    '/admin/analytics/agent-business-followups',
    { params: _analyticsParams(filter) },
  )
  return data.data
}
