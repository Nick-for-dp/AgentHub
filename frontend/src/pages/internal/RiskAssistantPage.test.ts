// @vitest-environment happy-dom

import { computed, defineComponent, nextTick, ref } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'

import type { RiskAssessmentTask, RiskTaskSummary } from '../../api/internalRiskAssistant'

const mocks = vi.hoisted(() => ({ useWorkbench: vi.fn() }))
vi.mock('../../composables/useRiskAssistantWorkbench', () => ({
  useRiskAssistantWorkbench: mocks.useWorkbench,
}))

import RiskAssistantPage from './RiskAssistantPage.vue'

const PassThrough = defineComponent({ template: '<div><slot /><slot name="description" /></div>' })
const SpinStub = defineComponent({
  name: 'SpinStub',
  props: { spinning: Boolean },
  template: '<div><slot /></div>',
})
const AlertStub = defineComponent({
  name: 'AlertStub',
  props: ['message', 'description'],
  template: '<div>{{ message }} {{ description }}<slot name="description" /></div>',
})
const EmptyStub = defineComponent({
  name: 'EmptyStub',
  props: ['description'],
  template: '<div>{{ description }}</div>',
})
const SelectStub = defineComponent({
  name: 'SelectStub',
  props: ['value', 'options'],
  emits: ['change'],
  template: '<div />',
})
const PaginationStub = defineComponent({
  name: 'PaginationStub',
  props: ['current', 'pageSize', 'total'],
  emits: ['change'],
  template: '<div />',
})
const PopconfirmStub = defineComponent({
  name: 'PopconfirmStub',
  emits: ['confirm'],
  template: '<div><slot /></div>',
})
const baseStubs = {
  'a-typography-title': PassThrough,
  'a-button': PassThrough,
  'a-select': SelectStub,
  'a-alert': AlertStub,
  'a-spin': SpinStub,
  'a-empty': EmptyStub,
  'a-tag': PassThrough,
  'a-pagination': PaginationStub,
  'a-popconfirm': PopconfirmStub,
  'a-tabs': PassThrough,
  'a-tab-pane': PassThrough,
  PlusOutlined: PassThrough,
  ReloadOutlined: PassThrough,
  DeleteOutlined: PassThrough,
}

function task(status: RiskAssessmentTask['status'] = 'WAITING_REVIEW'): RiskAssessmentTask {
  return {
    id: 'risk-1',
    status,
    agent_code: 'risk-assistant',
    business_code: 'BIZ-001',
    checkpoint_version: 2,
    versions: {},
    documents: [],
    result: { audit_items: [], checks: [], warnings: [], review_items: [] },
    review_context: { audit_items: [], checks: [], warnings: [], review_items: [] },
    review_events: [],
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:01:00+08:00',
  }
}

function summary(): RiskTaskSummary {
  return {
    id: 'risk-1',
    business_code: 'BIZ-001',
    status: 'WAITING_REVIEW',
    document_count: 4,
    created_at: '2026-07-20T10:00:00+08:00',
    updated_at: '2026-07-20T10:01:00+08:00',
  }
}

