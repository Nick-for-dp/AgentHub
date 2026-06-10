import { http } from './http'
import type { APIResponse } from './types'

export interface Conversation {
  id: string
  agent_id: string
  agent_code: string
  user_id: string
  org_unit_id?: string
  title: string
  provider: string
  provider_conversation_id?: string
  status: string
  last_message_at: string
  created_at: string
  updated_at: string
}

export interface ConversationMessage {
  id: string
  conversation_id: string
  sequence_no: number
  role: 'USER' | 'ASSISTANT' | 'SYSTEM'
  content: string
  thought?: string
  steps: Array<Record<string, unknown>>
  provider_message_id?: string
  invocation_record_id?: string
  status: string
  created_at: string
  updated_at: string
}

export interface ConversationWithMessages {
  conversation: Conversation | null
  messages: ConversationMessage[]
}

export interface ConversationPage {
  items: Conversation[]
  total: number
  page: number
  page_size: number
}

export async function getCurrentConversation(agentCode: string): Promise<ConversationWithMessages> {
  const { data } = await http.get<APIResponse<ConversationWithMessages>>('/conversations/current', {
    params: { agent_code: agentCode },
  })
  return data.data
}

export async function createConversation(agentCode: string, title?: string): Promise<Conversation> {
  const { data } = await http.post<APIResponse<Conversation>>('/conversations', {
    agent_code: agentCode,
    title,
  })
  return data.data
}

export async function getConversation(conversationId: string): Promise<Conversation> {
  const { data } = await http.get<APIResponse<Conversation>>(`/conversations/${conversationId}`)
  return data.data
}

export async function getConversationMessages(conversationId: string): Promise<ConversationMessage[]> {
  const { data } = await http.get<APIResponse<ConversationMessage[]>>(
    `/conversations/${conversationId}/messages`,
  )
  return data.data
}

export async function listConversations(
  agentCode?: string,
  page = 1,
  pageSize = 50,
): Promise<ConversationPage> {
  const { data } = await http.get<APIResponse<ConversationPage>>('/conversations', {
    params: { agent_code: agentCode, page, page_size: pageSize },
  })
  return data.data
}

export async function archiveConversation(conversationId: string): Promise<Conversation> {
  const { data } = await http.patch<APIResponse<Conversation>>(`/conversations/${conversationId}`, {
    status: 'ARCHIVED',
  })
  return data.data
}

export async function deleteConversation(conversationId: string): Promise<void> {
  await http.delete<APIResponse<null>>(`/conversations/${conversationId}`)
}
