import axios from 'axios'

import { http } from './http'
import type { APIResponse } from './types'
import {
  createFileParseTask,
  getFileParseTask,
  prepareFileUpload,
  uploadToPresignedUrl,
} from './internalFiles'
import type {
  FileParseTask,
  FileUploadPrepareResponse,
  InternalTaskStatus,
  RequestOptions,
  UploadOperation,
} from './internalFiles'

export type RiskDocumentType =
  | 'PURCHASE_CONTRACT'
  | 'SALES_CONTRACT'
  | 'APPROVAL_FORM'
  | 'SETTLEMENT_STATEMENT'
export type RiskReviewTargetKind = 'FIELD' | 'DOCUMENT_TYPE'
export type BusinessOverviewStatus = 'READY' | 'PARTIAL' | 'MISSING' | 'NEEDS_REVIEW'

export interface BusinessOverviewRow {
  code: string
  label: string
  content: string
  status: BusinessOverviewStatus
  source_files: string[]
  field_codes: string[]
  is_human_reviewed: boolean
}

export interface BusinessOverviewProjection {
  business_code: string
  generated_at: string
  rows: BusinessOverviewRow[]
}

export interface RiskSource {
  source?: string
  document_id?: string
  original_filename?: string
  declared_document_type?: RiskDocumentType
  type_validation_status?: string
  type_validation_warnings?: string[]
  block_id?: string
  page_number?: number
  quote?: string
  bbox?: number[]
  review_event_id?: string
  [key: string]: unknown
}

export interface RiskAuditItem {
  field_code: string
  label: string
  value?: unknown
  normalized_value?: unknown
  raw_value?: unknown
  raw_values?: unknown[]
  unit?: string | null
  status: string
  alternatives?: unknown[]
  sources?: RiskSource[]
  critical?: boolean
  is_review_target?: boolean
  related_checks?: RiskCheck[]
  [key: string]: unknown
}

export interface RiskCheck {
  rule_code: string
  outcome: string
  message: string
  affected_fields?: string[]
  input_evidence?: Array<Record<string, unknown>>
  selected_value?: unknown
  version?: string
}

export interface RiskReviewItem {
  id: string
  target_kind: RiskReviewTargetKind
  target_code: string
  alternatives?: unknown[]
  sources?: RiskSource[]
  reason?: string
  original_filename?: string
  declared_document_type?: RiskDocumentType
  warning?: string
  is_resolved?: boolean
  [key: string]: unknown
}

export interface RiskResultSnapshot {
  schema_version?: string
  audit_items?: RiskAuditItem[]
  document_facts?: Record<string, Record<string, unknown>>
  checks?: RiskCheck[]
  warnings?: string[]
  review_items?: RiskReviewItem[]
  overall_status?: string
  documents?: RiskAssessmentDocument[]
  versions?: Record<string, unknown>
}

export interface RiskAssessmentDocument {
  id: string
  file_parse_task_id: string
  original_filename: string
  declared_document_type: RiskDocumentType
  document_order: number
  type_validation_status: string
  type_validation_warnings: string[]
}

export interface RiskReviewEvent {
  id: string
  review_item_id: string
  target_kind: RiskReviewTargetKind
  target_code: string
  before_value?: Record<string, unknown> | null
  alternatives: unknown[]
  after_value?: Record<string, unknown> | null
  action: string
  reason: string
  actor_user_id?: string | null
  sources: RiskSource[]
  checkpoint_version: number
  created_at: string
}

export interface RiskAssessmentTask {
  id: string
  owner_org_unit_id?: string | null
  created_by?: string | null
  status: InternalTaskStatus
  agent_code: string
  business_code: string
  graph_thread_id?: string | null
  checkpoint_version: number
  current_node?: string | null
  invocation_record_id?: string | null
  versions: Record<string, unknown>
  documents: RiskAssessmentDocument[]
  result?: RiskResultSnapshot | null
  review_context?: RiskResultSnapshot | null
  review_events: RiskReviewEvent[]
  business_overview?: BusinessOverviewProjection | null
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface RiskTaskSummary {
  id: string
  business_code: string
  status: InternalTaskStatus
  current_node?: string | null
  document_count: number
  error_message?: string | null
  created_at: string
  updated_at: string
  finished_at?: string | null
}

export interface RiskTaskPage {
  items: RiskTaskSummary[]
  total: number
  page: number
  page_size: number
}

export interface CreateRiskTaskPayload {
  agent_code?: string
  business_code: string
  documents: Array<{
    file_parse_task_id: string
    declared_document_type: RiskDocumentType
  }>
}

export interface RiskReviewSubmitPayload {
  review_item_id: string
  target_kind: RiskReviewTargetKind
  target_code: string
  action: 'SELECT_VALUE' | 'CORRECT_VALUE' | 'MARK_MISSING' | 'CONFIRM_DECLARED_TYPE'
  value?: unknown
  reason: string
  checkpoint_version: number
}

export interface RiskDocumentAccess {
  access_url: string
  method: string
  headers: Record<string, string>
  expires_seconds: number
  original_filename: string
  file_type: string
}

export interface RiskTaskListOptions extends RequestOptions {
  page?: number
  pageSize?: number
  status?: InternalTaskStatus | null
}

export interface RiskExecuteOptions extends RequestOptions {
  timeout?: number
  requestId?: string
}

export const DEFAULT_RISK_EXECUTE_TIMEOUT_MS = resolvePositiveNumber(
  import.meta.env.VITE_RISK_ASSISTANT_EXECUTE_TIMEOUT_MS,
  12 * 60 * 1000,
)

export async function listRiskTasks(options: RiskTaskListOptions = {}): Promise<RiskTaskPage> {
  const { data } = await http.get<APIResponse<RiskTaskPage>>('/internal/risk-assistant/tasks', {
    signal: options.signal,
    params: {
      page: options.page ?? 1,
      page_size: options.pageSize ?? 20,
      status: options.status || undefined,
    },
  })
  return data.data
}

export async function createRiskTask(
  payload: CreateRiskTaskPayload,
  options: RequestOptions = {},
): Promise<RiskAssessmentTask> {
  const { data } = await http.post<APIResponse<RiskAssessmentTask>>(
    '/internal/risk-assistant/tasks',
    payload,
    { signal: options.signal },
  )
  return data.data
}

export async function getRiskTask(
  taskId: string,
  options: RequestOptions = {},
): Promise<RiskAssessmentTask> {
  const { data } = await http.get<APIResponse<RiskAssessmentTask>>(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}`,
    { signal: options.signal },
  )
  return data.data
}

export async function executeRiskTask(
  taskId: string,
  options: RiskExecuteOptions = {},
): Promise<RiskAssessmentTask> {
  const { data } = await http.post<APIResponse<RiskAssessmentTask>>(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}/execute`,
    {},
    {
      signal: options.signal,
      timeout: options.timeout ?? DEFAULT_RISK_EXECUTE_TIMEOUT_MS,
      headers: options.requestId ? { 'X-Request-ID': options.requestId } : undefined,
    },
  )
  return data.data
}

