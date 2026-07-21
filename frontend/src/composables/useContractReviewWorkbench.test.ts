import { AxiosError } from 'axios'
import { describe, expect, it, vi } from 'vitest'

import type {
  ContractReviewClient,
  ContractReviewTask,
  FileParseTask,
  FileUploadPrepareResponse,
} from '../api/internalContractReview'
import { useContractReviewWorkbench } from './useContractReviewWorkbench'

function createUpload(): FileUploadPrepareResponse {
  return {
    upload_url: 'http://minio.test/presigned',
    method: 'PUT',
    headers: { 'Content-Type': 'application/pdf' },
    storage_uri: 'minio://int-agenthub-raw/uploads/test.pdf',
    bucket: 'int-agenthub-raw',
    object_key: 'uploads/test.pdf',
    original_filename: 'test.pdf',
    file_type: 'pdf',
    content_type: 'application/pdf',
    expires_seconds: 900,
  }
}

function createParseTask(status: FileParseTask['status'] = 'SUCCEEDED'): FileParseTask {
  return {
    id: 'parse-1',
    source_uri: 'minio://int-agenthub-raw/uploads/test.pdf',
    original_filename: 'test.pdf',
    file_type: 'pdf',
    status,
    result_snapshot: { blocks: [] },
    created_at: '2026-07-13T00:00:00+08:00',
    updated_at: '2026-07-13T00:00:00+08:00',
  }
}

function createReviewTask(
  status: ContractReviewTask['status'] = 'SUCCEEDED',
  id = 'review-1',
): ContractReviewTask {
  return {
    id,
    status,
    agent_code: 'contract-review',
    file_parse_task_id: 'parse-1',
    contract_type: 'warehouse',
    counterparty_level: 'A1',
    callback_metadata: {},
    result: status === 'SUCCEEDED'
      ? {
        clauses: [],
        summary: {
          total_clause_count: 0,
          sensitive_clause_count: 0,
          highest_risk_level: null,
          warning_count: 0,
        },
        warnings: [],
      }
      : null,
    created_at: '2026-07-13T00:00:00+08:00',
    updated_at: '2026-07-13T00:00:00+08:00',
  }
}

function createClient(overrides: Partial<ContractReviewClient> = {}): ContractReviewClient {
  return {
    prepareFileUpload: async () => createUpload(),
    uploadToPresignedUrl: () => ({ promise: Promise.resolve(), cancel: vi.fn() }),
    createFileParseTask: async () => createParseTask(),
    getFileParseTask: async () => createParseTask(),
    createContractReviewTask: async () => createReviewTask('PENDING'),
    getContractReviewTask: async () => createReviewTask('SUCCEEDED'),
    executeContractReviewTask: async () => createReviewTask('SUCCEEDED'),
    ...overrides,
  }
}

function submission(fileName = 'contract.pdf') {
  return {
    file: new File(['contract'], fileName, { type: 'application/pdf' }),
    contractType: 'warehouse' as const,
    counterpartyLevel: 'A1' as const,
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => {
    resolve = settle
  })
  return { promise, resolve }
}

