import { http } from './http'

export interface EmbedExchangeResponse {
  authenticated: boolean
  expires_in: number
}

export interface EmbedSessionStatus {
  authenticated: boolean
  user?: {
    id: string
    phone?: string
  } | null
  agent_code?: string | null
  expires_in: number
}

export async function exchangeEmbedToken(
  token: string,
  agentCode: string,
): Promise<EmbedExchangeResponse> {
  const { data } = await http.post<EmbedExchangeResponse>('/embed/exchange', {
    token,
    agent_code: agentCode,
  })
  return data
}

export async function getEmbedSession(): Promise<EmbedSessionStatus> {
  const { data } = await http.get<EmbedSessionStatus>('/embed/session')
  return data
}

export async function logoutEmbedSession(): Promise<{ revoked: boolean }> {
  const { data } = await http.post<{ revoked: boolean }>('/embed/logout')
  return data
}
