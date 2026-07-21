import axios from 'axios'

import { http } from './http'
import type { APIResponse } from './types'

export type InternalTaskStatus =
  | 'PENDING'
  | 'RUNNING'
  | 'WAITING_REVIEW'
  | 'SUCCEEDED'
  | 'FAILED'
  | 'CANCELLED'

export interface ParsedDocumentBlock {
  id: string
  kind: string
  text: string
  order: number
  source_location?: {
    page_number?: number | null
  }
  metadata?: Record<string, unknown>
}

export interface ParsedDocumentSection {
  id: string
  title: string
  block_ids: string[]
}

export interface ParsedDocumentSnapshot {
  metadata?: Record<string, unknown>
  blocks?: ParsedDocumentBlock[]
  sections?: ParsedDocumentSection[]
  warnings?: Array<Record<string, unknown>>
}

export interface FileUploadPrepareResponse {
  upload_url: string
  method: string
  headers: Record<string, string>
  storage_uri: string
  bucket: string
  object_key: string
  original_filename: string
  file_type: string
  content_type: string
  expires_seconds: number
}

export interface FileParseTask {
  id: string
  owner_org_unit_id?: string | null
  created_by?: string | null
  api_key_id?: string | null
  source_uri: string
  original_filename?: string | null
  file_type: string
  reader_type?: string | null
  status: InternalTaskStatus
  result_snapshot?: ParsedDocumentSnapshot | null
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface UploadOperation {
  promise: Promise<void>
  cancel: () => void
}

export interface UploadFileOptions {
  onProgress?: (percent: number) => void
}

export interface RequestOptions {
  signal?: AbortSignal
}

export const DEFAULT_POLL_TIMEOUT_MS = 12 * 60 * 1000
export const DEFAULT_POLL_INITIAL_INTERVAL_MS = 1_500
export const DEFAULT_POLL_MAX_INTERVAL_MS = 5_000

export const terminalTaskStatuses = new Set<InternalTaskStatus>([
  'SUCCEEDED',
  'FAILED',
  'CANCELLED',
])

export function isTerminalTaskStatus(status: InternalTaskStatus): boolean {
  return terminalTaskStatuses.has(status)
}

export async function prepareFileUpload(
  file: File,
  options: RequestOptions = {},
): Promise<FileUploadPrepareResponse> {
  const { data } = await http.post<APIResponse<FileUploadPrepareResponse>>(
    '/internal/files/upload',
    {
      filename: file.name,
      content_type: file.type || undefined,
      file_size_bytes: file.size || undefined,
    },
    { signal: options.signal },
  )
  return data.data
}

export function uploadToPresignedUrl(
  upload: FileUploadPrepareResponse,
  file: File,
  options: UploadFileOptions = {},
): UploadOperation {
  const xhr = new XMLHttpRequest()
  let cancelled = false
  const promise = new Promise<void>((resolve, reject) => {
    xhr.open(upload.method || 'PUT', upload.upload_url, true)
    xhr.withCredentials = false
    for (const [name, value] of Object.entries(upload.headers || {})) {
      xhr.setRequestHeader(name, value)
    }
    xhr.upload.onprogress = (event) => {
      if (!event.lengthComputable) return
      options.onProgress?.(Math.min(100, Math.round((event.loaded / event.total) * 100)))
    }
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        options.onProgress?.(100)
        resolve()
        return
      }
      reject(new InternalFileApiError('对象上传失败，请检查文件或 MinIO CORS 配置。'))
    }
    xhr.onerror = () => reject(new InternalFileApiError('对象上传网络错误，请稍后重试。'))
    xhr.onabort = () => reject(new InternalFileApiError(
      cancelled ? '已停止等待文件上传。' : '文件上传已中断。',
      'ABORTED',
    ))
    xhr.send(file)
  })
  return {
    promise,
    cancel: () => {
      cancelled = true
      xhr.abort()
    },
  }
}

export async function createFileParseTask(
  sourceUri: string,
  originalFilename: string,
  options: RequestOptions = {},
): Promise<FileParseTask> {
  const { data } = await http.post<APIResponse<FileParseTask>>(
    '/internal/file-parse/tasks',
    { source_uri: sourceUri, original_filename: originalFilename },
    { signal: options.signal },
  )
  return data.data
}

export async function getFileParseTask(
  taskId: string,
  options: RequestOptions = {},
): Promise<FileParseTask> {
  const { data } = await http.get<APIResponse<FileParseTask>>(
    `/internal/file-parse/tasks/${encodeURIComponent(taskId)}`,
    { signal: options.signal },
  )
  return data.data
}

export class InternalFileApiError extends Error {
  constructor(message: string, public readonly code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'InternalFileApiError'
  }
}

export function toSafeInternalFileErrorMessage(error: unknown): string {
  if (error instanceof InternalFileApiError) return error.message
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') return '请求已停止。'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return '请求等待超时，请稍后重新查询任务。'
    }
    const responseMessage = readResponseMessage(error.response?.data)
    if (responseMessage) return responseMessage
  }
  return '请求未能完成，请检查网络或稍后重试。'
}

export function isUncertainRequestError(error: unknown): boolean {
  return axios.isAxiosError(error)
    && (!error.response || error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT')
}

function readResponseMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const message = (payload as { message?: unknown }).message
  return typeof message === 'string' && message.trim() ? message.trim() : null
}
