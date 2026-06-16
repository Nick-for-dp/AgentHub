/** SSE 流式聊天 API。 */

import { isEmbedSessionActive } from '../utils/embedAuth'

export interface ChatPayload {
  question: string
  conversation_id?: string
  stream?: boolean
}

export interface ChatError {
  status: number
  message: string
}

export interface StreamEvent {
  answer?: string
  thought?: string
  conversation_id?: string
  provider_conversation_id?: string
  message_id?: string
  event?: string
  message?: string
  /** Dify workflow 节点事件数据（含 node_retry 重试状态） */
  node?: {
    event?: string
    node_id?: string
    node_type?: string
    title?: string
    status?: string
    elapsed_time?: number
    error?: string
    retry_index?: number
  }
  /** Dify 顶层 error 事件消息（workflow 执行失败时由 Dify 发送） */
  error?: string
}

/**
 * 流式调用 Agent Q&A。
 *
 * 使用原生 fetch 读取 SSE 流（axios 不支持流式响应）。
 * 如果后端返回非 2xx，会尝试解析 JSON 错误信息并抛出 ChatError。
 * onEvent 回调接收结构化事件，包含 answer（回答增量）和 thought（思考过程）。
 */
export async function streamChat(
  agentCode: string,
  payload: ChatPayload,
  onEvent: (event: StreamEvent) => void,
) {
  const response = await fetch(`/api/v1/chat/${agentCode}`, {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(isEmbedSessionActive() ? { 'X-AgentHub-Embed': 'true' } : {}),
    },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let errMsg = `HTTP ${response.status}`
    try {
      const body = await response.json()
      // 后端 APIResponse 格式：{ code, message, data }
      if (body.message) errMsg = body.message
      else if (body.detail) errMsg = body.detail
    } catch {
      // 响应体不是 JSON，使用默认错误信息
    }
    throw { status: response.status, message: errMsg } as ChatError
  }

  if (!response.body) {
    throw { status: 0, message: '响应体为空' } as ChatError
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder('utf-8')
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })

    const lines = buffer.split('\n')
    // 最后一段可能是不完整的行，保留到下次读取
    buffer = lines.pop() ?? ''

    for (const line of lines) {
      if (!line.startsWith('data:')) continue
      const raw = line.slice(5).trimStart()
      if (!raw) continue
      // JSON 解析和 onEvent 调用分离：解析失败静默忽略（keepalive/[DONE] 等非 JSON 行），
      // 但 onEvent 内部抛出的异常（如 ChatPage 在 error 事件中抛出的 ChatError）必须穿透。
      let event: StreamEvent
      try {
        event = JSON.parse(raw) as StreamEvent
      } catch {
        continue
      }
      onEvent(event)
      // 让出一次事件循环，避免大量 SSE 行在同一个 tick 内批量触发 UI 更新。
      await new Promise(resolve => setTimeout(resolve, 0))
    }
  }
}
