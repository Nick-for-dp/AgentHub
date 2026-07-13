import axios from 'axios'

import { http } from './http'
import type { APIResponse } from './types'

export type ContractType = 'warehouse' | 'transport'
export type CounterpartyLevel = 'A1' | 'A2' | 'A3' | 'A4' | 'A5' | 'A6' | 'A7'
export type InternalTaskStatus = 'PENDING' | 'RUNNING' | 'SUCCEEDED' | 'FAILED' | 'CANCELLED'

export interface ReviewWarning {
  code?: string
  message?: string
  severity?: string
  block_id?: string | null
  [key: string]: unknown
}

export interface ParsedDocumentBlock {
  id: string
  kind: string
  text: string
  order: number
  source_location?: {
    page_number?: number | null
  }
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
  warnings?: ReviewWarning[]
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
  file_type: string
  reader_type?: string | null
  status: InternalTaskStatus
  result_snapshot?: ParsedDocumentSnapshot | null
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface ContractClauseSource {
  section_id?: string | null
  section_title?: string | null
  block_id?: string | null
  page_number?: number | null
  text_offset?: number | null
}

export interface ContractClauseSourceSpan {
  block_id: string
  section_id?: string | null
  section_title?: string | null
  start_offset: number
  end_offset: number
  matched_text: string
}

export interface ContractClauseReviewResult {
  text: string
  category: string
  matrix_clause?: string | null
  source: ContractClauseSource
  source_block_ids: string[]
  source_spans: ContractClauseSourceSpan[]
  is_sensitive: boolean
  risk_level: string
  matched_rules: string[]
  reason: string
  confidence: number
  warnings: ReviewWarning[]
}

export interface ContractReviewSummary {
  total_clause_count: number
  sensitive_clause_count: number
  highest_risk_level?: string | null
  warning_count: number
}

export interface ContractReviewResult {
  clauses: ContractClauseReviewResult[]
  summary: ContractReviewSummary
  warnings: ReviewWarning[]
}

export interface ContractReviewTask {
  id: string
  owner_org_unit_id?: string | null
  created_by?: string | null
  api_key_id?: string | null
  status: InternalTaskStatus
  agent_code: string
  file_parse_task_id: string
  contract_type: ContractType
  counterparty_level: CounterpartyLevel
  rule_set_version?: string | null
  callback_metadata: Record<string, unknown>
  invocation_record_id?: string | null
  result?: ContractReviewResult | null
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface CreateContractReviewTaskPayload {
  agent_code?: string
  file_parse_task_id: string
  contract_type: ContractType
  counterparty_level: CounterpartyLevel
  rule_set_version?: string
  callback_metadata?: Record<string, unknown>
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

export interface ExecuteOptions extends RequestOptions {
  timeout?: number
}

export const DEFAULT_EXECUTE_TIMEOUT_MS = resolvePositiveNumber(
  import.meta.env.VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS,
  10 * 60 * 1000,
)

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
      reject(new ContractReviewApiError('对象上传失败，请检查文件或 MinIO CORS 配置。'))
    }
    xhr.onerror = () => reject(new ContractReviewApiError('对象上传网络错误，请稍后重试。'))
    xhr.onabort = () => {
      reject(new ContractReviewApiError(cancelled ? '已停止等待文件上传。' : '文件上传已中断。', 'ABORTED'))
    }
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
  options: RequestOptions = {},
): Promise<FileParseTask> {
  const { data } = await http.post<APIResponse<FileParseTask>>(
    '/internal/file-parse/tasks',
    { source_uri: sourceUri },
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

export async function createContractReviewTask(
  payload: CreateContractReviewTaskPayload,
  options: RequestOptions = {},
): Promise<ContractReviewTask> {
  const { data } = await http.post<APIResponse<ContractReviewTask>>(
    '/internal/contract-review/tasks',
    payload,
    { signal: options.signal },
  )
  return data.data
}

export async function getContractReviewTask(
  taskId: string,
  options: RequestOptions = {},
): Promise<ContractReviewTask> {
  const { data } = await http.get<APIResponse<ContractReviewTask>>(
    `/internal/contract-review/tasks/${encodeURIComponent(taskId)}`,
    { signal: options.signal },
  )
  return data.data
}

export async function executeContractReviewTask(
  taskId: string,
  options: ExecuteOptions = {},
): Promise<ContractReviewTask> {
  const { data } = await http.post<APIResponse<ContractReviewTask>>(
    `/internal/contract-review/tasks/${encodeURIComponent(taskId)}/execute`,
    {},
    {
      signal: options.signal,
      timeout: options.timeout ?? DEFAULT_EXECUTE_TIMEOUT_MS,
    },
  )
  return data.data
}

export interface ContractReviewClient {
  prepareFileUpload: typeof prepareFileUpload
  uploadToPresignedUrl: typeof uploadToPresignedUrl
  createFileParseTask: typeof createFileParseTask
  getFileParseTask: typeof getFileParseTask
  createContractReviewTask: typeof createContractReviewTask
  getContractReviewTask: typeof getContractReviewTask
  executeContractReviewTask: typeof executeContractReviewTask
}

export const contractReviewClient: ContractReviewClient = {
  prepareFileUpload,
  uploadToPresignedUrl,
  createFileParseTask,
  getFileParseTask,
  createContractReviewTask,
  getContractReviewTask,
  executeContractReviewTask,
}

export class ContractReviewApiError extends Error {
  constructor(message: string, public readonly code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'ContractReviewApiError'
  }
}

export function toSafeContractReviewErrorMessage(error: unknown): string {
  if (error instanceof ContractReviewApiError) return error.message
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') return '请求已停止。'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return '请求等待超时，正在确认合同审查任务状态。'
    }
    const responseMessage = readResponseMessage(error.response?.data)
    if (responseMessage) return responseMessage
  }
  return '请求未能完成，请检查网络或稍后重试。'
}

export function isUncertainExecutionError(error: unknown): boolean {
  if (axios.isAxiosError(error)) {
    return !error.response || error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT'
  }
  return false
}

function readResponseMessage(payload: unknown): string | null {
  if (!payload || typeof payload !== 'object') return null
  const message = (payload as { message?: unknown }).message
  return typeof message === 'string' && message.trim() ? message.trim() : null
}

function resolvePositiveNumber(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : fallback
}
