import { computed, getCurrentInstance, onBeforeUnmount, ref } from 'vue'

import {
  type FileParseTask,
  type InternalTaskStatus,
  type UploadOperation,
  DEFAULT_POLL_INITIAL_INTERVAL_MS,
  DEFAULT_POLL_MAX_INTERVAL_MS,
  DEFAULT_POLL_TIMEOUT_MS,
  isTerminalTaskStatus,
  toSafeInternalFileErrorMessage,
} from '../api/internalFiles'
import {
  type RiskAssessmentTask,
  type RiskAssistantClient,
  type RiskDocumentType,
  type RiskReviewItem,
  type RiskReviewSubmitPayload,
  type RiskTaskSummary,
  isRiskCheckpointConflict,
  isUncertainRiskExecutionError,
  riskAssistantClient,
  toSafeRiskAssistantError,
} from '../api/internalRiskAssistant'

export type RiskFilePhase =
  | 'SELECTED'
  | 'PREPARING_UPLOAD'
  | 'UPLOADING'
  | 'PARSING'
  | 'READY'
  | 'FAILED'

export type RiskWorkbenchOperation =
  | 'IDLE'
  | 'CREATING'
  | 'LOADING_TASK'
  | 'EXECUTING'
  | 'POLLING'
  | 'REVIEWING'
  | 'CANCELLING'
  | 'OPENING_SOURCE'
  | 'EXPORTING'

export interface RiskFilePackageItem {
  id: string
  file: File
  declaredDocumentType: RiskDocumentType | null
  phase: RiskFilePhase
  progress: number
  parseTaskId: string | null
  errorMessage: string | null
  operationVersion: number
}

export interface RiskTaskListState {
  items: RiskTaskSummary[]
  total: number
  page: number
  pageSize: number
  status: InternalTaskStatus | null
  loading: boolean
  errorMessage: string | null
}

export interface RiskReviewDecision {
  action: RiskReviewSubmitPayload['action']
  value?: unknown
  reason: string
}

export interface RiskWorkbenchOptions {
  client?: RiskAssistantClient
  pollTimeoutMs?: number
  pollInitialIntervalMs?: number
  pollMaxIntervalMs?: number
  now?: () => number
  createRequestId?: () => string
  openExternal?: (url: string) => void
  downloadBlob?: (blob: Blob, filename: string) => void
}

const SUPPORTED_FILE_PATTERN = /\.(pdf|docx)$/i
const REVIEW_BOUNDARY_STATUSES = new Set<InternalTaskStatus>([
  'WAITING_REVIEW',
  'SUCCEEDED',
  'FAILED',
  'CANCELLED',
])

