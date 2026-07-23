import { AxiosError, type AxiosResponse } from 'axios'
import { describe, expect, it, vi } from 'vitest'

import type {
  FileParseTask,
  FileUploadPrepareResponse,
} from '../api/internalFiles'
import type {
  CreateRiskTaskPayload,
  RiskAssessmentTask,
  RiskAssistantClient,
  RiskDocumentType,
} from '../api/internalRiskAssistant'
import { useRiskAssistantWorkbench } from './useRiskAssistantWorkbench'

function uploadFor(file: File): FileUploadPrepareResponse {
  return {
    upload_url: `https://storage.test/${encodeURIComponent(file.name)}`,
    method: 'PUT',
    headers: { 'Content-Type': file.type },
    storage_uri: `minio://risk/${file.name}`,
    bucket: 'risk',
    object_key: file.name,
    original_filename: file.name,
    file_type: file.name.endsWith('.docx') ? 'docx' : 'pdf',
    content_type: file.type,
    expires_seconds: 900,
  }
}

function parseTask(
  id: string,
  status: FileParseTask['status'] = 'SUCCEEDED',
  filename = `${id}.pdf`,
): FileParseTask {
  return {
    id,
    source_uri: `minio://risk/${filename}`,
    original_filename: filename,
    file_type: filename.endsWith('.docx') ? 'docx' : 'pdf',
    status,
    result_snapshot: { blocks: [] },
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:00:01+08:00',
  }
}

function riskTask(
  status: RiskAssessmentTask['status'],
  overrides: Partial<RiskAssessmentTask> = {},
): RiskAssessmentTask {
  return {
    id: 'risk-1',
    status,
    agent_code: 'risk-assistant',
    business_code: 'BIZ-001',
    checkpoint_version: status === 'WAITING_REVIEW' ? 2 : 0,
    current_node: status === 'RUNNING' ? 'extract_documents' : null,
    versions: {},
    documents: [],
    result: null,
    review_context: null,
    review_events: [],
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:00:01+08:00',
    ...overrides,
  }
}

function waitingTask(checkpointVersion = 2): RiskAssessmentTask {
  return riskTask('WAITING_REVIEW', {
    checkpoint_version: checkpointVersion,
    result: {
      audit_items: [],
      checks: [],
      warnings: [],
      review_items: [{
        id: 'review-1',
        target_kind: 'FIELD',
        target_code: 'goods_name',
        alternatives: ['焦炭', '焦粉'],
        sources: [],
        is_resolved: false,
      }],
    },
    review_context: {
      audit_items: [],
      checks: [],
      warnings: [],
      review_items: [{
        id: 'review-1',
        target_kind: 'FIELD',
        target_code: 'goods_name',
        alternatives: ['焦炭', '焦粉'],
        sources: [],
        is_resolved: false,
      }],
    },
  })
}

function createClient(overrides: Partial<RiskAssistantClient> = {}): RiskAssistantClient {
  return {
    prepareFileUpload: async (file) => uploadFor(file),
    uploadToPresignedUrl: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    createFileParseTask: async (_sourceUri, originalFilename) => (
      parseTask(`parse-${originalFilename}`, 'SUCCEEDED', originalFilename)
    ),
    getFileParseTask: async (taskId) => parseTask(taskId),
    listRiskTasks: async () => ({ items: [], total: 0, page: 1, page_size: 20 }),
    createRiskTask: async () => riskTask('PENDING'),
    getRiskTask: async () => riskTask('SUCCEEDED'),
    deleteRiskTask: async () => undefined,
    executeRiskTask: async () => riskTask('SUCCEEDED'),
    submitRiskReview: async () => riskTask('SUCCEEDED'),
    cancelRiskTask: async () => riskTask('CANCELLED'),
    getRiskDocumentAccess: async () => ({
      access_url: 'https://storage.test/source',
      method: 'GET',
      headers: {},
      expires_seconds: 300,
      original_filename: 'source.pdf',
      file_type: 'pdf',
    }),
    exportRiskWorkbook: async () => new Blob(['xlsx']),
    ...overrides,
  }
}

function file(name: string): File {
  const type = name.endsWith('.docx')
    ? 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    : 'application/pdf'
  return new File([name], name, { type })
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => { resolve = settle })
  return { promise, resolve }
}

function axiosResponse(status: number): AxiosResponse {
  return {
    data: { message: 'internal detail' },
    status,
    statusText: String(status),
    headers: {},
    config: { headers: {} } as AxiosResponse['config'],
  }
}

