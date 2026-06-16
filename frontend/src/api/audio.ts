import { http } from './http'
import type { APIResponse } from './types'
import { isEmbedSessionActive } from '../utils/embedAuth'

export interface AudioTranscriptionResult {
  text: string
  provider: string
  request_id?: string
  log_id?: string
  metadata: Record<string, unknown>
}

export async function transcribeAudio(file: Blob): Promise<AudioTranscriptionResult> {
  const form = new FormData()
  form.append('file', file, 'speech.wav')
  const { data } = await http.post<APIResponse<AudioTranscriptionResult>>(
    '/audio/transcriptions',
    form,
    {
      timeout: 120000,
    },
  )
  return data.data
}

export async function requestSpeechAudio(
  text: string,
  voice?: string,
  signal?: AbortSignal,
): Promise<Response> {
  const response = await fetch('/api/v1/audio/speech', {
    method: 'POST',
    credentials: 'include',
    headers: {
      'Content-Type': 'application/json',
      ...(isEmbedSessionActive() ? { 'X-AgentHub-Embed': 'true' } : {}),
    },
    body: JSON.stringify({ text, voice }),
    signal,
  })

  if (!response.ok) {
    let message = `HTTP ${response.status}`
    try {
      const body = await response.json()
      message = body.message || body.detail || message
    } catch {
      // Keep default message.
    }
    throw new Error(message)
  }

  return response
}

export async function fetchSpeechAudio(
  text: string,
  voice?: string,
  signal?: AbortSignal,
): Promise<Blob> {
  const response = await requestSpeechAudio(text, voice, signal)

  if (!response.body) {
    throw new Error('语音合成响应为空')
  }

  const reader = response.body.getReader()
  const chunks: ArrayBuffer[] = []
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    if (value) {
      chunks.push(value.buffer.slice(value.byteOffset, value.byteOffset + value.byteLength))
    }
  }
  return new Blob(chunks, { type: response.headers.get('content-type') || 'audio/mpeg' })
}