export function useRiskAssistantWorkbench(options: RiskWorkbenchOptions = {}) {
  const client = options.client ?? riskAssistantClient
  const now = options.now ?? Date.now
  const pollTimeoutMs = options.pollTimeoutMs ?? DEFAULT_POLL_TIMEOUT_MS
  const pollInitialIntervalMs = options.pollInitialIntervalMs ?? DEFAULT_POLL_INITIAL_INTERVAL_MS
  const pollMaxIntervalMs = options.pollMaxIntervalMs ?? DEFAULT_POLL_MAX_INTERVAL_MS
  const createRequestId = options.createRequestId ?? defaultRequestId
  const openExternal = options.openExternal ?? ((url) => window.open(url, '_blank', 'noopener,noreferrer'))
  const downloadBlob = options.downloadBlob ?? triggerBlobDownload

  const businessCode = ref('')
  const files = ref<RiskFilePackageItem[]>([])
  const packageErrorMessage = ref<string | null>(null)
  const selectedTask = ref<RiskAssessmentTask | null>(null)
  const detailErrorMessage = ref<string | null>(null)
  const operation = ref<RiskWorkbenchOperation>('IDLE')
  const canRetryExecuteAfterUncertain = ref(false)
  const checkpointConflictMessage = ref<string | null>(null)
  const taskList = ref<RiskTaskListState>({
    items: [],
    total: 0,
    page: 1,
    pageSize: 20,
    status: null,
    loading: false,
    errorMessage: null,
  })

  let fileSequence = 0
  let detailRunId = 0
  let listRunId = 0
  let detailController: AbortController | null = null
  let listController: AbortController | null = null
  const fileControllers = new Map<string, AbortController>()
  const uploadOperations = new Map<string, UploadOperation>()

  const isTaskBusy = computed(() => operation.value !== 'IDLE')
  const allFilesReady = computed(() => (
    files.value.length > 0 && files.value.every((item) => item.phase === 'READY')
  ))
  const canCreateTask = computed(() => (
    businessCode.value.trim().length > 0
    && allFilesReady.value
    && files.value.every((item) => item.declaredDocumentType !== null)
    && !isTaskBusy.value
  ))
  const canRetryExecute = computed(() => (
    canRetryExecuteAfterUncertain.value
    && selectedTask.value?.status === 'PENDING'
    && !isTaskBusy.value
  ))
  const activeReviewItem = computed<RiskReviewItem | null>(() => {
    if (selectedTask.value?.status !== 'WAITING_REVIEW') return null
    const snapshot = selectedTask.value.review_context ?? selectedTask.value.result
    return snapshot?.review_items?.find((item) => !item.is_resolved) ?? null
  })
  const auditItems = computed(() => (
    selectedTask.value?.review_context?.audit_items
    ?? selectedTask.value?.result?.audit_items
    ?? []
  ))
  const checks = computed(() => (
    selectedTask.value?.review_context?.checks
    ?? selectedTask.value?.result?.checks
    ?? []
  ))
  const warnings = computed(() => (
    selectedTask.value?.review_context?.warnings
    ?? selectedTask.value?.result?.warnings
    ?? []
  ))

  async function addFiles(selectedFiles: File[]): Promise<void> {
    packageErrorMessage.value = null
    const additions = selectedFiles.map((file) => {
      const item: RiskFilePackageItem = {
        id: `risk-file-${++fileSequence}`,
        file,
        declaredDocumentType: null,
        phase: 'SELECTED',
        progress: 0,
        parseTaskId: null,
        errorMessage: null,
        operationVersion: 0,
      }
      files.value.push(item)
      return processFile(item.id)
    })
    await Promise.all(additions)
  }

  function setDeclaredDocumentType(fileId: string, value: RiskDocumentType | null): void {
    const item = findFile(fileId)
    if (item) item.declaredDocumentType = value
  }

  function removeFile(fileId: string): void {
    cancelFileOperation(fileId)
    files.value = files.value.filter((item) => item.id !== fileId)
  }

  async function retryFile(fileId: string): Promise<boolean> {
    const item = findFile(fileId)
    if (!item || item.phase !== 'FAILED') return false
    return processFile(fileId)
  }

  async function processFile(fileId: string): Promise<boolean> {
    const item = findFile(fileId)
    if (!item) return false
    cancelFileOperation(fileId)
    item.operationVersion += 1
    const operationVersion = item.operationVersion
    item.progress = 0
    item.parseTaskId = null
    item.errorMessage = null

    if (!SUPPORTED_FILE_PATTERN.test(item.file.name)) {
      item.phase = 'FAILED'
      item.errorMessage = '仅支持 PDF 或 DOCX 文件。'
      return false
    }

    const controller = new AbortController()
    fileControllers.set(fileId, controller)
    try {
      item.phase = 'PREPARING_UPLOAD'
      const upload = await client.prepareFileUpload(item.file, { signal: controller.signal })
      ensureCurrentFile(fileId, operationVersion)

      item.phase = 'UPLOADING'
      const uploadOperation = client.uploadToPresignedUrl(upload, item.file, {
        onProgress: (percent) => {
          const current = findFile(fileId)
          if (current?.operationVersion === operationVersion) current.progress = percent
        },
      })
      uploadOperations.set(fileId, uploadOperation)
      await uploadOperation.promise
      ensureCurrentFile(fileId, operationVersion)
      uploadOperations.delete(fileId)

      item.phase = 'PARSING'
      let parseTask = await client.createFileParseTask(
        upload.storage_uri,
        upload.original_filename,
        { signal: controller.signal },
      )
      ensureCurrentFile(fileId, operationVersion)
      parseTask = await pollFileParse(parseTask, fileId, operationVersion, controller.signal)
      ensureCurrentFile(fileId, operationVersion)
      if (parseTask.status !== 'SUCCEEDED') {
        throw new RiskWorkbenchError(
          parseTask.error_message?.trim() || '文件解析未能成功完成。',
        )
      }
      item.parseTaskId = parseTask.id
      item.phase = 'READY'
      item.progress = 100
      return true
    } catch (error) {
      const current = findFile(fileId)
      if (!current || current.operationVersion !== operationVersion) return false
      current.phase = 'FAILED'
      current.errorMessage = error instanceof RiskWorkbenchError
        ? error.message
        : toSafeInternalFileErrorMessage(error)
      return false
    } finally {
      if (findFile(fileId)?.operationVersion === operationVersion) {
        fileControllers.delete(fileId)
        uploadOperations.delete(fileId)
      }
    }
  }

  async function createAndExecuteTask(): Promise<boolean> {
    const validationMessage = validateTaskPackage()
    if (validationMessage) {
      packageErrorMessage.value = validationMessage
      return false
    }
    const currentRunId = beginDetailRun('CREATING')
    packageErrorMessage.value = null
    detailErrorMessage.value = null
    checkpointConflictMessage.value = null
    canRetryExecuteAfterUncertain.value = false
    try {
      const task = await client.createRiskTask({
        agent_code: 'risk-assistant',
        business_code: businessCode.value.trim(),
        documents: files.value.map((item) => ({
          file_parse_task_id: item.parseTaskId as string,
          declared_document_type: item.declaredDocumentType as RiskDocumentType,
        })),
      }, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      updateSelectedTask(task)
      return await executeAndResolve(task, currentRunId)
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function retryExecute(): Promise<boolean> {
    const task = selectedTask.value
    if (!task || !canRetryExecute.value) return false
    const currentRunId = beginDetailRun('EXECUTING')
    detailErrorMessage.value = null
    canRetryExecuteAfterUncertain.value = false
    try {
      return await executeAndResolve(task, currentRunId)
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function executeAndResolve(task: RiskAssessmentTask, currentRunId: number): Promise<boolean> {
    operation.value = 'EXECUTING'
    let current: RiskAssessmentTask
    try {
      current = await client.executeRiskTask(task.id, {
        signal: detailController?.signal,
        requestId: createRequestId(),
      })
      ensureCurrentDetail(currentRunId)
    } catch (error) {
      ensureCurrentDetail(currentRunId)
      if (!isUncertainRiskExecutionError(error)) throw error
      current = await client.getRiskTask(task.id, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      updateSelectedTask(current)
      if (current.status === 'PENDING') {
        canRetryExecuteAfterUncertain.value = true
        throw new RiskWorkbenchError(
          '未能确认执行请求是否已接收。已确认任务仍待执行，可安全重试。',
        )
      }
    }
    updateSelectedTask(current)
    current = await pollTaskToBoundary(current, currentRunId)
    updateSelectedTask(current)
    finishDetailRun(currentRunId)
    return current.status === 'SUCCEEDED' || current.status === 'WAITING_REVIEW'
  }

  async function loadTaskList(params: {
    page?: number
    pageSize?: number
    status?: InternalTaskStatus | null
  } = {}): Promise<boolean> {
    listRunId += 1
    const currentRunId = listRunId
    listController?.abort()
    listController = new AbortController()
    const page = params.page ?? taskList.value.page
    const pageSize = params.pageSize ?? taskList.value.pageSize
    const status = params.status === undefined ? taskList.value.status : params.status
    taskList.value.loading = true
    taskList.value.errorMessage = null
    try {
      const result = await client.listRiskTasks({
        page,
        pageSize,
        status,
        signal: listController.signal,
      })
      if (currentRunId !== listRunId) return false
      taskList.value = {
        items: result.items,
        total: result.total,
        page: result.page,
        pageSize: result.page_size,
        status,
        loading: false,
        errorMessage: null,
      }
      return true
    } catch (error) {
      if (currentRunId !== listRunId) return false
      taskList.value.loading = false
      taskList.value.errorMessage = toSafeRiskAssistantError(error)
      return false
    } finally {
      if (currentRunId === listRunId) listController = null
    }
  }

  async function loadTask(taskId: string, autoPoll = true): Promise<boolean> {
    const currentRunId = beginDetailRun('LOADING_TASK')
    detailErrorMessage.value = null
    checkpointConflictMessage.value = null
    canRetryExecuteAfterUncertain.value = false
    try {
      let task = await client.getRiskTask(taskId, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      updateSelectedTask(task)
      if (autoPoll && task.status === 'RUNNING') {
        task = await pollTaskToBoundary(task, currentRunId)
        updateSelectedTask(task)
      }
      finishDetailRun(currentRunId)
      return true
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function refreshSelectedTask(): Promise<boolean> {
    return selectedTask.value ? loadTask(selectedTask.value.id) : false
  }

  async function submitReview(decision: RiskReviewDecision): Promise<boolean> {
    const task = selectedTask.value
    const reviewItem = activeReviewItem.value
    if (!task || !reviewItem || task.status !== 'WAITING_REVIEW' || isTaskBusy.value) return false
    if (!decision.reason.trim()) {
      detailErrorMessage.value = '请填写复核理由。'
      return false
    }
    if (decision.action !== 'MARK_MISSING'
      && decision.action !== 'CONFIRM_DECLARED_TYPE'
      && (decision.value === undefined || decision.value === null || decision.value === '')) {
      detailErrorMessage.value = '请选择或输入复核后的值。'
      return false
    }

    const currentRunId = beginDetailRun('REVIEWING')
    detailErrorMessage.value = null
    checkpointConflictMessage.value = null
    const payload: RiskReviewSubmitPayload = {
      review_item_id: reviewItem.id,
      target_kind: reviewItem.target_kind,
      target_code: reviewItem.target_code,
      action: decision.action,
      value: decision.value,
      reason: decision.reason.trim(),
      checkpoint_version: task.checkpoint_version,
    }
    try {
      let current: RiskAssessmentTask
      try {
        current = await client.submitRiskReview(task.id, payload, {
          signal: detailController?.signal,
          requestId: createRequestId(),
        })
        ensureCurrentDetail(currentRunId)
      } catch (error) {
        ensureCurrentDetail(currentRunId)
        if (isRiskCheckpointConflict(error)) {
          checkpointConflictMessage.value = '该复核节点已更新，已刷新最新任务，请重新确认。'
          current = await client.getRiskTask(task.id, { signal: detailController?.signal })
          ensureCurrentDetail(currentRunId)
          updateSelectedTask(current)
          finishDetailRun(currentRunId)
          return false
        }
        if (!isUncertainRiskExecutionError(error)) throw error
        current = await client.getRiskTask(task.id, { signal: detailController?.signal })
        ensureCurrentDetail(currentRunId)
        updateSelectedTask(current)
        if (current.status === 'WAITING_REVIEW'
          && current.checkpoint_version === task.checkpoint_version) {
          throw new RiskWorkbenchError(
            '未能确认复核请求是否已接收。已刷新最新任务，请核对后再操作。',
          )
        }
      }
      updateSelectedTask(current)
      current = await pollTaskToBoundary(current, currentRunId)
      updateSelectedTask(current)
      finishDetailRun(currentRunId)
      return true
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function cancelSelectedTask(): Promise<boolean> {
    const task = selectedTask.value
    if (!task || isTerminalTaskStatus(task.status) || isTaskBusy.value) return false
    const currentRunId = beginDetailRun('CANCELLING')
    detailErrorMessage.value = null
    try {
      const cancelled = await client.cancelRiskTask(task.id, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      updateSelectedTask(cancelled)
      finishDetailRun(currentRunId)
      return true
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function openSourceDocument(documentId: string): Promise<boolean> {
    const task = selectedTask.value
    if (!task || isTaskBusy.value) return false
    const currentRunId = beginDetailRun('OPENING_SOURCE')
    detailErrorMessage.value = null
    try {
      const access = await client.getRiskDocumentAccess(task.id, documentId, {
        signal: detailController?.signal,
      })
      ensureCurrentDetail(currentRunId)
      openExternal(access.access_url)
      finishDetailRun(currentRunId)
      return true
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  async function exportSelectedTask(): Promise<boolean> {
    const task = selectedTask.value
    if (!task || task.status !== 'SUCCEEDED' || isTaskBusy.value) return false
    const currentRunId = beginDetailRun('EXPORTING')
    detailErrorMessage.value = null
    try {
      const blob = await client.exportRiskWorkbook(task.id, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      downloadBlob(blob, `供应链业务核对审计底稿_${sanitizeFilename(task.business_code)}.xlsx`)
      finishDetailRun(currentRunId)
      return true
    } catch (error) {
      handleDetailError(error, currentRunId)
      return false
    }
  }

  function resetPackage(): void {
    for (const fileId of fileControllers.keys()) cancelFileOperation(fileId)
    files.value = []
    businessCode.value = ''
    packageErrorMessage.value = null
  }

  function clearSelectedTask(): void {
    detailRunId += 1
    detailController?.abort()
    detailController = null
    selectedTask.value = null
    detailErrorMessage.value = null
    checkpointConflictMessage.value = null
    canRetryExecuteAfterUncertain.value = false
    operation.value = 'IDLE'
  }

  async function pollFileParse(
    initial: FileParseTask,
    fileId: string,
    operationVersion: number,
    signal: AbortSignal,
  ): Promise<FileParseTask> {
    let current = initial
    let delay = pollInitialIntervalMs
    const deadline = now() + pollTimeoutMs
    while (!isTerminalTaskStatus(current.status)) {
      ensureCurrentFile(fileId, operationVersion)
      if (now() >= deadline) throw new RiskWorkbenchError('文件仍在解析，已停止等待，可稍后重试。')
      await abortableDelay(delay, signal)
      ensureCurrentFile(fileId, operationVersion)
      current = await client.getFileParseTask(current.id, { signal })
      delay = nextPollDelay(delay, pollMaxIntervalMs)
    }
    return current
  }

  async function pollTaskToBoundary(
    initial: RiskAssessmentTask,
    currentRunId: number,
  ): Promise<RiskAssessmentTask> {
    if (REVIEW_BOUNDARY_STATUSES.has(initial.status)) return initial
    operation.value = 'POLLING'
    let current = initial
    let delay = pollInitialIntervalMs
    const deadline = now() + pollTimeoutMs
    while (!REVIEW_BOUNDARY_STATUSES.has(current.status)) {
      ensureCurrentDetail(currentRunId)
      if (now() >= deadline) {
        throw new RiskWorkbenchError('任务仍在处理中，已停止自动等待。可稍后刷新该任务。')
      }
      await abortableDelay(delay, detailController?.signal)
      ensureCurrentDetail(currentRunId)
      current = await client.getRiskTask(current.id, { signal: detailController?.signal })
      ensureCurrentDetail(currentRunId)
      updateSelectedTask(current)
      delay = nextPollDelay(delay, pollMaxIntervalMs)
    }
    return current
  }

  function validateTaskPackage(): string | null {
    if (!businessCode.value.trim()) return '请填写业务编号。'
    if (files.value.length === 0) return '请选择供应链业务文件。'
    if (files.value.some((item) => item.phase !== 'READY')) return '请等待所有文件解析成功。'
    if (files.value.some((item) => !item.declaredDocumentType)) return '请为每份文件选择声明类型。'
    return null
  }

  function beginDetailRun(nextOperation: RiskWorkbenchOperation): number {
    detailRunId += 1
    detailController?.abort()
    detailController = new AbortController()
    operation.value = nextOperation
    return detailRunId
  }

  function finishDetailRun(currentRunId: number): void {
    if (currentRunId !== detailRunId) return
    operation.value = 'IDLE'
    detailController = null
  }

  function handleDetailError(error: unknown, currentRunId: number): void {
    if (currentRunId !== detailRunId) return
    detailErrorMessage.value = error instanceof RiskWorkbenchError
      ? error.message
      : toSafeRiskAssistantError(error)
    finishDetailRun(currentRunId)
  }

  function updateSelectedTask(task: RiskAssessmentTask): void {
    selectedTask.value = task
    const summary = toTaskSummary(task)
    const index = taskList.value.items.findIndex((item) => item.id === task.id)
    if (index >= 0) taskList.value.items[index] = summary
    else taskList.value.items.unshift(summary)
  }

  function ensureCurrentDetail(currentRunId: number): void {
    if (currentRunId !== detailRunId) throw new RiskWorkbenchError('任务请求已过期。', 'STALE_RUN')
  }

  function ensureCurrentFile(fileId: string, operationVersion: number): void {
    if (findFile(fileId)?.operationVersion !== operationVersion) {
      throw new RiskWorkbenchError('文件请求已过期。', 'STALE_RUN')
    }
  }

  function findFile(fileId: string): RiskFilePackageItem | undefined {
    return files.value.find((item) => item.id === fileId)
  }

  function cancelFileOperation(fileId: string): void {
    uploadOperations.get(fileId)?.cancel()
    uploadOperations.delete(fileId)
    fileControllers.get(fileId)?.abort()
    fileControllers.delete(fileId)
  }

  function dispose(): void {
    detailRunId += 1
    listRunId += 1
    detailController?.abort()
    listController?.abort()
    for (const fileId of fileControllers.keys()) cancelFileOperation(fileId)
  }

  if (getCurrentInstance()) onBeforeUnmount(dispose)

  return {
    businessCode,
    files,
    packageErrorMessage,
    selectedTask,
    detailErrorMessage,
    checkpointConflictMessage,
    operation,
    taskList,
    isTaskBusy,
    allFilesReady,
    canCreateTask,
    canRetryExecute,
    activeReviewItem,
    auditItems,
    checks,
    warnings,
    addFiles,
    setDeclaredDocumentType,
    removeFile,
    retryFile,
    createAndExecuteTask,
    retryExecute,
    loadTaskList,
    loadTask,
    refreshSelectedTask,
    submitReview,
    cancelSelectedTask,
    openSourceDocument,
    exportSelectedTask,
    resetPackage,
    clearSelectedTask,
    dispose,
  }
}

function toTaskSummary(task: RiskAssessmentTask): RiskTaskSummary {
  return {
    id: task.id,
    business_code: task.business_code,
    status: task.status,
    current_node: task.current_node,
    document_count: task.documents.length,
    error_message: task.error_message,
    created_at: task.created_at,
    updated_at: task.updated_at,
    finished_at: task.finished_at,
  }
}

function nextPollDelay(current: number, maximum: number): number {
  if (current <= 0) return 0
  return Math.min(maximum, Math.round(current * 1.4))
}

function abortableDelay(delayMs: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolveAndCleanup, delayMs)
    function resolveAndCleanup(): void {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }
    function onAbort(): void {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(new RiskWorkbenchError('请求已停止。', 'ABORTED'))
    }
    if (signal?.aborted) {
      onAbort()
      return
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function defaultRequestId(): string {
  return typeof crypto !== 'undefined' && 'randomUUID' in crypto
    ? crypto.randomUUID()
    : `risk-web-${Date.now()}-${Math.random().toString(16).slice(2)}`
}

function sanitizeFilename(value: string): string {
  return value.replace(/[<>:"/\\|?*\x00-\x1F]/g, '_').trim() || 'risk-task'
}

function triggerBlobDownload(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

class RiskWorkbenchError extends Error {
  constructor(message: string, public readonly code = 'WORKBENCH_ERROR') {
    super(message)
    this.name = 'RiskWorkbenchError'
  }
}
