/** AgentHub 前端类型定义，对应后端 Pydantic Schema。 */

export interface APIResponse<T> {
  code: string
  message: string
  data: T
  request_id?: string
}

// ======================== Agent ========================

export interface Agent {
  id: string
  code: string
  name: string
  type: string
  description?: string
  owner_org_unit_id: string
  runtime_type: string
  runtime_app_id?: string
  version: number
  publish_status: string
  visibility: string
  /** config_snapshot 中的敏感字段已被后端脱敏为 "***" */
  config_snapshot: Record<string, unknown>
  created_by?: string
  created_at: string
  updated_at: string
}

export interface AgentCreate {
  code: string
  name: string
  type?: string
  description?: string
  owner_org_unit_id: string
  runtime_type?: string
  runtime_app_id?: string
  visibility?: string
  config_snapshot?: Record<string, unknown>
}

export interface AgentUpdate {
  name?: string
  description?: string
  runtime_type?: string
  runtime_app_id?: string
  publish_status?: string
  visibility?: string
  config_snapshot?: Record<string, unknown>
}

// ======================== Org ========================

export interface OrgUnit {
  id: string
  name: string
  type: string
  parent_id?: string
  status: string
  created_at: string
  updated_at: string
}

/** Agent-KB 绑定关系 */
export interface AgentKnowledgeBaseBind {
  id: string
  agent_id: string
  knowledge_base_id: string
  priority: number
  status: string
  created_at: string
}

// ======================== KnowledgeBase ========================

export interface KnowledgeBase {
  id: string
  name: string
  owner_org_unit_id: string
  provider: string
  provider_kb_id?: string
  embedding_model?: string
  retrieval_config: Record<string, unknown>
  status: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface KnowledgeBaseCreate {
  name: string
  owner_org_unit_id: string
  provider?: string
  provider_kb_id?: string
  embedding_model?: string
  retrieval_config?: Record<string, unknown>
}

// ======================== Document ========================

export interface DocumentRead {
  id: string
  knowledge_base_id: string
  owner_org_unit_id: string
  file_name: string
  file_type?: string
  file_size?: number
  storage_uri?: string
  provider_doc_id?: string
  parse_status: string
  parser_version?: string
  embedding_model?: string
  chunk_version?: string
  failed_reason?: string
  created_by?: string
  created_at: string
  updated_at: string
}

export interface DocumentCreate {
  knowledge_base_id: string
  owner_org_unit_id: string
  file_name: string
  file_type?: string
  file_size?: number
  storage_uri?: string
  provider_doc_id?: string
  parser_version?: string
  embedding_model?: string
  chunk_version?: string
}

// ======================== API Key ========================

export interface APIKeyRecord {
  id: string
  key_prefix: string
  owner_type: string
  owner_id: string
  issued_for_phone?: string
  name: string
  scopes: string[]
  status: string
  expires_at?: string
  last_used_at?: string
  created_at: string
  updated_at: string
}

export interface APIKeyIssued {
  /** 完整 API Key，仅签发时返回一次，之后不可再次获取 */
  api_key: string
  record: APIKeyRecord
}

// ======================== Invocation Record ========================

export interface InvocationRecord {
  id: string
  request_id: string
  trace_id?: string
  agent_id: string
  agent_code?: string
  agent_name?: string
  org_unit_id?: string
  org_unit_name?: string
  user_id?: string
  customer_name?: string
  customer_phone?: string
  api_key_id?: string
  api_key_name?: string
  api_key_prefix?: string
  caller_type: string
  source_channel?: string
  operation_type: string
  input: Record<string, unknown>
  output: Record<string, unknown>
  stream_mode: boolean
  status: string
  error_code?: string
  error_message?: string
  token_usage: Record<string, unknown>
  latency_ms?: number
  retrieval_snapshot: Record<string, unknown>
  model_snapshot: Record<string, unknown>
  runtime_snapshot: Record<string, unknown>
  session_id?: string
  parent_id?: string
  feedback_score?: number
  evaluation_score?: number
  created_at: string
  finished_at?: string
}

export interface InvocationRecordPage {
  items: InvocationRecord[]
  total: number
  page: number
  page_size: number
}

export interface InvocationRecordFilter {
  agent_id?: string
  agent_code?: string
  status?: string
  api_key_id?: string
  created_from?: string
  created_to?: string
  page?: number
  page_size?: number
}

// ======================== Sales Lead ========================

export interface LeadCaptureEvent {
  id: string
  conversation_id?: string
  conversation_message_id?: string
  invocation_record_id?: string
  sales_lead_id?: string
  contact_id?: string
  action?: string
  status: string
  reason?: string
  raw_delta: Record<string, unknown>
  normalized_delta: Record<string, unknown>
  followup_decision: Record<string, unknown>
  created_at: string
}

export interface SalesLead {
  id: string
  contact_id?: string
  conversation_id?: string
  agent_id?: string
  agent_code?: string
  agent_name?: string
  user_id?: string
  org_unit_id?: string
  org_unit_name?: string
  customer_name?: string
  company_name?: string
  contact_type?: string
  contact_value?: string
  phone_normalized?: string
  requirement_summary?: string
  requirement_types: string[]
  region?: string
  missing_fields: string[]
  status: string
  has_contact: boolean
  event_count: number
  latest_event?: LeadCaptureEvent
  created_at: string
  updated_at: string
}

export interface SalesLeadPage {
  items: SalesLead[]
  total: number
  page: number
  page_size: number
}

export interface SalesLeadFilter {
  keyword?: string
  status?: string
  created_from?: string
  created_to?: string
  page?: number
  page_size?: number
}

// ======================== Analytics ========================

/** 单日活跃用户数 */
export interface DAUItem {
  date: string
  active_users: number
}

/** 用户消息发送次数排行条目 */
export interface UserMessageCountItem {
  user_id: string
  user_name?: string
  phone_normalized?: string
  org_unit_name?: string
  message_count: number
  last_message_at?: string
  agent_codes: string[]
}

export interface UserMessageCountPage {
  items: UserMessageCountItem[]
  total: number
  page: number
  page_size: number
}

/** 用户聊天活跃跨度（根据消息时间估算） */
export interface UserChatDurationItem {
  user_id: string
  user_name?: string
  chat_date: string
  first_message_at?: string
  last_message_at?: string
  duration_seconds: number
  message_count: number
}

export interface UserChatDurationPage {
  items: UserChatDurationItem[]
  total: number
  page: number
  page_size: number
}

/** 智能体业务追问次数 */
export interface AgentBusinessFollowupItem {
  agent_code?: string
  agent_name?: string
  followup_count: number
}

export interface AgentBusinessFollowupPage {
  items: AgentBusinessFollowupItem[]
  total: number
  page: number
  page_size: number
}

/** 统计指标通用筛选参数 */
export interface AnalyticsFilter {
  created_from?: string
  created_to?: string
  agent_code?: string
  user_id?: string
  org_unit_id?: string
  page?: number
  page_size?: number
}