function workbenchState() {
  const selectedTask = ref<RiskAssessmentTask | null>(task())
  const taskList = ref({
    items: [summary()],
    total: 25,
    page: 1,
    pageSize: 20,
    status: null,
    loading: false,
    errorMessage: null as string | null,
  })
  return {
    businessCode: ref(''),
    files: ref([]),
    packageErrorMessage: ref(null),
    selectedTask,
    detailErrorMessage: ref(null),
    checkpointConflictMessage: ref(null),
    deletingTaskId: ref<string | null>(null),
    operation: ref('IDLE'),
    taskList,
    isTaskBusy: computed(() => false),
    canCreateTask: computed(() => false),
    canRetryExecute: computed(() => false),
    activeReviewItem: computed(() => null),
    auditItems: computed(() => []),
    checks: computed(() => []),
    warnings: computed(() => []),
    addFiles: vi.fn(),
    setDeclaredDocumentType: vi.fn(),
    removeFile: vi.fn(),
    retryFile: vi.fn(),
    createAndExecuteTask: vi.fn(),
    retryExecute: vi.fn(),
    loadTaskList: vi.fn(async () => true),
    loadTask: vi.fn(async () => true),
    deleteTask: vi.fn(async () => true),
    refreshSelectedTask: vi.fn(),
    submitReview: vi.fn(),
    cancelSelectedTask: vi.fn(),
    openSourceDocument: vi.fn(),
    exportSelectedTask: vi.fn(),
    resetPackage: vi.fn(),
    clearSelectedTask: vi.fn(),
  }
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('RiskAssistantPage', () => {
  it('loads a stable route task and renders recent-task pagination', async () => {
    const state = workbenchState()
    mocks.useWorkbench.mockReturnValue(state)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/internal/risk-assistant/tasks/:taskId', component: PassThrough }],
    })
    await router.push('/internal/risk-assistant/tasks/risk-1')
    await router.isReady()

    const wrapper = shallowMount(RiskAssistantPage, {
      global: {
        plugins: [router],
        stubs: baseStubs,
      },
    })
    await nextTick()

    expect(state.loadTask).toHaveBeenCalledWith('risk-1')
    expect(state.loadTaskList).toHaveBeenCalled()
    expect(wrapper.text()).toContain('BIZ-001')
    expect(wrapper.findComponent({ name: 'RiskTaskHeader' }).exists()).toBe(true)
    wrapper.findComponent(SelectStub).vm.$emit('change', 'SUCCEEDED')
    wrapper.findComponent(PaginationStub).vm.$emit('change', 2)
    await nextTick()
    expect(state.loadTaskList).toHaveBeenCalledWith({ page: 1, status: 'SUCCEEDED' })
    expect(state.loadTaskList).toHaveBeenCalledWith({ page: 2 })
  })

  it('reflects loading, empty, and error list states from the centralized composable', async () => {
    const state = workbenchState()
    state.selectedTask.value = null
    state.taskList.value = {
      ...state.taskList.value,
      items: [],
      total: 0,
      loading: true,
      errorMessage: '任务列表加载失败',
    }
    mocks.useWorkbench.mockReturnValue(state)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/internal/risk-assistant', component: PassThrough }],
    })
    await router.push('/internal/risk-assistant')
    await router.isReady()
    const wrapper = shallowMount(RiskAssistantPage, {
      global: { plugins: [router], stubs: baseStubs },
    })

    expect(wrapper.findComponent(SpinStub).props('spinning')).toBe(true)
    expect(wrapper.findComponent(AlertStub).props('message')).toBe('任务列表加载失败')

    state.taskList.value.loading = false
    state.taskList.value.errorMessage = null
    await nextTick()
    expect(wrapper.findComponent(EmptyStub).exists()).toBe(true)
    expect(wrapper.findComponent({ name: 'RiskFilePackagePanel' }).exists()).toBe(true)
  })

  it('confirms deletion, returns from a deleted detail route, and reloads the list', async () => {
    const state = workbenchState()
    mocks.useWorkbench.mockReturnValue(state)
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/internal/risk-assistant', component: PassThrough },
        { path: '/internal/risk-assistant/tasks/:taskId', component: PassThrough },
      ],
    })
    await router.push('/internal/risk-assistant/tasks/risk-1')
    await router.isReady()
    const wrapper = shallowMount(RiskAssistantPage, {
      global: { plugins: [router], stubs: baseStubs },
    })

    wrapper.findComponent(PopconfirmStub).vm.$emit('confirm')
    await flushPromises()

    expect(state.deleteTask).toHaveBeenCalledWith('risk-1')
    expect(router.currentRoute.value.path).toBe('/internal/risk-assistant')
    expect(state.loadTaskList).toHaveBeenCalledWith({ page: 1 })
  })
})