export async function submitRiskReview(
  taskId: string,
  payload: RiskReviewSubmitPayload,
  options: RiskExecuteOptions = {},
): Promise<RiskAssessmentTask> {
  const { data } = await http.post<APIResponse<RiskAssessmentTask>>(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}/reviews`,
    payload,
    {
      signal: options.signal,
      timeout: options.timeout ?? DEFAULT_RISK_EXECUTE_TIMEOUT_MS,
      headers: options.requestId ? { 'X-Request-ID': options.requestId } : undefined,
    },
  )
  return data.data
}

export async function cancelRiskTask(
  taskId: string,
  options: RequestOptions = {},
): Promise<RiskAssessmentTask> {
  const { data } = await http.post<APIResponse<RiskAssessmentTask>>(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}/cancel`,
    {},
    { signal: options.signal },
  )
  return data.data
}

export async function getRiskDocumentAccess(
  taskId: string,
  documentId: string,
  options: RequestOptions = {},
): Promise<RiskDocumentAccess> {
  const { data } = await http.get<APIResponse<RiskDocumentAccess>>(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}`
      + `/documents/${encodeURIComponent(documentId)}/access`,
    { signal: options.signal },
  )
  return data.data
}

export async function exportRiskWorkbook(
  taskId: string,
  options: RequestOptions = {},
): Promise<Blob> {
  const response = await http.get(
    `/internal/risk-assistant/tasks/${encodeURIComponent(taskId)}/export`,
    { signal: options.signal, responseType: 'blob' },
  )
  return response.data as Blob
}

export interface RiskAssistantClient {
  prepareFileUpload: (file: File, options?: RequestOptions) => Promise<FileUploadPrepareResponse>
  uploadToPresignedUrl: typeof uploadToPresignedUrl
  createFileParseTask: typeof createFileParseTask
  getFileParseTask: typeof getFileParseTask
  listRiskTasks: typeof listRiskTasks
  createRiskTask: typeof createRiskTask
  getRiskTask: typeof getRiskTask
  executeRiskTask: typeof executeRiskTask
  submitRiskReview: typeof submitRiskReview
  cancelRiskTask: typeof cancelRiskTask
  getRiskDocumentAccess: typeof getRiskDocumentAccess
  exportRiskWorkbook: typeof exportRiskWorkbook
}

export const riskAssistantClient: RiskAssistantClient = {
  prepareFileUpload,
  uploadToPresignedUrl,
  createFileParseTask,
  getFileParseTask,
  listRiskTasks,
  createRiskTask,
  getRiskTask,
  executeRiskTask,
  submitRiskReview,
  cancelRiskTask,
  getRiskDocumentAccess,
  exportRiskWorkbook,
}

export class RiskAssistantApiError extends Error {
  constructor(message: string, public readonly code = 'REQUEST_FAILED') {
    super(message)
    this.name = 'RiskAssistantApiError'
  }
}

export function toSafeRiskAssistantError(error: unknown): string {
  if (error instanceof RiskAssistantApiError) return error.message
  if (axios.isAxiosError(error)) {
    if (error.code === 'ERR_CANCELED') return '请求已停止。'
    if (error.response?.status === 409) return '任务状态已变化，请刷新后重试。'
    if (error.response?.status === 403) return '你没有权限访问该风控任务。'
    const message = readResponseMessage(error.response?.data)
    if (message) return message
    if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') {
      return '请求等待超时，正在确认风控任务状态。'
    }
  }
  return '请求未能完成，请检查网络或稍后重试。'
}

export function isUncertainRiskExecutionError(error: unknown): boolean {
  return axios.isAxiosError(error)
    && (!error.response || error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT')
}

export function isRiskCheckpointConflict(error: unknown): boolean {
  return axios.isAxiosError(error) && error.response?.status === 409
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

export type { FileParseTask, InternalTaskStatus, UploadOperation }