async function addReadyPackage(
  workbench: ReturnType<typeof useRiskAssistantWorkbench>,
  names = ['purchase.pdf'],
): Promise<void> {
  await workbench.addFiles(names.map(file))
  const types: RiskDocumentType[] = [
    'PURCHASE_CONTRACT',
    'SALES_CONTRACT',
    'APPROVAL_FORM',
    'SETTLEMENT_STATEMENT',
  ]
  workbench.files.value.forEach((item, index) => {
    workbench.setDeclaredDocumentType(item.id, types[index] ?? 'PURCHASE_CONTRACT')
  })
  workbench.businessCode.value = 'BIZ-001'
}

describe('useRiskAssistantWorkbench file package and execution', () => {
  it('runs four independent uploads/parses before one task create and execute', async () => {
    const calls: string[] = []
    const createRiskTask = vi.fn(async (payload: CreateRiskTaskPayload) => {
      calls.push('create-risk')
      expect(payload.documents).toHaveLength(4)
      expect(payload.documents.map((item) => item.declared_document_type)).toEqual([
        'PURCHASE_CONTRACT',
        'SALES_CONTRACT',
        'APPROVAL_FORM',
        'SETTLEMENT_STATEMENT',
      ])
      return riskTask('PENDING')
    })
    const client = createClient({
      prepareFileUpload: async (selected) => {
        calls.push(`prepare:${selected.name}`)
        return uploadFor(selected)
      },
      uploadToPresignedUrl: (upload) => {
        calls.push(`upload:${upload.original_filename}`)
        return { promise: Promise.resolve(), cancel: vi.fn() }
      },
      createFileParseTask: async (_uri, name) => {
        calls.push(`parse:${name}`)
        return parseTask(`parse-${name}`, 'SUCCEEDED', name)
      },
      createRiskTask,
      executeRiskTask: async () => {
        calls.push('execute-risk')
        return riskTask('SUCCEEDED')
      },
    })
    const workbench = useRiskAssistantWorkbench({ client, pollInitialIntervalMs: 0 })

    await addReadyPackage(workbench, [
      'purchase.pdf',
      'sales.pdf',
      'approval.docx',
      'settlement.pdf',
    ])
    await expect(workbench.createAndExecuteTask()).resolves.toBe(true)

    expect(workbench.files.value.every((item) => item.phase === 'READY')).toBe(true)
    expect(calls.filter((item) => item.startsWith('prepare:'))).toHaveLength(4)
    expect(calls.filter((item) => item.startsWith('upload:'))).toHaveLength(4)
    expect(calls.filter((item) => item.startsWith('parse:'))).toHaveLength(4)
    expect(calls.slice(-2)).toEqual(['create-risk', 'execute-risk'])
    expect(workbench.selectedTask.value?.status).toBe('SUCCEEDED')
  })

  it('retries only the failed file', async () => {
    let attempts = 0
    const workbench = useRiskAssistantWorkbench({
      client: createClient({
        createFileParseTask: async (_uri, name) => {
          attempts += 1
          return attempts === 1
            ? { ...parseTask('parse-1', 'FAILED', name), error_message: '扫描件解析失败' }
            : parseTask('parse-2', 'SUCCEEDED', name)
        },
      }),
      pollInitialIntervalMs: 0,
    })

    await workbench.addFiles([file('purchase.pdf')])
    expect(workbench.files.value[0]?.phase).toBe('FAILED')

    await expect(workbench.retryFile(workbench.files.value[0]!.id)).resolves.toBe(true)
    expect(attempts).toBe(2)
    expect(workbench.files.value[0]?.phase).toBe('READY')
    expect(workbench.files.value[0]?.parseTaskId).toBe('parse-2')
  })

  it('ignores a removed file when its old prepare request resolves late', async () => {
    const firstPrepare = deferred<FileUploadPrepareResponse>()
    let prepareCount = 0
    const workbench = useRiskAssistantWorkbench({
      client: createClient({
        prepareFileUpload: async (selected) => {
          prepareCount += 1
          if (prepareCount === 1) return firstPrepare.promise
          return uploadFor(selected)
        },
      }),
      pollInitialIntervalMs: 0,
    })

    const firstRun = workbench.addFiles([file('same.pdf')])
    const firstId = workbench.files.value[0]!.id
    workbench.removeFile(firstId)
    await workbench.addFiles([file('same.pdf')])
    firstPrepare.resolve(uploadFor(file('same.pdf')))
    await firstRun

    expect(workbench.files.value).toHaveLength(1)
    expect(workbench.files.value[0]?.id).not.toBe(firstId)
    expect(workbench.files.value[0]?.phase).toBe('READY')
  })
})

