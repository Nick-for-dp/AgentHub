import { http } from './http'

export interface EmbedTokenResponse {
  access_token: string
  token_type: string
  expires_in: number
  expires_at: string
}

export interface EmbedSessionStatus {
  authenticated: boolean
  user?: {
    id: string
    external_user_id: string
    name: string
    phone?: string
  } | null
  agent_code?: string | null
  access_expires_in: number
  refreshable: boolean
}

export async function refreshEmbedToken(accessToken?: string): Promise<EmbedTokenResponse> {
  const { data } = await http.post<EmbedTokenResponse>('/embed/refresh', {
    access_token: accessToken,
  })
  return data
}

export async function getEmbedSession(): Promise<EmbedSessionStatus> {
  const { data } = await http.get<EmbedSessionStatus>('/embed/session')
  return data
}
