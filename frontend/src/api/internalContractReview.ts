import axios from 'axios'

import { http } from './http'
import {
  InternalFileApiError,
  createFileParseTask,
  getFileParseTask,
  isTerminalTaskStatus,
  isUncertainRequestError,
  prepareFileUpload,
  uploadToPresignedUrl,
  DEFAULT_POLL_INITIAL_INTERVAL_MS,
  DEFAULT_POLL_MAX_INTERVAL_MS,
  DEFAULT_POLL_TIMEOUT_MS,
} from './internalFiles'
import type {
  FileParseTask,
  FileUploadPrepareResponse,
  InternalTaskStatus,
  ParsedDocumentBlock,
  ParsedDocumentSection,
  ParsedDocumentSnapshot,
  RequestOptions,
  UploadFileOptions,
  UploadOperation,
} from './internalFiles'
import type { APIResponse } from './types'

export type {
  FileParseTask,
  FileUploadPrepareResponse,
  InternalTaskStatus,
  ParsedDocumentBlock,
  ParsedDocumentSection,
  ParsedDocumentSnapshot,
  RequestOptions,
  UploadFileOptions,
  UploadOperation,
}
export {
  createFileParseTask,
  getFileParseTask,
  isTerminalTaskStatus,
  prepareFileUpload,
  uploadToPresignedUrl,
  DEFAULT_POLL_INITIAL_INTERVAL_MS,
  DEFAULT_POLL_MAX_INTERVAL_MS,
  DEFAULT_POLL_TIMEOUT_MS,
}

export type ContractType = 'warehouse' | 'transport'
export type CounterpartyLevel = 'A1' | 'A2' | 'A3' | 'A4' | 'A5' | 'A6' | 'A7'
export type ContractReviewTaskStatus = Exclude<InternalTaskStatus, 'WAITING_REVIEW'>

export interface ReviewWarning {
  code?: string
  message?: string
  severity?: string
  block_id?: string | null
  [key: string]: unknown
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
  status: ContractReviewTaskStatus
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

export interface ContractReviewTaskSummary {
  id: string
  original_filename?: string | null
  status: ContractReviewTaskStatus
  contract_type: ContractType
  counterparty_level: CounterpartyLevel
  total_clause_count: number
  sensitive_clause_count: number
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface ContractReviewTaskPage {
  items: ContractReviewTaskSummary[]
  total: number
  page: number
  page_size: number
}

export interface ContractReviewTaskDeleteResult {
  id: string
  deleted_at: string
}

export interface ListContractReviewTasksOptions extends RequestOptions {
  page?: number
  pageSize?: number
  status?: ContractReviewTaskStatus | null
  contractType?: ContractType | null
  keyword?: string | null
}

export interface CreateContractReviewTaskPayload {
  agent_code?: string
  file_parse_task_id: string
  contract_type: ContractType
  counterparty_level: CounterpartyLevel
  rule_set_version?: string
  callback_metadata?: Record<string, unknown>
}

export interface ExecuteOptions extends RequestOptions {
  timeout?: number
}

export const DEFAULT_EXECUTE_TIMEOUT_MS = resolvePositiveNumber(
  import.meta.env.VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS,
  10 * 60 * 1000,
)

export async function listContractReviewTasks(
  options: ListContractReviewTasksOptions = {},
): Promise<ContractReviewTaskPage> {
  const keyword = options.keyword?.trim()
  const { data } = await http.get<APIResponse<ContractReviewTaskPage>>(
    '/internal/contract-review/tasks',
    {
      signal: options.signal,
      params: {
        page: options.page ?? 1,
        page_size: options.pageSize ?? 20,
        ...(options.status ? { status: options.status } : {}),
        ...(options.contractType ? { contract_type: options.contractType } : {}),
        ...(keyword ? { keyword } : {}),
      },
    },
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

export async function deleteContractReviewTask(
  taskId: string,
  options: RequestOptions = {},
): Promise<ContractReviewTaskDeleteResult> {
  const { data } = await http.delete<APIResponse<ContractReviewTaskDeleteResult>>(
    `/internal/contract-review/tasks/${encodeURIComponent(taskId)}`,
    { signal: options.signal },
  )
  return data.data
}

export interface ContractReviewClient {
  prepareFileUpload: typeof prepareFileUpload
  uploadToPresignedUrl: typeof uploadToPresignedUrl
  createFileParseTask: typeof createFileParseTask
  getFileParseTask: typeof getFileParseTask
  listContractReviewTasks: typeof listContractReviewTasks
  createContractReviewTask: typeof createContractReviewTask
  getContractReviewTask: typeof getContractReviewTask
  executeContractReviewTask: typeof executeContractReviewTask
  deleteContractReviewTask: typeof deleteContractReviewTask
}

export const contractReviewClient: ContractReviewClient = {
  prepareFileUpload,
  uploadToPresignedUrl,
  createFileParseTask,
  getFileParseTask,
  listContractReviewTasks,
  createContractReviewTask,
  getContractReviewTask,
  executeContractReviewTask,
  deleteContractReviewTask,
}

export class ContractReviewApiError extends Error {
  constructor(message: string, public readonly code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'ContractReviewApiError'
  }
}

export function toSafeContractReviewErrorMessage(error: unknown): string {
  if (error instanceof ContractReviewApiError || error instanceof InternalFileApiError) {
    return error.message
  }
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') return '请求已停止。'
    if (error.response?.status === 409) return '任务状态已变化，当前操作无法完成，请刷新后重试。'
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return '请求等待超时，正在确认合同审查任务状态。'
    }
    const responseMessage = readResponseMessage(error.response?.data)
    if (responseMessage) return responseMessage
  }
  return '请求未能完成，请检查网络或稍后重试。'
}

export function isUncertainExecutionError(error: unknown): boolean {
  return isUncertainRequestError(error)
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
