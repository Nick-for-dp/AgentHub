import { afterEach, describe, expect, it, vi } from 'vitest'

import { http } from './http'
import {
  deleteContractReviewTask,
  listContractReviewTasks,
  type ContractReviewTaskPage,
} from './internalContractReview'

function apiResponse<T>(data: T) {
  return { data: { code: 'OK', message: 'success', data } }
}

afterEach(() => {
  vi.restoreAllMocks()
})

describe('internalContractReview history client', () => {
  it('sends pagination, status, contract type, and trimmed filename filters', async () => {
    const page: ContractReviewTaskPage = {
      items: [],
      total: 0,
      page: 2,
      page_size: 10,
    }
    const get = vi.spyOn(http, 'get').mockResolvedValue(apiResponse(page))

    await expect(listContractReviewTasks({
      page: 2,
      pageSize: 10,
      status: 'SUCCEEDED',
      contractType: 'transport',
      keyword: ' 运输合同 ',
    })).resolves.toEqual(page)

    expect(get).toHaveBeenCalledWith(
      '/internal/contract-review/tasks',
      expect.objectContaining({
        params: {
          page: 2,
          page_size: 10,
          status: 'SUCCEEDED',
          contract_type: 'transport',
          keyword: '运输合同',
        },
      }),
    )
  })

  it('encodes the task id when logically deleting a work record', async () => {
    const result = { id: 'review/1', deleted_at: '2026-07-23T10:00:00+08:00' }
    const deleteRequest = vi.spyOn(http, 'delete').mockResolvedValue(apiResponse(result))

    await expect(deleteContractReviewTask('review/1')).resolves.toEqual(result)

    expect(deleteRequest).toHaveBeenCalledWith(
      '/internal/contract-review/tasks/review%2F1',
      expect.objectContaining({ signal: undefined }),
    )
  })
})
