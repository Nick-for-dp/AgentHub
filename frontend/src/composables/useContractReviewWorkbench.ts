import { computed, getCurrentInstance, onBeforeUnmount, ref } from 'vue'

import {
  type ContractReviewClient,
  type ContractReviewTask,
  type ContractType,
  type CounterpartyLevel,
  type FileParseTask,
  type FileUploadPrepareResponse,
  type InternalTaskStatus,
  type UploadOperation,
  DEFAULT_POLL_INITIAL_INTERVAL_MS,
  DEFAULT_POLL_MAX_INTERVAL_MS,
  DEFAULT_POLL_TIMEOUT_MS,
  contractReviewClient,
  isTerminalTaskStatus,
  isUncertainExecutionError,
  toSafeContractReviewErrorMessage,
} from '../api/internalContractReview'

export type ContractReviewPhase =
  | 'idle'
  | 'preparing_upload'
  | 'uploading'
  | 'parsing'
  | 'creating_review'
  | 'reviewing'
  | 'succeeded'
  | 'failed'

export interface ContractReviewSubmission {
  file: File | null
  contractType: ContractType | null
  counterpartyLevel: CounterpartyLevel | null
}

export interface SubmissionValidation {
  file?: string
  contractType?: string
  counterpartyLevel?: string
}

export interface WorkbenchOptions {
  client?: ContractReviewClient
  pollTimeoutMs?: number
  pollInitialIntervalMs?: number
  pollMaxIntervalMs?: number
  now?: () => number
}

export interface WorkbenchState {
  phase: ContractReviewPhase
  errorMessage: string | null
  uploadProgress: number
  startedAt: number | null
  elapsedSeconds: number
  fileParseTask: FileParseTask | null
  reviewTask: ContractReviewTask | null
  canRetryExecute: boolean
}

const SUPPORTED_FILE_PATTERN = /\.(pdf|docx)$/i

const PHASE_LABELS: Record<ContractReviewPhase, string> = {
  idle: '等待提交',
  preparing_upload: '正在申请上传',
  uploading: '正在上传合同',
  parsing: '正在解析合同',
  creating_review: '正在创建审查任务',
  reviewing: '正在审查敏感条款',
  succeeded: '审查完成',
  failed: '审查未完成',
}

export function validateContractReviewSubmission(
  submission: ContractReviewSubmission,
): SubmissionValidation {
  const errors: SubmissionValidation = {}
  if (!submission.file) {
    errors.file = '请选择 PDF 或 DOCX 合同文件。'
  } else if (!SUPPORTED_FILE_PATTERN.test(submission.file.name)) {
    errors.file = '仅支持 PDF 或 DOCX 合同文件；DOC 和图片暂不支持本次审查。'
  }
  if (!submission.contractType) errors.contractType = '请选择合同类型。'
  if (!submission.counterpartyLevel) errors.counterpartyLevel = '请选择合同对手方资信等级。'
  return errors
}

export function phaseLabel(phase: ContractReviewPhase): string {
  return PHASE_LABELS[phase]
}

