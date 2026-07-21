import { AxiosError, type AxiosResponse } from 'axios'
import { afterEach, describe, expect, it, vi } from 'vitest'

import { http } from './http'
import {
  executeRiskTask,
  exportRiskWorkbook,
  listRiskTasks,
  submitRiskReview,
  toSafeRiskAssistantError,
  type RiskAssessmentTask,
  type RiskReviewSubmitPayload,
  type RiskTaskPage,
} from './internalRiskAssistant'

function apiResponse<T>(data: T) {
  return { data: { code: 'OK', message: 'success', data } }
}

function createTask(): RiskAssessmentTask {
  return {
    id: 'risk-1',
    status: 'WAITING_REVIEW',
    agent_code: 'risk-assistant',
    business_code: 'BIZ-001',
    checkpoint_version: 2,
    versions: {},
    documents: [],
    review_events: [],
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:01:00+08:00',
  }
}

function axiosResponse(status: number, data: unknown): AxiosResponse {
  return {
    data,
    status,
    statusText: String(status),
    headers: {},
    config: { headers: {} } as AxiosResponse['config'],
  }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('internalRiskAssistant client', () => {
  it('sends stable pagination and status parameters', async () => {
    const page: RiskTaskPage = { items: [], total: 0, page: 2, page_size: 10 }
    const get = vi.spyOn(http, 'get').mockResolvedValue(apiResponse(page))

    await expect(listRiskTasks({ page: 2, pageSize: 10, status: 'WAITING_REVIEW' }))
      .resolves.toEqual(page)

    expect(get).toHaveBeenCalledWith('/internal/risk-assistant/tasks', expect.objectContaining({
      params: { page: 2, page_size: 10, status: 'WAITING_REVIEW' },
    }))
  })

  it('sends request id header for execute and checkpoint version in review payload', async () => {
    const task = createTask()
    const post = vi.spyOn(http, 'post').mockResolvedValue(apiResponse(task))
    const review: RiskReviewSubmitPayload = {
      review_item_id: 'review-1',
      target_kind: 'FIELD',
      target_code: 'goods_name',
      action: 'CORRECT_VALUE',
      value: '硫酸钠',
      reason: '根据合同正文修正',
      checkpoint_version: 2,
    }

    await executeRiskTask(task.id, { requestId: 'req-execute' })
    await submitRiskReview(task.id, review, { requestId: 'req-review' })

    expect(post).toHaveBeenNthCalledWith(
      1,
      '/internal/risk-assistant/tasks/risk-1/execute',
      {},
      expect.objectContaining({ headers: { 'X-Request-ID': 'req-execute' } }),
    )
    expect(post).toHaveBeenNthCalledWith(
      2,
      '/internal/risk-assistant/tasks/risk-1/reviews',
      review,
      expect.objectContaining({ headers: { 'X-Request-ID': 'req-review' } }),
    )
    expect(post.mock.calls[1]?.[1]).toMatchObject({ checkpoint_version: 2 })
  })

  it('returns the workbook Blob without attempting to decode it as JSON', async () => {
    const workbook = new Blob(['xlsx'], {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    })
    const get = vi.spyOn(http, 'get').mockResolvedValue({ data: workbook })

    await expect(exportRiskWorkbook('risk/1')).resolves.toBe(workbook)

    expect(get).toHaveBeenCalledWith(
      '/internal/risk-assistant/tasks/risk%2F1/export',
      expect.objectContaining({ responseType: 'blob' }),
    )
  })

  it('normalizes checkpoint conflict and permission errors without exposing response details', () => {
    const conflict = new AxiosError(
      'conflict',
      undefined,
      undefined,
      undefined,
      axiosResponse(409, { message: 'risk graph checkpoint version conflict' }),
    )
    const forbidden = new AxiosError(
      'forbidden',
      undefined,
      undefined,
      undefined,
      axiosResponse(403, { message: 'owner_org_unit_id mismatch' }),
    )

    expect(toSafeRiskAssistantError(conflict)).toBe('任务状态已变化，请刷新后重试。')
    expect(toSafeRiskAssistantError(forbidden)).toBe('你没有权限访问该风控任务。')
  })
})
