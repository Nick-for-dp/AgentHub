// @vitest-environment happy-dom

import { defineComponent, nextTick } from 'vue'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

const mocks = vi.hoisted(() => ({
  push: vi.fn(),
  replace: vi.fn(),
  currentRoute: {
    value: {
      meta: {} as Record<string, unknown>,
      query: {} as Record<string, unknown>,
    },
  },
  authState: {
    currentUser: null as { name: string; is_admin?: boolean } | null,
    isLoggedIn: false,
  },
  clearSession: vi.fn(),
  doLogout: vi.fn(),
  ensureFreshSessionForChat: vi.fn(),
  streamChat: vi.fn(),
  createConversation: vi.fn(),
  deleteConversation: vi.fn(),
  getConversation: vi.fn(),
  getConversationMessages: vi.fn(),
  getCurrentConversation: vi.fn(),
  listConversations: vi.fn(),
  exchangeEmbedToken: vi.fn(),
  getEmbedSession: vi.fn(),
  logoutEmbedSession: vi.fn(),
  setEmbedSessionActive: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRouter: () => ({
    currentRoute: mocks.currentRoute,
    push: mocks.push,
    replace: mocks.replace,
  }),
}))

vi.mock('../../stores/auth', () => ({
  useAuthStore: () => ({
    ...mocks.authState,
    clearSession: mocks.clearSession,
    doLogout: mocks.doLogout,
    ensureFreshSessionForChat: mocks.ensureFreshSessionForChat,
  }),
}))

vi.mock('../../api/chat', () => ({
  streamChat: mocks.streamChat,
}))

vi.mock('../../api/conversations', () => ({
  createConversation: mocks.createConversation,
  deleteConversation: mocks.deleteConversation,
  getConversation: mocks.getConversation,
  getConversationMessages: mocks.getConversationMessages,
  getCurrentConversation: mocks.getCurrentConversation,
  listConversations: mocks.listConversations,
}))

vi.mock('../../api/embed', () => ({
  exchangeEmbedToken: mocks.exchangeEmbedToken,
  getEmbedSession: mocks.getEmbedSession,
  logoutEmbedSession: mocks.logoutEmbedSession,
}))

vi.mock('../../utils/embedAuth', () => ({
  setEmbedSessionActive: mocks.setEmbedSessionActive,
}))

import ChatPage from './ChatPage.vue'

const PassThrough = defineComponent({
  template: '<div><slot /><slot name="overlay" /></div>',
})

const ButtonStub = defineComponent({
  inheritAttrs: false,
  props: {
    disabled: Boolean,
    loading: Boolean,
  },
  emits: ['click'],
  template: `
    <button v-bind="$attrs" :disabled="disabled" @click="$emit('click', $event)">
      <slot name="icon" />
      <slot />
    </button>
  `,
})

const TextareaStub = defineComponent({
  props: {
    value: {
      type: String,
      default: '',
    },
    disabled: Boolean,
  },
  emits: ['update:value', 'press-enter'],
  template: `
    <textarea
      :value="value"
      :disabled="disabled"
      @input="$emit('update:value', $event.target.value)"
      @keydown.enter="$emit('press-enter')"
    />
  `,
})

const AlertStub = defineComponent({
  props: {
    message: {
      type: String,
      default: '',
    },
  },
  template: '<div class="error-message">{{ message }}</div>',
})

function mountChatPage() {
  return shallowMount(ChatPage, {
    global: {
      stubs: {
        'a-alert': AlertStub,
        'a-button': ButtonStub,
        'a-collapse': PassThrough,
        'a-collapse-panel': PassThrough,
        'a-dropdown': PassThrough,
        'a-menu': PassThrough,
        'a-menu-divider': defineComponent({ template: '<div />' }),
        'a-menu-item': PassThrough,
        'a-popconfirm': PassThrough,
        'a-textarea': TextareaStub,
        'a-tooltip': PassThrough,
      },
    },
  })
}

function storedConversation(id = 'conversation-1') {
  return {
    id,
    agent_id: 'agent-1',
    agent_code: 'qa',
    user_id: 'user-1',
    title: '历史会话',
    provider: 'dify',
    status: 'ACTIVE',
    last_message_at: '2026-09-21T08:00:00Z',
    created_at: '2026-09-21T08:00:00Z',
    updated_at: '2026-09-21T08:00:00Z',
  }
}

function storedAssistantMessage(
  id: string,
  steps: Array<Record<string, unknown>>,
) {
  return {
    id,
    conversation_id: 'conversation-1',
    sequence_no: 1,
    role: 'ASSISTANT',
    content: '这是历史回答',
    thought: '',
    steps,
    status: 'COMPLETED',
    created_at: '2026-09-21T08:00:00Z',
    updated_at: '2026-09-21T08:00:00Z',
  }
}

async function submitQuestion(wrapper: ReturnType<typeof mountChatPage>, question: string) {
  await wrapper.find('textarea').setValue(question)
  await wrapper.find('.composer-send-button').trigger('click')
}