export function useContractReviewWorkbench(options: WorkbenchOptions = {}) {
  const client = options.client ?? contractReviewClient
  const now = options.now ?? Date.now
  const pollTimeoutMs = options.pollTimeoutMs ?? DEFAULT_POLL_TIMEOUT_MS
  const pollInitialIntervalMs = options.pollInitialIntervalMs ?? DEFAULT_POLL_INITIAL_INTERVAL_MS
  const pollMaxIntervalMs = options.pollMaxIntervalMs ?? DEFAULT_POLL_MAX_INTERVAL_MS

  const phase = ref<ContractReviewPhase>('idle')
  const errorMessage = ref<string | null>(null)
  const uploadProgress = ref(0)
  const startedAt = ref<number | null>(null)
  const elapsedNow = ref(now())
  const fileParseTask = ref<FileParseTask | null>(null)
  const reviewTask = ref<ContractReviewTask | null>(null)
  const runId = ref(0)

  let requestController: AbortController | null = null
  let uploadOperation: UploadOperation | null = null
  let elapsedTimer: ReturnType<typeof setInterval> | null = null

  const isBusy = computed(() => !['idle', 'succeeded', 'failed'].includes(phase.value))
  const elapsedSeconds = computed(() => {
    if (!startedAt.value) return 0
    return Math.max(0, Math.floor((elapsedNow.value - startedAt.value) / 1000))
  })
  const canRetryExecute = computed(() => phase.value === 'failed' && reviewTask.value?.status === 'PENDING')
  const state = computed<WorkbenchState>(() => ({
    phase: phase.value,
    errorMessage: errorMessage.value,
    uploadProgress: uploadProgress.value,
    startedAt: startedAt.value,
    elapsedSeconds: elapsedSeconds.value,
    fileParseTask: fileParseTask.value,
    reviewTask: reviewTask.value,
    canRetryExecute: canRetryExecute.value,
  }))

  function isCurrent(currentRunId: number): boolean {
    return runId.value === currentRunId
  }

  function ensureActive(currentRunId: number): void {
    if (!isCurrent(currentRunId)) {
      throw new WorkbenchError('审查任务已过期。', 'STALE_RUN')
    }
  }

  function beginRun(): number {
    stopActiveRun()
    runId.value += 1
    const currentRunId = runId.value
    requestController = new AbortController()
    uploadProgress.value = 0
    errorMessage.value = null
    fileParseTask.value = null
    reviewTask.value = null
    startedAt.value = now()
    elapsedNow.value = startedAt.value
    startElapsedTimer(currentRunId)
    return currentRunId
  }

  async function startReview(submission: ContractReviewSubmission): Promise<boolean> {
    const validation = validateContractReviewSubmission(submission)
    if (Object.keys(validation).length > 0) {
      phase.value = 'failed'
      errorMessage.value = Object.values(validation)[0] ?? '请补充必填信息。'
      return false
    }

    const currentRunId = beginRun()
    const file = submission.file as File
    const contractType = submission.contractType as ContractType
    const counterpartyLevel = submission.counterpartyLevel as CounterpartyLevel

    try {
      phase.value = 'preparing_upload'
      const upload = await client.prepareFileUpload(file, { signal: currentSignal() })
      ensureActive(currentRunId)

      phase.value = 'uploading'
      uploadOperation = client.uploadToPresignedUrl(upload, file, {
        onProgress: (percent) => {
          if (isCurrent(currentRunId)) uploadProgress.value = percent
        },
      })
      await uploadOperation.promise
      ensureActive(currentRunId)
      uploadOperation = null

      phase.value = 'parsing'
      const parseTask = await client.createFileParseTask(
        upload.storage_uri,
        upload.original_filename,
        { signal: currentSignal() },
      )
      ensureActive(currentRunId)
      fileParseTask.value = await waitForFileParseTerminal(parseTask, currentRunId)
      assertSucceeded(fileParseTask.value.status, fileParseTask.value.error_message, '文件解析')

      phase.value = 'creating_review'
      const createdReviewTask = await client.createContractReviewTask({
        agent_code: 'contract-review',
        file_parse_task_id: fileParseTask.value.id,
        contract_type: contractType,
        counterparty_level: counterpartyLevel,
        callback_metadata: { source: 'contract-review-web-workbench' },
      }, { signal: currentSignal() })
      ensureActive(currentRunId)
      reviewTask.value = createdReviewTask

      return await executeAndResolve(createdReviewTask, currentRunId)
    } catch (error) {
      handleRunError(error, currentRunId)
      return false
    }
  }

  async function retryExecute(): Promise<boolean> {
    const currentTask = reviewTask.value
    const currentParseTask = fileParseTask.value
    if (!currentTask || currentTask.status !== 'PENDING' || isBusy.value) return false

    const currentRunId = beginRun()
    reviewTask.value = currentTask
    fileParseTask.value = currentParseTask
    try {
      return await executeAndResolve(currentTask, currentRunId)
    } catch (error) {
      handleRunError(error, currentRunId)
      return false
    }
  }

  async function executeAndResolve(
    task: ContractReviewTask,
    currentRunId: number,
  ): Promise<boolean> {
    phase.value = 'reviewing'
    let resolvedTask: ContractReviewTask
    try {
      resolvedTask = await client.executeContractReviewTask(task.id, { signal: currentSignal() })
      ensureActive(currentRunId)
    } catch (error) {
      ensureActive(currentRunId)
      if (!isUncertainExecutionError(error)) throw error
      resolvedTask = await client.getContractReviewTask(task.id, { signal: currentSignal() })
      ensureActive(currentRunId)
      if (resolvedTask.status === 'PENDING') {
        reviewTask.value = resolvedTask
        throw new WorkbenchError('未能确认审查是否已启动。已确认任务仍待执行，可安全重试。')
      }
    }

    reviewTask.value = await waitForReviewTerminal(resolvedTask, currentRunId)
    assertSucceeded(reviewTask.value.status, reviewTask.value.error_message, '合同审查')
    finishRun('succeeded', currentRunId)
    return true
  }

  async function waitForFileParseTerminal(
    task: FileParseTask,
    currentRunId: number,
  ): Promise<FileParseTask> {
    if (isTerminalTaskStatus(task.status)) return task
    return pollUntilTerminal(
      task,
      (taskId) => client.getFileParseTask(taskId, { signal: currentSignal() }),
      currentRunId,
    )
  }

  async function waitForReviewTerminal(
    task: ContractReviewTask,
    currentRunId: number,
  ): Promise<ContractReviewTask> {
    if (isTerminalTaskStatus(task.status)) return task
    return pollUntilTerminal(
      task,
      (taskId) => client.getContractReviewTask(taskId, { signal: currentSignal() }),
      currentRunId,
    )
  }

  async function pollUntilTerminal<T extends { id: string; status: InternalTaskStatus }>(
    task: T,
    readTask: (taskId: string) => Promise<T>,
    currentRunId: number,
  ): Promise<T> {
    const deadline = now() + pollTimeoutMs
    let currentTask = task
    let delay = pollInitialIntervalMs
    while (!isTerminalTaskStatus(currentTask.status)) {
      ensureActive(currentRunId)
      if (now() >= deadline) {
        throw new WorkbenchError('任务仍在处理中，已停止等待。请稍后重新打开或再次查询该任务。')
      }
      await abortableDelay(delay, currentSignal())
      ensureActive(currentRunId)
      currentTask = await readTask(currentTask.id)
      ensureActive(currentRunId)
      delay = Math.min(pollMaxIntervalMs, Math.round(delay * 1.4))
    }
    return currentTask
  }

  function cancelWaiting(): void {
    stopActiveRun()
    phase.value = 'idle'
    errorMessage.value = null
    uploadProgress.value = 0
  }

  function reset(): void {
    cancelWaiting()
    fileParseTask.value = null
    reviewTask.value = null
    startedAt.value = null
  }

  function handleRunError(error: unknown, currentRunId: number): void {
    if (!isCurrent(currentRunId)) return
    if (isAbortError(error)) {
      finishRun('idle', currentRunId)
      return
    }
    errorMessage.value = error instanceof WorkbenchError
      ? error.message
      : toSafeContractReviewErrorMessage(error)
    finishRun('failed', currentRunId)
  }

  function finishRun(nextPhase: ContractReviewPhase, currentRunId: number): void {
    if (!isCurrent(currentRunId)) return
    phase.value = nextPhase
    stopElapsedTimer()
    requestController = null
    uploadOperation = null
  }

  function stopActiveRun(): void {
    runId.value += 1
    uploadOperation?.cancel()
    uploadOperation = null
    requestController?.abort()
    requestController = null
    stopElapsedTimer()
  }

  function currentSignal(): AbortSignal | undefined {
    return requestController?.signal
  }

  function startElapsedTimer(currentRunId: number): void {
    stopElapsedTimer()
    elapsedTimer = setInterval(() => {
      if (isCurrent(currentRunId)) elapsedNow.value = now()
    }, 1_000)
  }

  function stopElapsedTimer(): void {
    if (elapsedTimer) {
      clearInterval(elapsedTimer)
      elapsedTimer = null
    }
  }

  if (getCurrentInstance()) onBeforeUnmount(stopActiveRun)

  return {
    phase,
    errorMessage,
    uploadProgress,
    startedAt,
    elapsedSeconds,
    fileParseTask,
    reviewTask,
    runId,
    isBusy,
    canRetryExecute,
    state,
    startReview,
    retryExecute,
    cancelWaiting,
    reset,
  }
}

function assertSucceeded(status: InternalTaskStatus, detail: string | null | undefined, label: string): void {
  if (status === 'SUCCEEDED') return
  if (status === 'CANCELLED') throw new WorkbenchError(`${label}任务已取消。`)
  throw new WorkbenchError(detail?.trim() || `${label}未能成功完成。`)
}

function abortableDelay(delayMs: number, signal: AbortSignal | undefined): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(cleanupAndResolve, delayMs)
    function cleanupAndResolve(): void {
      signal?.removeEventListener('abort', onAbort)
      resolve()
    }
    function onAbort(): void {
      clearTimeout(timer)
      signal?.removeEventListener('abort', onAbort)
      reject(new WorkbenchError('请求已停止。', 'ABORTED'))
    }
    if (signal?.aborted) {
      onAbort()
      return
    }
    signal?.addEventListener('abort', onAbort, { once: true })
  })
}

function isAbortError(error: unknown): boolean {
  return error instanceof WorkbenchError && error.code === 'ABORTED'
}

class WorkbenchError extends Error {
  constructor(message: string, public readonly code = 'WORKBENCH_ERROR') {
    super(message)
    this.name = 'WorkbenchError'
  }
}