describe('useRiskAssistantWorkbench recovery', () => {
  it('restores a RUNNING route task and polls until WAITING_REVIEW', async () => {
    const getRiskTask = vi.fn()
      .mockResolvedValueOnce(riskTask('RUNNING'))
      .mockResolvedValueOnce(waitingTask())
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ getRiskTask }),
      pollInitialIntervalMs: 0,
      pollMaxIntervalMs: 0,
    })

    await expect(workbench.loadTask('risk-1')).resolves.toBe(true)

    expect(getRiskTask).toHaveBeenCalledTimes(2)
    expect(workbench.selectedTask.value?.status).toBe('WAITING_REVIEW')
    expect(workbench.activeReviewItem.value?.target_code).toBe('goods_name')
  })

  it('restores WAITING_REVIEW without ordinary polling', async () => {
    const getRiskTask = vi.fn(async () => waitingTask())
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ getRiskTask }),
      pollInitialIntervalMs: 0,
    })

    await expect(workbench.loadTask('risk-1')).resolves.toBe(true)

    expect(getRiskTask).toHaveBeenCalledTimes(1)
    expect(workbench.operation.value).toBe('IDLE')
  })

  it('GETs task state after execute timeout and only enables retry for confirmed PENDING', async () => {
    const executeRiskTask = vi.fn(async () => {
      throw new AxiosError('timeout', 'ECONNABORTED')
    })
    const getRiskTask = vi.fn(async () => riskTask('PENDING'))
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ executeRiskTask, getRiskTask }),
      pollInitialIntervalMs: 0,
    })
    await addReadyPackage(workbench)

    await expect(workbench.createAndExecuteTask()).resolves.toBe(false)

    expect(executeRiskTask).toHaveBeenCalledTimes(1)
    expect(getRiskTask).toHaveBeenCalledTimes(1)
    expect(workbench.selectedTask.value?.status).toBe('PENDING')
    expect(workbench.canRetryExecute.value).toBe(true)
  })

  it('refreshes task and does not repeat a review after checkpoint conflict', async () => {
    const conflict = new AxiosError(
      'conflict',
      undefined,
      undefined,
      undefined,
      axiosResponse(409),
    )
    const submitRiskReview = vi.fn(async () => { throw conflict })
    const getRiskTask = vi.fn(async () => waitingTask(3))
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ submitRiskReview, getRiskTask }),
      pollInitialIntervalMs: 0,
    })
    workbench.selectedTask.value = waitingTask(2)

    await expect(workbench.submitReview({
      action: 'SELECT_VALUE',
      value: '焦炭',
      reason: '根据合同正文确认',
    })).resolves.toBe(false)

    expect(submitRiskReview).toHaveBeenCalledTimes(1)
    expect(getRiskTask).toHaveBeenCalledTimes(1)
    expect(workbench.selectedTask.value?.checkpoint_version).toBe(3)
    expect(workbench.checkpointConflictMessage.value).toContain('已更新')
  })

  it('does not poll a terminal task loaded from its stable route', async () => {
    const getRiskTask = vi.fn(async () => riskTask('SUCCEEDED'))
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ getRiskTask }),
      pollInitialIntervalMs: 0,
    })

    await expect(workbench.loadTask('risk-1')).resolves.toBe(true)

    expect(getRiskTask).toHaveBeenCalledTimes(1)
    expect(workbench.selectedTask.value?.status).toBe('SUCCEEDED')
  })

  it('soft deletes a recent task and clears its selected detail', async () => {
    const deleteRiskTask = vi.fn(async () => undefined)
    const workbench = useRiskAssistantWorkbench({
      client: createClient({ deleteRiskTask }),
      pollInitialIntervalMs: 0,
    })
    workbench.selectedTask.value = riskTask('FAILED')
    workbench.taskList.value = {
      items: [{
        id: 'risk-1',
        business_code: 'BIZ-001',
        status: 'FAILED',
        document_count: 4,
        created_at: '2026-07-20T10:00:00+08:00',
        updated_at: '2026-07-20T10:01:00+08:00',
      }],
      total: 1,
      page: 1,
      pageSize: 20,
      status: null,
      loading: false,
      errorMessage: null,
    }

    await expect(workbench.deleteTask('risk-1')).resolves.toBe(true)

    expect(deleteRiskTask).toHaveBeenCalledWith('risk-1')
    expect(workbench.taskList.value.items).toEqual([])
    expect(workbench.taskList.value.total).toBe(0)
    expect(workbench.selectedTask.value).toBeNull()
    expect(workbench.deletingTaskId.value).toBeNull()
  })
})