describe('ChatPage', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.currentRoute.value = { meta: {}, query: {} }
    mocks.authState.currentUser = null
    mocks.authState.isLoggedIn = false
    mocks.ensureFreshSessionForChat.mockResolvedValue(true)
    mocks.getCurrentConversation.mockResolvedValue({
      conversation: null,
      messages: [],
    })
    mocks.listConversations.mockResolvedValue({
      items: [],
      total: 0,
      page: 1,
      page_size: 30,
    })
    mocks.getEmbedSession.mockResolvedValue({
      authenticated: false,
      expires_in: 0,
    })
    mocks.logoutEmbedSession.mockResolvedValue({ revoked: true })
    Object.defineProperty(HTMLElement.prototype, 'scrollIntoView', {
      configurable: true,
      value: vi.fn(),
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the unified sign-in prompt in embed and standard modes', async () => {
    mocks.currentRoute.value.meta = { embed: true }

    const embedPage = mountChatPage()
    await flushPromises()

    expect(embedPage.find('.hint-banner').text()).toContain('请先登录')
    expect(embedPage.text()).not.toContain('请先登录官网')
    embedPage.unmount()

    mocks.currentRoute.value = { meta: {}, query: {} }
    const standardPage = mountChatPage()
    await flushPromises()

    expect(standardPage.find('.hint-banner').text()).toContain('请先登录')
    standardPage.unmount()
  })

  it('shows the generic welcome prompt without exposing the agent code', async () => {
    mocks.authState.currentUser = { name: '测试用户' }
    mocks.authState.isLoggedIn = true

    const wrapper = mountChatPage()
    await flushPromises()

    expect(wrapper.find('.welcome-text').text()).toBe('请提问')
    expect(wrapper.text()).not.toContain('qa')
    expect(wrapper.text()).not.toContain('Agent')
    wrapper.unmount()
  })

  it('keeps restored workflow details collapsed until the summary is expanded', async () => {
    mocks.authState.currentUser = { name: '测试用户' }
    mocks.authState.isLoggedIn = true
    mocks.getCurrentConversation.mockResolvedValue({
      conversation: storedConversation(),
      messages: [
        storedAssistantMessage('finished-message', [
          {
            node_id: 'retrieval-1',
            node_type: 'knowledge-retrieval',
            title: '检索知识库',
            status: 'finished',
            elapsed_time: 0.4,
          },
        ]),
        storedAssistantMessage('failed-message', [
          {
            node_id: 'answer-1',
            node_type: 'code',
            title: '生成回答',
            status: 'failed',
            elapsed_time: 1.2,
          },
        ]),
      ],
    })

    const wrapper = mountChatPage()
    await flushPromises()

    const summaries = wrapper.findAll('.workflow-summary')
    expect(summaries).toHaveLength(2)
    expect(summaries[0].text()).toContain('已完成')
    expect(summaries[0].text()).not.toContain('最近完成')
    expect(summaries[0].find('.workflow-detail').exists()).toBe(false)
    expect(summaries[1].text()).toContain('工作流执行失败')
    expect(summaries[1].find('.workflow-detail').text()).toBe('失败节点：生成回答')
    expect(wrapper.findAll('.step-list')).toHaveLength(0)
    expect(summaries[0].attributes('aria-expanded')).toBe('false')

    await summaries[0].trigger('click')
    await nextTick()

    expect(wrapper.findAll('.step-list')).toHaveLength(1)
    expect(wrapper.find('.step-list').text()).toContain('检索知识库')
    expect(summaries[0].attributes('aria-expanded')).toBe('true')
    wrapper.unmount()
  })

  it('shows the customer-facing running title', async () => {
    vi.useFakeTimers()
    mocks.authState.currentUser = { name: '测试用户' }
    mocks.authState.isLoggedIn = true
    mocks.streamChat.mockImplementation(
      async (
        _agentCode: string,
        _payload: unknown,
        onEvent: (event: Record<string, unknown>) => void,
      ) => {
        onEvent({
          event: 'node_started',
          node: {
            node_id: 'retrieval-1',
            node_type: 'knowledge-retrieval',
            title: '检索知识库',
            status: 'running',
          },
        })
      },
    )

    const wrapper = mountChatPage()
    await flushPromises()
    await submitQuestion(wrapper, '金华有仓库吗？')
    await flushPromises()
    await vi.advanceTimersByTimeAsync(520)
    await nextTick()

    expect(wrapper.find('.workflow-title').text()).toBe('正在搜索')
    expect(wrapper.find('.workflow-detail').text()).toBe('正在处理：检索知识库')
    expect(wrapper.find('.step-list').exists()).toBe(false)
    wrapper.unmount()
  })

  it.each([403, 503, 500])(
    'shows only the unified message for a %s stream error',
    async (status) => {
      mocks.authState.currentUser = { name: '测试用户' }
      mocks.authState.isLoggedIn = true
      mocks.streamChat.mockRejectedValue({
        status,
        message: `内部错误 ${status}`,
      })

      const wrapper = mountChatPage()
      await flushPromises()
      await submitQuestion(wrapper, '测试问题')
      await flushPromises()

      expect(wrapper.find('.error-message').text()).toBe('抱歉，出错了')
      expect(wrapper.text()).not.toContain(`内部错误 ${status}`)
      wrapper.unmount()
    },
  )

  it('still clears the session and redirects on a 401 stream error', async () => {
    mocks.authState.currentUser = { name: '测试用户' }
    mocks.authState.isLoggedIn = true
    mocks.streamChat.mockRejectedValue({
      status: 401,
      message: '会话已过期',
    })

    const wrapper = mountChatPage()
    await flushPromises()
    await submitQuestion(wrapper, '测试问题')
    await flushPromises()

    expect(wrapper.find('.error-message').text()).toBe('抱歉，出错了')
    expect(mocks.clearSession).toHaveBeenCalledTimes(1)
    expect(mocks.push).toHaveBeenCalledWith('/login')
    expect(wrapper.text()).not.toContain('会话已过期')
    wrapper.unmount()
  })
})
