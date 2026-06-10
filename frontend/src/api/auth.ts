/** 认证 API：登录、查看当前用户、刷新 token、登出。 */

import { http } from './http'

export interface LoginRequest {
  phone: string
  password: string
}

export interface UserSummary {
  id: string
  name: string
  phone: string | null
  org_unit_id: string
  org_unit_name: string | null
  is_admin: boolean
}

export interface SessionResponse {
  user: UserSummary
  access_expires_at: string
  idle_expires_at: string
  expires_in: number
  idle_expires_in: number
}

export interface SessionStatusResponse {
  authenticated: boolean
  user: UserSummary | null
  access_expires_at: string | null
  idle_expires_at: string | null
  expires_in: number
  idle_expires_in: number
}

export async function login(payload: LoginRequest): Promise<SessionResponse> {
  const { data } = await http.post<SessionResponse>('/auth/login', payload)
  return data
}

export async function getMe(): Promise<SessionResponse> {
  const { data } = await http.get<SessionResponse>('/auth/me')
  return data
}

export async function getSessionStatus(): Promise<SessionStatusResponse> {
  const { data } = await http.get<SessionStatusResponse>('/auth/session')
  return data
}

export async function refreshSession(): Promise<SessionResponse> {
  const { data } = await http.post<SessionResponse>('/auth/refresh')
  return data
}

export async function logout(): Promise<void> {
  await http.post('/auth/logout')
}