describe('useContractReviewWorkbench', () => {
  it('runs upload, parse, creation, and execute in order', async () => {
    const calls: string[] = []
    const client = createClient({
      prepareFileUpload: async () => {
        calls.push('prepare')
        return createUpload()
      },
      uploadToPresignedUrl: () => {
        calls.push('upload')
        return { promise: Promise.resolve(), cancel: vi.fn() }
      },
      createFileParseTask: async (_sourceUri, originalFilename) => {
        calls.push('parse')
        expect(originalFilename).toBe('test.pdf')
        return createParseTask()
      },
      createContractReviewTask: async () => {
        calls.push('create')
        return createReviewTask('PENDING')
      },
      executeContractReviewTask: async () => {
        calls.push('execute')
        return createReviewTask('SUCCEEDED')
      },
    })
    const workbench = useContractReviewWorkbench({ client })

    await expect(workbench.startReview(submission())).resolves.toBe(true)

    expect(calls).toEqual(['prepare', 'upload', 'parse', 'create', 'execute'])
    expect(workbench.phase.value).toBe('succeeded')
    expect(workbench.reviewTask.value?.status).toBe('SUCCEEDED')
  })

  it('short-circuits after parse failure without creating or executing review', async () => {
    const createReviewSpy = vi.fn(async () => createReviewTask('PENDING'))
    const executeReviewSpy = vi.fn(async () => createReviewTask('SUCCEEDED'))
    const workbench = useContractReviewWorkbench({
      client: createClient({
        createFileParseTask: async () => ({ ...createParseTask('FAILED'), error_message: '无法解析文件' }),
        createContractReviewTask: createReviewSpy,
        executeContractReviewTask: executeReviewSpy,
      }),
    })

    await expect(workbench.startReview(submission())).resolves.toBe(false)

    expect(workbench.phase.value).toBe('failed')
    expect(workbench.errorMessage.value).toBe('无法解析文件')
    expect(createReviewSpy).not.toHaveBeenCalled()
    expect(executeReviewSpy).not.toHaveBeenCalled()
  })

  it('polls a non-terminal parse task until it succeeds', async () => {
    const getFileParseTask = vi.fn(async () => createParseTask('SUCCEEDED'))
    const workbench = useContractReviewWorkbench({
      client: createClient({
        createFileParseTask: async () => createParseTask('PENDING'),
        getFileParseTask,
      }),
      pollInitialIntervalMs: 0,
      pollMaxIntervalMs: 0,
    })

    await expect(workbench.startReview(submission())).resolves.toBe(true)

    expect(getFileParseTask).toHaveBeenCalledTimes(1)
    expect(workbench.phase.value).toBe('succeeded')
  })

  it('keeps a newer run when an earlier request resolves late', async () => {
    const firstPrepare = deferred<FileUploadPrepareResponse>()
    let prepareCount = 0
    const client = createClient({
      prepareFileUpload: async () => {
        prepareCount += 1
        if (prepareCount === 1) {
          return firstPrepare.promise
        }
        return createUpload()
      },
      createContractReviewTask: async () => createReviewTask('PENDING', `review-${prepareCount}`),
      executeContractReviewTask: async (taskId) => createReviewTask('SUCCEEDED', taskId),
    })
    const workbench = useContractReviewWorkbench({ client })

    const firstRun = workbench.startReview(submission('first.pdf'))
    const secondRun = workbench.startReview(submission('second.pdf'))
    await expect(secondRun).resolves.toBe(true)
    firstPrepare.resolve(createUpload())
    await expect(firstRun).resolves.toBe(false)

    expect(workbench.reviewTask.value?.id).toBe('review-2')
    expect(workbench.phase.value).toBe('succeeded')
  })

  it('reads task status before allowing a retry after an uncertain execute response', async () => {
    const calls: string[] = []
    let executeAttempts = 0
    const client = createClient({
      executeContractReviewTask: async () => {
        calls.push('execute')
        executeAttempts += 1
        if (executeAttempts === 1) throw new AxiosError('timeout', 'ECONNABORTED')
        return createReviewTask('SUCCEEDED')
      },
      getContractReviewTask: async () => {
        calls.push('get')
        return createReviewTask('PENDING')
      },
    })
    const workbench = useContractReviewWorkbench({ client })

    await expect(workbench.startReview(submission())).resolves.toBe(false)

    expect(calls).toEqual(['execute', 'get'])
    expect(workbench.canRetryExecute.value).toBe(true)
    await expect(workbench.retryExecute()).resolves.toBe(true)
    expect(calls).toEqual(['execute', 'get', 'execute'])
    expect(workbench.phase.value).toBe('succeeded')
  })

  it('cancels local waiting without allowing the old request to update state', async () => {
    const pendingPrepare = deferred<FileUploadPrepareResponse>()
    const workbench = useContractReviewWorkbench({
      client: createClient({
        prepareFileUpload: async () => pendingPrepare.promise,
      }),
    })

    const running = workbench.startReview(submission())
    workbench.cancelWaiting()
    pendingPrepare.resolve(createUpload())
    await expect(running).resolves.toBe(false)

    expect(workbench.phase.value).toBe('idle')
    expect(workbench.reviewTask.value).toBeNull()
  })
})
