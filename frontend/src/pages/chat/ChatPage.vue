<template>
  <main class="chat-page">
    <!-- 历史会话侧边栏 -->
    <aside
      v-if="auth.isLoggedIn"
      :class="['conversation-sidebar', {
        'sidebar-open': sidebarVisible,
        'sidebar-collapsed': !sidebarVisible,
        'sidebar-mobile': isMobile
      }]"
    >
      <div class="sidebar-header">
        <span class="sidebar-title">历史会话</span>
      </div>
      <div class="sidebar-list">
        <div
          v-for="conv in conversationList"
          :key="conv.id"
          :class="['sidebar-item', {
            active: conv.id === conversationId,
            switching: conv.id === switchingConversationId,
          }]"
          @click="switchConversation(conv.id)"
        >
          <span class="sidebar-item-main">
            <span class="sidebar-item-title">{{ conv.title || '新对话' }}</span>
            <span class="sidebar-item-time">{{ formatTime(conv.last_message_at) }}</span>
          </span>
          <a-popconfirm
            title="确认删除该会话？"
            ok-text="删除"
            cancel-text="取消"
            placement="right"
            @confirm="deleteConversationItem(conv.id)"
          >
            <button
              type="button"
              class="sidebar-delete-btn"
              title="删除会话"
              :disabled="deletingConversationId === conv.id"
              @click.stop
            >
              <DeleteOutlined />
            </button>
          </a-popconfirm>
        </div>
        <div v-if="conversationList.length === 0 && !loadingConversations" class="sidebar-empty">
          暂无历史会话
        </div>
        <div v-if="loadingConversations" class="sidebar-loading">
          正在加载...
        </div>
        <a-button
          v-else-if="hasMoreConversations"
          block
          size="small"
          class="sidebar-load-more"
          @click="loadMoreConversations"
        >
          加载更多
        </a-button>
      </div>
    </aside>

    <!-- 移动端遮罩 -->
    <div
      v-if="isMobile && sidebarVisible"
      class="sidebar-overlay"
      @click="sidebarVisible = false"
    />

    <section :class="['chat-panel', { 'sidebar-hidden-panel': !auth.isLoggedIn || !sidebarVisible }]">
      <!-- 顶栏 -->
      <header class="chat-header">
        <div class="header-left">
          <button
            v-if="auth.isLoggedIn"
            type="button"
            class="sidebar-toggle-btn"
            :title="sidebarVisible ? '收起历史会话' : '展开历史会话'"
            :aria-label="sidebarVisible ? '收起历史会话' : '展开历史会话'"
            @click="sidebarVisible = !sidebarVisible"
          >
            <MenuOutlined />
          </button>
          <span class="header-title">智能问答</span>
        </div>

        <div class="header-right">
          <a-tooltip title="新对话">
            <a-button
            v-if="auth.isLoggedIn"
            shape="circle"
            :disabled="loading || restoringConversation"
            class="header-icon-button"
            aria-label="新对话"
            @click="handleNewConversation"
            >
              <template #icon>
                <PlusOutlined />
              </template>
            </a-button>
          </a-tooltip>
          <template v-if="auth.isLoggedIn && auth.currentUser">
            <a-dropdown trigger="click" placement="bottomRight">
              <button type="button" class="user-avatar-button" :title="auth.currentUser.name">
                <span class="user-avatar">{{ getUserInitial(auth.currentUser.name) }}</span>
              </button>
              <template #overlay>
                <a-menu>
                  <a-menu-item key="user" disabled>
                    {{ auth.currentUser.name }}
                  </a-menu-item>
                  <a-menu-divider />
                  <a-menu-item key="logout" @click="handleLogout">
                    退出登录
                  </a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </template>
        </div>
      </header>

      <!-- 消息区 -->
      <div ref="msgContainer" class="messages">
        <!-- 未登录时的引导提示 -->
        <div v-if="!canChat" class="hint-banner">
          <a-button type="primary" @click="$router.push('/login')">请先登录</a-button>
        </div>

        <!-- 无消息时的欢迎 -->
        <div v-else-if="messages.length === 0 && !loading" class="welcome-banner">
          <RobotOutlined class="welcome-icon" />
          <p class="welcome-text">向「{{ agentCode }}」Agent 提问</p>
          <p class="welcome-hint">{{ restoringConversation ? '正在恢复对话...' : '智能问答助手已就绪' }}</p>
        </div>

        <div
          v-for="msg in messages"
          :key="msg.id"
          :data-message-id="msg.id"
          :class="['message', msg.role]"
        >
          <!-- 智能体过程步骤 -->
          <div v-if="msg.role === 'assistant' && (msg.steps.length > 0 || msg.isStreaming)" class="steps-section">
            <button
              type="button"
              :class="['workflow-summary', getWorkflowStatus(msg)]"
              :aria-expanded="expandedSteps[msg.id] ? 'true' : 'false'"
              @click="msg.steps.length > 0 && (expandedSteps[msg.id] = !expandedSteps[msg.id])"
            >
              <span class="workflow-status-icon">
                <LoadingOutlined v-if="isWorkflowRunning(msg)" spin />
                <CloseCircleFilled v-else-if="getWorkflowStatus(msg) === 'failed'" />
                <CheckCircleFilled v-else />
              </span>
              <span class="workflow-copy">
                <span class="workflow-title">{{ getWorkflowTitle(msg) }}</span>
                <span class="workflow-detail">{{ getWorkflowDetail(msg) }}</span>
              </span>
              <span class="workflow-count">{{ getWorkflowCountText(msg) }}</span>
              <DownOutlined
                v-if="msg.steps.length > 0"
                :class="['workflow-chevron', { expanded: expandedSteps[msg.id] }]"
              />
            </button>
            <div v-if="msg.steps.length > 0 && expandedSteps[msg.id]" class="step-list">
              <div
                v-for="step in msg.steps"
                :key="step.id || step.title"
                :class="['step-item', step.status]"
              >
                <span class="step-dot"></span>
                <span class="step-title">{{ step.title }}</span>
                <span class="step-status">{{ getStepStatusText(step.status) }}</span>
                <span v-if="step.elapsedTime != null" class="step-time">{{ step.elapsedTime.toFixed(1) }}s</span>
              </div>
            </div>
          </div>
          <!-- 步骤与回答的分隔线 -->
          <div v-if="msg.role === 'assistant' && (msg.steps.length > 0 || msg.isStreaming) && msg.content" class="steps-divider"></div>
          <!-- 思考过程：可折叠 -->
          <div v-if="msg.displayThought" class="thought-section">
            <a-collapse :activeKey="thoughtOpen ? ['thought'] : []" ghost>
              <a-collapse-panel key="thought" header="思考过程">
                <div class="thought-content">{{ msg.displayThought }}</div>
              </a-collapse-panel>
            </a-collapse>
          </div>
          <!-- 回答内容：Markdown 渲染 + 打字机效果 -->
          <div
            v-if="msg.role === 'assistant' && msg.displayContent"
            class="markdown-body"
            v-html="renderMarkdown(msg.displayContent ?? msg.content)"
          />
          <!-- 用户消息：纯文本 -->
          <template v-else>
            {{ msg.content }}
          </template>
          <!-- 语音播报按钮 -->
          <div
            v-if="msg.role === 'assistant' && msg.content && synth.isSupported.value"
            class="speech-actions"
          >
            <a-button
              size="small"
              type="link"
              :loading="synth.isLoading.value"
              :title="synth.isSpeaking.value ? '停止播报' : '播报回复'"
              @click="toggleSpeechOutput(msg.content)"
            >
              <template v-if="synth.isSpeaking.value">
                <PauseCircleOutlined /> 停止
              </template>
              <template v-else>
                <SoundOutlined /> 播报
              </template>
            </a-button>
          </div>
        </div>

      </div>

      <!-- 错误提示 -->
      <a-alert
        v-if="errorMsg"
        type="error"
        :message="errorMsg"
        show-icon
        closable
        class="error-bar"
        @close="errorMsg = ''"
      />

      <!-- 输入区 -->
      <footer class="composer">
        <a-textarea
          v-model:value="question"
          class="composer-input"
          :auto-size="{ minRows: 1, maxRows: 4 }"
          :placeholder="speechPlaceholder"
          :disabled="!canChat || speech.isRecording.value || speech.isTranscribing.value"
          @press-enter.prevent="safeSend"
        />
        <a-button
          v-if="speech.isSupported.value"
          :type="speech.isRecording.value ? 'primary' : 'default'"
          :danger="speech.isRecording.value"
          :loading="speech.isTranscribing.value"
          :title="speech.isRecording.value ? '松开结束录音' : '长按语音输入'"
          size="large"
          class="composer-icon-button"
          @mousedown.prevent="startSpeechInput"
          @mouseup.prevent="stopSpeechInput"
          @mouseleave.prevent="stopSpeechInput"
          @touchstart.prevent="startSpeechInput"
          @touchend.prevent="stopSpeechInput"
        >
          <template #icon>
            <PauseCircleOutlined v-if="speech.isRecording.value" />
            <AudioOutlined v-else />
          </template>
        </a-button>
        <a-button
          type="primary"
          :loading="loading"
          :disabled="!canChat || (!question.trim() && !speech.transcript.value)"
          size="large"
          class="composer-send-button"
          @click="safeSend"
        >
          发送
        </a-button>
      </footer>
    </section>
  </main>
</template>

<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import {
  AudioOutlined,
  CheckCircleFilled,
  CloseCircleFilled,
  DeleteOutlined,
  DownOutlined,
  LoadingOutlined,
  MenuOutlined,
  PauseCircleOutlined,
  PlusOutlined,
  RobotOutlined,
  SoundOutlined,
} from '@ant-design/icons-vue'
import { marked } from 'marked'
import DOMPurify from 'dompurify'

import { streamChat } from '../../api/chat'
import type { ChatError, StreamEvent } from '../../api/chat'
import {
  createConversation,
  deleteConversation,
  getConversation,
  getConversationMessages,
  getCurrentConversation,
  listConversations,
} from '../../api/conversations'
import type { Conversation, ConversationMessage } from '../../api/conversations'
import { useAuthStore } from '../../stores/auth'
import { useCloudSpeechRecognition } from '../../composables/useCloudSpeechRecognition'
import { useCloudSpeechSynthesis } from '../../composables/useCloudSpeechSynthesis'

// 配置 marked
marked.setOptions({ breaks: true, gfm: true })

// 配置 DOMPurify：链接安全策略
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node instanceof HTMLAnchorElement) {
    node.setAttribute('target', '_blank')
    node.setAttribute('rel', 'noopener noreferrer')
  }
})

function renderMarkdown(text: string): string {
  if (!text) return ''
  const rawHtml = marked(text) as string
  return DOMPurify.sanitize(rawHtml, { ALLOWED_TAGS: [
    'h1','h2','h3','h4','h5','h6',
    'p','br','hr',
    'ul','ol','li',
    'blockquote','pre','code',
    'table','thead','tbody','tr','th','td',
    'strong','em','del','ins','s',
    'a','img',
    'span','div',
  ]})
}

interface Step {
  id: string
  title: string
  emoji: string
  color: string
  status: 'running' | 'finished' | 'failed' | 'retry'
  elapsedTime?: number
  visibleAt?: number
}

type StepStatus = Step['status']

interface NodeEventPayload {
  node_id?: string
  node_type?: string
  title?: string
  status?: string
  elapsed_time?: number
  event?: string
}

interface QueuedStep {
  message: Message
  id: string
  title: string
  emoji: string
  color: string
  status: StepStatus
  elapsedTime?: number
  finalStatus?: StepStatus
  finalElapsedTime?: number
}

/** 根据节点类型/标题决定是否展示及对应 emoji 与颜色。返回 null 表示跳过该节点。 */
function getStepMeta(node: { node_type?: string; title?: string }): { emoji: string; color: string } | null {
  const type = node.node_type || ''
  const title = node.title || ''
  // 不展示的节点：workflow 占位、用户输入、结束、条件分支、最终回复。
  if (!type && !title) return null
  if (type === 'start' || type === 'end' || type === 'answer') return null
  if (title === '处理中') return null
  if (title.includes('用户输入') || title === '开始' || title === '结束') return null
  if (title.includes('条件分支') || title.includes('条件判断') || type === 'if-else') return null
  if (
    title === 'answer'
    || title.includes('智能回复')
    || title.includes('智能问答回复')
    || title.includes('直接回复')
  ) return null
  // 按标题关键词匹配
  if (title.includes('意图') || title.includes('识别')) return { emoji: '🎯', color: '#722ed1' }
  if (title.includes('润色') || title.includes('改写') || title.includes('重写')) return { emoji: '✨', color: '#fa8c16' }
  if (title.includes('知识库') || title.includes('检索')) return { emoji: '📚', color: '#1677ff' }
  // 按节点类型匹配
  if (type === 'knowledge-retrieval') return { emoji: '📚', color: '#1677ff' }
  if (type === 'llm') return { emoji: '🤖', color: '#52c41a' }
  if (type === 'http-request') return { emoji: '🌐', color: '#13c2c2' }
  if (type === 'code') return { emoji: '💻', color: '#eb2f96' }
  // 其他类型默认展示
  return { emoji: '⚙️', color: '#8c8c8c' }
}

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  thought: string
  displayContent: string | null
  displayThought: string
  steps: Step[]
  isStreaming: boolean
}

function buildStoredSteps(rawSteps: Array<Record<string, unknown>> | undefined): Step[] {
  if (!rawSteps?.length) return []
  const result: Step[] = []
  const seen = new Set<string>()
  for (const raw of rawSteps) {
    const node = raw as NodeEventPayload
    const meta = getStepMeta(node)
    if (!meta) continue
    const { id, title } = getNodeIdentity(node)
    const status: StepStatus = node.status === 'failed' ? 'failed' : 'finished'
    const existing = result.find(step => step.id === id || step.title === title)
    if (existing) {
      existing.status = status
      existing.elapsedTime = node.elapsed_time
      continue
    }
    if (seen.has(id)) continue
    seen.add(id)
    result.push({
      id,
      title,
      emoji: meta.emoji,
      color: meta.color,
      status,
      elapsedTime: node.elapsed_time,
    })
  }
  return result
}

function isWorkflowRunning(message: Message): boolean {
  return message.isStreaming || message.steps.some(step => step.status === 'running' || step.status === 'retry')
}

function getWorkflowStatus(message: Message): 'running' | 'finished' | 'failed' {
  if (message.steps.some(step => step.status === 'failed')) return 'failed'
  return isWorkflowRunning(message) ? 'running' : 'finished'
}

function getWorkflowTitle(message: Message): string {
  const status = getWorkflowStatus(message)
  if (status === 'failed') return '工作流执行失败'
  if (status === 'finished') return '工作流已完成'
  return '工作流正在执行'
}

function getWorkflowDetail(message: Message): string {
  const latest = message.steps[message.steps.length - 1]
  if (!latest) return '正在准备处理流程'
  if (latest.status === 'running') return `正在处理：${latest.title}`
  if (latest.status === 'retry') return `正在重试：${latest.title}`
  if (latest.status === 'failed') return `失败节点：${latest.title}`
  return `最近完成：${latest.title}`
}

function getWorkflowCountText(message: Message): string {
  return message.steps.length > 0 ? `${message.steps.length} 步` : '准备中'
}

function getStepStatusText(status: StepStatus): string {
  const statusText: Record<StepStatus, string> = {
    running: '进行中',
    finished: '已完成',
    failed: '失败',
    retry: '重试中',
  }
  return statusText[status]
}

function getUserInitial(name: string): string {
  return name.trim().slice(0, 1).toUpperCase() || '用'
}

function mapConversationMessage(item: ConversationMessage): Message | null {
  if (item.role === 'SYSTEM') return null
  const role = item.role === 'USER' ? 'user' : 'assistant'
  return {
    id: item.id,
    role,
    content: item.content,
    thought: item.thought || '',
    displayContent: role === 'assistant' ? item.content : '',
    displayThought: item.thought || '',
    steps: role === 'assistant' ? buildStoredSteps(item.steps) : [],
    isStreaming: false,
  }
}

const router = useRouter()
const auth = useAuthStore()
const canChat = computed(() => auth.isLoggedIn)
const agentCode = ref('qa')
const question = ref('')
const loading = ref(false)
const restoringConversation = ref(false)
const errorMsg = ref('')
const messages = ref<Message[]>([])
const msgContainer = ref<HTMLElement | null>(null)
const thoughtOpen = ref(true)
const expandedSteps = ref<Record<string, boolean>>({})
const conversationId = ref<string | null>(null)
const conversationTitle = ref('')
const conversationList = ref<Conversation[]>([])
const loadingConversations = ref(false)
const conversationPage = ref(1)
const conversationTotal = ref(0)
const conversationPageSize = 30
const switchingConversationId = ref<string | null>(null)
const deletingConversationId = ref<string | null>(null)
let switchRequestSeq = 0
const hasMoreConversations = computed(() => conversationList.value.length < conversationTotal.value)
const windowWidth = ref(window.innerWidth)
const isMobile = computed(() => windowWidth.value < 768)
const sidebarVisible = ref(window.innerWidth >= 768)
// 语音能力
const speech = useCloudSpeechRecognition()
const synth = useCloudSpeechSynthesis()
const speechPlaceholder = computed(() => {
  if (speech.isRecording.value) return '正在录音，松开发送识别'
  if (speech.isTranscribing.value) return '正在转写语音...'
  return '输入问题，Enter 发送'
})

// 节点事件通常会在几十毫秒内连续到达。这里用前端队列把步骤逐个展示，
// 同时保证每一步至少可见一小段时间，避免用户看到“一整串步骤瞬间出现”。
const STEP_REVEAL_GAP_MS = 520
const STEP_MIN_VISIBLE_MS = 700
const queuedSteps: QueuedStep[] = []
const stepTimers = new Set<ReturnType<typeof setTimeout>>()
let isDrainingStepQueue = false
let scrollTimer: ReturnType<typeof setTimeout> | null = null

function syncConversationUrl(id: string | null): void {
  const query = { ...router.currentRoute.value.query }
  if (id) {
    query.conversation_id = id
  } else {
    delete query.conversation_id
  }
  void router.replace({ query })
}

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const isToday = date.toDateString() === now.toDateString()
  if (isToday) {
    return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })
  }
  return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' })
}

function mergeConversationList(items: Conversation[], append: boolean): void {
  const existing = append ? conversationList.value : []
  const byId = new Map(existing.map(item => [item.id, item]))
  for (const item of items) {
    byId.set(item.id, item)
  }
  conversationList.value = Array.from(byId.values()).sort(
    (a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime(),
  )
}

async function loadConversationList(page = 1, append = false): Promise<void> {
  if (!auth.isLoggedIn) return
  loadingConversations.value = true
  try {
    const result = await listConversations(agentCode.value, page, conversationPageSize)
    conversationPage.value = result.page
    conversationTotal.value = result.total
    mergeConversationList(result.items, append)
  } catch {
    // 静默失败，不影响聊天主体验
  } finally {
    loadingConversations.value = false
  }
}

async function refreshConversationList(): Promise<void> {
  await loadConversationList(1, false)
}

async function loadMoreConversations(): Promise<void> {
  if (loadingConversations.value || !hasMoreConversations.value) return
  await loadConversationList(conversationPage.value + 1, true)
}

async function deleteConversationItem(id: string): Promise<void> {
  if (deletingConversationId.value || loading.value) return
  deletingConversationId.value = id
  errorMsg.value = ''
  try {
    await deleteConversation(id)
    conversationList.value = conversationList.value.filter(item => item.id !== id)
    conversationTotal.value = Math.max(0, conversationTotal.value - 1)
    if (conversationId.value === id) {
      conversationId.value = null
      conversationTitle.value = ''
      messages.value = []
      expandedSteps.value = {}
      syncConversationUrl(null)
    }
  } catch {
    errorMsg.value = '删除会话失败，请稍后重试'
  } finally {
    deletingConversationId.value = null
  }
}

async function switchConversation(id: string): Promise<void> {
  if (id === conversationId.value || loading.value) return
  const requestSeq = ++switchRequestSeq
  switchingConversationId.value = id
  errorMsg.value = ''
  if (isMobile.value) {
    sidebarVisible.value = false
  }
  try {
    const [conversation, storedMessages] = await Promise.all([
      getConversation(id),
      getConversationMessages(id),
    ])
    if (requestSeq !== switchRequestSeq) return
    if (conversation.agent_code !== agentCode.value) {
      throw new Error('conversation agent mismatch')
    }
    conversationId.value = conversation.id
    conversationTitle.value = conversation.title
    messages.value = storedMessages
      .map(mapConversationMessage)
      .filter((item): item is Message => item !== null)
    syncConversationUrl(conversation.id)
    await scrollBottom()
  } catch {
    if (requestSeq !== switchRequestSeq) return
    errorMsg.value = '切换会话失败，请稍后重试'
  } finally {
    if (requestSeq === switchRequestSeq) {
      switchingConversationId.value = null
    }
  }
}

async function restoreCurrentConversation(): Promise<void> {
  if (!auth.isLoggedIn) return
  restoringConversation.value = true
  try {
    const routeConversationId = router.currentRoute.value.query.conversation_id
    const requestedId = typeof routeConversationId === 'string' ? routeConversationId : null
    let currentState = requestedId ? null : await getCurrentConversation(agentCode.value)
    let current = requestedId ? await getConversation(requestedId) : currentState?.conversation
    let storedMessages = requestedId
      ? await getConversationMessages(requestedId)
      : currentState?.messages ?? []
    if (current && current.agent_code !== agentCode.value) {
      syncConversationUrl(null)
      currentState = await getCurrentConversation(agentCode.value)
      current = currentState.conversation
      storedMessages = currentState.messages
    }
    conversationId.value = current?.id ?? null
    conversationTitle.value = current?.title ?? ''
    messages.value = storedMessages
      .map(mapConversationMessage)
      .filter((item): item is Message => item !== null)
    syncConversationUrl(conversationId.value)
    await scrollBottom()
  } catch {
    errorMsg.value = '恢复对话失败，请稍后重试'
  } finally {
    restoringConversation.value = false
  }
}

async function handleNewConversation(): Promise<void> {
  if (loading.value) return
  errorMsg.value = ''
  const conversation = await createConversation(agentCode.value)
  conversationId.value = conversation.id
  conversationTitle.value = conversation.title
  messages.value = []
  expandedSteps.value = {}
  syncConversationUrl(conversation.id)
  await scrollBottom()
  if (isMobile.value) {
    sidebarVisible.value = false
  }
  await refreshConversationList()
}

function scheduleStepTimer(callback: () => void, delayMs: number): void {
  const timer = setTimeout(() => {
    stepTimers.delete(timer)
    callback()
  }, delayMs)
  stepTimers.add(timer)
}

function waitForStepTimer(delayMs: number): Promise<void> {
  return new Promise(resolve => scheduleStepTimer(resolve, delayMs))
}

function getNodeIdentity(node: NodeEventPayload): { id: string; title: string } {
  const title = node.title || node.node_type || '处理中'
  return {
    id: node.node_id || title,
    title,
  }
}

function findVisibleStep(message: Message, id: string, title: string): Step | undefined {
  return message.steps.find(step => step.id === id || step.title === title)
}

function findQueuedStep(message: Message, id: string, title: string): QueuedStep | undefined {
  return queuedSteps.find(step => step.message.id === message.id && (step.id === id || step.title === title))
}

function mergeQueuedStep(queued: QueuedStep, status: StepStatus, elapsedTime?: number): void {
  if (status === 'finished' || status === 'failed') {
    queued.finalStatus = status
    queued.finalElapsedTime = elapsedTime
    return
  }
  queued.status = status
  queued.elapsedTime = elapsedTime
}

function applyVisibleStepUpdate(step: Step, status: StepStatus, elapsedTime?: number): void {
  step.status = status
  step.elapsedTime = elapsedTime
}

function finishVisibleStepAfterMinimum(step: Step, status: StepStatus, elapsedTime?: number): void {
  const visibleAt = step.visibleAt ?? Date.now()
  const remainingMs = Math.max(0, STEP_MIN_VISIBLE_MS - (Date.now() - visibleAt))
  scheduleStepTimer(() => {
    applyVisibleStepUpdate(step, status, elapsedTime)
    scrollLatestMessageIntoView('smooth')
  }, remainingMs)
}

async function drainStepQueue(): Promise<void> {
  if (isDrainingStepQueue) return
  isDrainingStepQueue = true
  try {
    while (queuedSteps.length > 0) {
      const queued = queuedSteps.shift()
      if (!queued || !messages.value.some(message => message.id === queued.message.id)) {
        continue
      }

      const existing = findVisibleStep(queued.message, queued.id, queued.title)
      const step = existing ?? {
        id: queued.id,
        title: queued.title,
        emoji: queued.emoji,
        color: queued.color,
        status: queued.status,
        elapsedTime: queued.elapsedTime,
        visibleAt: Date.now(),
      }
      if (!existing) {
        queued.message.steps.push(step)
      } else {
        applyVisibleStepUpdate(step, queued.status, queued.elapsedTime)
      }

      scrollLatestMessageIntoView('smooth')
      if (queued.finalStatus) {
        finishVisibleStepAfterMinimum(step, queued.finalStatus, queued.finalElapsedTime)
      }
      await waitForStepTimer(STEP_REVEAL_GAP_MS)
    }
  } finally {
    isDrainingStepQueue = false
    if (queuedSteps.length > 0) {
      void drainStepQueue()
    }
  }
}

function enqueueStepUpdate(message: Message, node: NodeEventPayload, eventName?: string): void {
  if (eventName === 'workflow_started' || eventName === 'workflow_finished') return

  const meta = getStepMeta(node)
  if (!meta) return

  const { id, title } = getNodeIdentity(node)
  const status: StepStatus = eventName === 'node_finished'
    ? (node.status === 'failed' ? 'failed' : 'finished')
    : eventName === 'node_retry'
      ? 'retry'
      : 'running'

  const visible = findVisibleStep(message, id, title)
  if (visible) {
    if (status === 'finished' || status === 'failed') {
      finishVisibleStepAfterMinimum(visible, status, node.elapsed_time)
    } else {
      applyVisibleStepUpdate(visible, status, node.elapsed_time)
    }
    return
  }

  const queued = findQueuedStep(message, id, title)
  if (queued) {
    mergeQueuedStep(queued, status, node.elapsed_time)
    return
  }

  queuedSteps.push({
    message,
    id,
    title,
    emoji: meta.emoji,
    color: meta.color,
    status: status === 'finished' || status === 'failed' ? 'running' : status,
    elapsedTime: status === 'finished' || status === 'failed' ? undefined : node.elapsed_time,
    finalStatus: status === 'finished' || status === 'failed' ? status : undefined,
    finalElapsedTime: status === 'finished' || status === 'failed' ? node.elapsed_time : undefined,
  })
  void drainStepQueue()
}

// 语音输入：长按录音，松开后将云端识别结果填入输入框
function startSpeechInput(): void {
  if (speech.isRecording.value || speech.isTranscribing.value || !canChat.value) return
  speech.clearTranscript()
  void speech.start({
    onEnd: (text) => {
      void finishSpeechInput(text)
    },
    onError: (error) => {
      errorMsg.value = getSpeechErrorMessage(error)
    },
  })
}

function stopSpeechInput(): void {
  if (!speech.isRecording.value) return
  void speech.stop()
}

function finishSpeechInput(text: string): void {
  const recognizedText = (text || speech.transcript.value).trim()
  if (!recognizedText) {
    speech.clearTranscript()
    return
  }
  question.value = recognizedText
  speech.clearTranscript()
}

function getSpeechErrorMessage(error: string): string {
  if (error.includes('Permission') || error.includes('NotAllowed')) {
    return '浏览器未允许使用麦克风，请检查权限设置'
  }
  if (error.includes('uploaded WAV')) {
    return '录音格式不符合要求，请重试'
  }
  return error || '语音输入失败，请重试'
}

// 语音播报：播放/停止
function toggleSpeechOutput(text: string): void {
  if (synth.isSpeaking.value) {
    synth.stop()
  } else {
    void synth.speak(text)
  }
}

// 发送新问题时停止播报
async function safeSend(): Promise<void> {
  synth.stop()
  await send()
}

// ── 打字机效果 ──────────────────────────────
const typewriterTimer = ref<ReturnType<typeof setInterval> | null>(null)
const typewriterCursors = ref<Map<string, number>>(new Map())

function startTypewriter() {
  typewriterTimer.value = setInterval(() => {
    let anyTyping = false
    for (const msg of messages.value) {
      if (msg.role !== 'assistant') continue
      let cursor = typewriterCursors.value.get(msg.id) ?? (msg.displayContent?.length ?? 0)
      if (cursor < msg.content.length) {
        // 自适应步长：长文本一次多输出几个字符，保证约 1.5 秒打完
        const chunkSize = Math.max(1, Math.floor(msg.content.length / 50))
        cursor = Math.min(msg.content.length, cursor + chunkSize)
        msg.displayContent = msg.content.slice(0, cursor)
        typewriterCursors.value.set(msg.id, cursor)
        anyTyping = true
      }

      const thoughtKey = `${msg.id}:thought`
      let thoughtCursor = typewriterCursors.value.get(thoughtKey) ?? msg.displayThought.length
      if (thoughtCursor < msg.thought.length) {
        const chunkSize = Math.max(1, Math.floor(msg.thought.length / 80))
        thoughtCursor = Math.min(msg.thought.length, thoughtCursor + chunkSize)
        msg.displayThought = msg.thought.slice(0, thoughtCursor)
        typewriterCursors.value.set(thoughtKey, thoughtCursor)
        anyTyping = true
      }
    }
    // 流未结束时不停止，避免内容尚未到达时 timer 自杀
    if (!anyTyping && !loading.value && typewriterTimer.value) {
      clearInterval(typewriterTimer.value)
      typewriterTimer.value = null
    }
  }, 30)
}

function stopTypewriter() {
  if (typewriterTimer.value) {
    clearInterval(typewriterTimer.value)
    typewriterTimer.value = null
  }
  // 全部显示完整内容
  for (const msg of messages.value) {
    if (msg.role === 'assistant' && msg.content) {
      msg.displayContent = msg.content
    }
    if (msg.role === 'assistant' && msg.thought) {
      msg.displayThought = msg.thought
    }
  }
  typewriterCursors.value.clear()
}

function onWindowResize(): void {
  const wasMobile = isMobile.value
  windowWidth.value = window.innerWidth
  if (wasMobile && !isMobile.value) {
    sidebarVisible.value = true
  }
}

onMounted(() => {
  window.addEventListener('resize', onWindowResize)
  void restoreCurrentConversation()
  if (auth.isLoggedIn) {
    void refreshConversationList()
  }
})

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize)
  if (scrollTimer) {
    clearTimeout(scrollTimer)
    scrollTimer = null
  }
  queuedSteps.length = 0
  for (const timer of stepTimers) {
    clearTimeout(timer)
  }
  stepTimers.clear()
  stopTypewriter()
  synth.stop()
})

async function handleLogout() {
  await auth.doLogout()
  router.push('/login')
}

// ── 滚动 ───────────────────────────────────
async function scrollLatestMessageIntoView(behavior: ScrollBehavior = 'auto') {
  await nextTick()
  const container = msgContainer.value
  if (!container) return

  const messageNodes = container.querySelectorAll<HTMLElement>('.message')
  const latestMessage = messageNodes[messageNodes.length - 1]
  if (latestMessage) {
    latestMessage.scrollIntoView({ block: 'center', inline: 'nearest', behavior })
  } else {
    container.scrollTop = container.scrollHeight
  }
}

async function scrollBottom() {
  await scrollLatestMessageIntoView('auto')
}

function scheduleScrollLatest(behavior: ScrollBehavior = 'auto'): void {
  if (scrollTimer) return
  scrollTimer = setTimeout(() => {
    scrollTimer = null
    void scrollLatestMessageIntoView(behavior)
  }, 80)
}

// ── 发送消息 ───────────────────────────────
async function send() {
  const current = (question.value || speech.transcript.value).trim()
  if (!current || loading.value || !canChat.value) return
  question.value = current
  speech.clearTranscript()

  errorMsg.value = ''
  thoughtOpen.value = true

  const sessionReady = await auth.ensureFreshSessionForChat()
  if (!sessionReady) {
    errorMsg.value = '登录已失效，请重新登录'
    router.push('/login')
    return
  }

  const userMsg: Message = {
    id: crypto.randomUUID(),
    role: 'user',
    content: current,
    thought: '',
    displayContent: '',
    displayThought: '',
    steps: [],
    isStreaming: false,
  }
  const assistantMsg: Message = {
    id: crypto.randomUUID(),
    role: 'assistant',
    content: '',
    thought: '',
    displayContent: '',
    displayThought: '',
    steps: [],
    isStreaming: true,
  }
  messages.value.push(userMsg, assistantMsg)
  question.value = ''
  loading.value = true
  startTypewriter()
  await scrollBottom()

  try {
    await streamChat(
      agentCode.value,
      { question: current, stream: true, conversation_id: conversationId.value || undefined },
      (event: StreamEvent) => {
        // 流式错误事件 — 包括 Dify 顶层 error（event.error）和 chat.py 异常（event.message）
        if (event.event === 'error') {
          throw { status: 0, message: event.error || event.message || '流式处理异常' } as ChatError
        }
        // done 事件 — 流正常结束，无需额外处理
        if (event.event === 'done') return
        // workflow 节点事件由聊天页按队列渐进展示，避免多个节点瞬间堆叠。
        if (event.node) {
          enqueueStepUpdate(assistantMsg, event.node, event.event)
        }
        if (event.thought) {
          assistantMsg.thought += event.thought
        }
        if (event.answer) {
          assistantMsg.content += event.answer
        }
        if (event.conversation_id) {
          conversationId.value = event.conversation_id
          conversationTitle.value = conversationTitle.value || current.slice(0, 30)
          syncConversationUrl(event.conversation_id)
        }
        scheduleScrollLatest()
      },
    )
    // 流结束：让打字机继续跑完剩余内容
    // 不做 stopTypewriter，由 setInterval 自动检测 completed 后停止
  } catch (err: unknown) {
    const e = err as ChatError
    // 清除空的 assistant 消息
    if (!assistantMsg.content && !assistantMsg.thought && assistantMsg.steps.length === 0) {
      messages.value = messages.value.filter((m) => m.id !== assistantMsg.id)
    }
    stopTypewriter()
    // 让显示内容保持已有内容，不清空
    assistantMsg.displayContent = assistantMsg.content
    assistantMsg.displayThought = assistantMsg.thought
    if (e.status === 401) {
      // token 过期或无效，清理登录态并跳转
      auth.clearSession()
      errorMsg.value = '登录已失效，请重新登录'
      router.push('/login')
    } else if (e.status === 403) {
      errorMsg.value = `权限不足（403）：${e.message}`
    } else if (e.status === 503) {
      errorMsg.value = '服务未就绪（503）：Agent 运行时未配置，请联系管理员。'
    } else {
      errorMsg.value = `调用失败：${e.message || '未知错误'}`
    }
  } finally {
    assistantMsg.isStreaming = false
    loading.value = false
    if (auth.isLoggedIn) {
      await refreshConversationList()
      const currentConversation = conversationList.value.find(item => item.id === conversationId.value)
      if (currentConversation) {
        conversationTitle.value = currentConversation.title
      }
    }
    await scrollBottom()
  }
}
</script>

<style scoped>
/* ---- 页面背景 ---- */
.chat-page {
  min-height: 100dvh;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  padding: 28px 24px;
  background:
    linear-gradient(90deg, rgba(234, 245, 255, 0.72) 0%, rgba(245, 247, 250, 0) 34%),
    linear-gradient(180deg, #f8fbff 0%, var(--color-bg-page) 52%, #eef4f9 100%);
}

/* ---- 历史会话侧边栏 ---- */
.conversation-sidebar {
  width: 260px;
  flex-shrink: 0;
  height: calc(100dvh - 56px);
  min-height: 640px;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-white);
  border: 1px solid var(--color-border);
  border-right: none;
  border-radius: var(--radius-lg) 0 0 var(--radius-lg);
  box-shadow: 0 18px 52px rgba(15, 23, 42, 0.09), 0 2px 8px rgba(15, 23, 42, 0.04);
  overflow: hidden;
  transition: width 0.22s ease, opacity 0.18s ease, border-width 0.18s ease;
}

.conversation-sidebar.sidebar-collapsed {
  width: 0;
  min-width: 0;
  border-width: 0;
  opacity: 0;
  pointer-events: none;
}

.conversation-sidebar.sidebar-collapsed + .chat-panel {
  border-radius: var(--radius-lg);
}

.sidebar-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  min-height: 58px;
  padding: 10px 16px 10px 20px;
  border-bottom: 1px solid var(--color-border);
  background:
    linear-gradient(90deg, rgba(223, 241, 255, 0.96) 0%, rgba(245, 250, 255, 0.98) 46%, rgba(255, 255, 255, 0.98) 100%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 251, 255, 0.94) 100%);
}

.sidebar-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.sidebar-list {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  padding: 8px;
}

.sidebar-item {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 28px;
  align-items: center;
  gap: 4px;
  min-height: 52px;
  padding: 8px 8px 8px 12px;
  border-radius: var(--radius);
  cursor: pointer;
  transition: background 0.15s ease, box-shadow 0.15s ease;
}

.sidebar-item:hover {
  background: var(--color-primary-bg);
}

.sidebar-item.active {
  background: var(--color-primary-bg);
  box-shadow: inset 0 0 0 1px var(--color-primary-border);
}

.sidebar-item.switching {
  opacity: 0.68;
  pointer-events: none;
}

.sidebar-item-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sidebar-item-title {
  font-size: 14px;
  color: var(--color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sidebar-item-time {
  font-size: 12px;
  color: var(--color-text-tertiary);
}

.sidebar-delete-btn {
  width: 28px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: var(--radius);
  background: transparent;
  color: var(--color-text-tertiary);
  cursor: pointer;
  opacity: 0;
  transition: opacity 0.15s ease, background 0.15s ease, color 0.15s ease;
}

.sidebar-item:hover .sidebar-delete-btn,
.sidebar-delete-btn:focus-visible {
  opacity: 1;
}

.sidebar-delete-btn:hover,
.sidebar-delete-btn:focus-visible {
  background: #fef2f2;
  color: var(--color-error);
  outline: none;
}

.sidebar-delete-btn:disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.sidebar-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.sidebar-loading {
  padding: 14px 12px;
  text-align: center;
  color: var(--color-text-tertiary);
  font-size: 13px;
}

.sidebar-load-more {
  margin-top: 8px;
  color: var(--color-primary);
  border-color: var(--color-primary-border);
}

.sidebar-toggle-btn {
  width: 28px;
  height: 28px;
  min-width: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
  font-size: 16px;
  line-height: 1;
}

.sidebar-toggle-btn:hover,
.sidebar-toggle-btn:focus-visible {
  background: var(--color-primary-bg);
  color: var(--color-primary);
}

.sidebar-overlay {
  position: fixed;
  inset: 0;
  z-index: 99;
  background: rgba(0, 0, 0, 0.3);
}

/* ---- 面板 ---- */
.chat-panel {
  width: min(920px, 100%);
  height: calc(100dvh - 56px);
  min-height: 640px;
  display: grid;
  grid-template-rows: auto 1fr auto auto;
  background: var(--color-bg-white);
  border: 1px solid var(--color-border);
  border-radius: 0 var(--radius-lg) var(--radius-lg) 0;
  box-shadow: 0 18px 52px rgba(15, 23, 42, 0.09), 0 2px 8px rgba(15, 23, 42, 0.04);
  overflow: hidden;
}

.chat-panel.sidebar-hidden-panel {
  border-radius: var(--radius-lg);
}

/* ---- 顶栏 ---- */
.chat-header {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  min-height: 58px;
  padding: 10px 18px 10px 16px;
  border-bottom: 1px solid var(--color-border);
  background:
    linear-gradient(90deg, rgba(223, 241, 255, 0.96) 0%, rgba(245, 250, 255, 0.98) 46%, rgba(255, 255, 255, 0.98) 100%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(248, 251, 255, 0.94) 100%);
  flex-wrap: wrap;
  box-shadow: inset 0 -1px 0 rgba(187, 223, 255, 0.75);
}
.chat-header::after {
  content: '';
  position: absolute;
  left: 0;
  right: 0;
  bottom: -1px;
  height: 2px;
  background: linear-gradient(90deg, var(--color-primary) 0%, rgba(187, 223, 255, 0.78) 34%, rgba(187, 223, 255, 0) 100%);
  opacity: 0.45;
  pointer-events: none;
}
.header-left {
  min-width: 0;
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-title {
  position: relative;
  font-size: 17px;
  font-weight: 700;
  color: #0f172a;
}
.header-title::before {
  content: '';
  position: absolute;
  left: -11px;
  top: 50%;
  width: 4px;
  height: 18px;
  border-radius: 999px;
  background: var(--color-primary);
  transform: translateY(-50%);
}
.conversation-title {
  max-width: 260px;
  overflow: hidden;
  color: var(--color-text-tertiary);
  font-size: 13px;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.header-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}
.header-icon-button {
  width: 32px;
  height: 32px;
  min-height: 32px;
  border-color: transparent;
  background: var(--color-primary-bg);
  color: var(--color-primary);
  box-shadow: inset 0 0 0 1px rgba(0, 122, 204, 0.12);
}
.header-icon-button:hover,
.header-icon-button:focus-visible {
  border-color: var(--color-primary-border);
  background: #dff1ff;
  color: var(--color-primary-hover);
}
.user-avatar-button {
  width: 34px;
  height: 34px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0;
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}
.user-avatar-button:focus-visible {
  outline: 3px solid rgba(0, 122, 204, 0.16);
  outline-offset: 2px;
}
.user-avatar {
  width: 30px;
  height: 30px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 2px solid #ffffff;
  border-radius: 999px;
  background: linear-gradient(135deg, #0098ff 0%, #13c2c2 100%);
  color: #ffffff;
  font-size: 14px;
  font-weight: 700;
  box-shadow: 0 8px 18px rgba(0, 122, 204, 0.22);
}
/* ---- 消息区 ---- */
.messages {
  display: flex;
  flex-direction: column;
  gap: 16px;
  min-height: 0;
  padding: 28px 28px 32px;
  background:
    linear-gradient(90deg, rgba(234, 245, 255, 0.54) 0%, rgba(255, 255, 255, 0) 22%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.78) 0%, rgba(247, 251, 255, 0.88) 100%);
  overflow: auto;
  scroll-padding: 30vh 0;
}

.hint-banner {
  align-self: center;
  margin: auto;
  color: var(--color-text-secondary);
  font-size: 14px;
  padding: 24px;
  text-align: center;
  background: var(--color-bg-page);
  border-radius: var(--radius-lg);
  max-width: 360px;
}

/* ---- 欢迎横幅 ---- */
.welcome-banner {
  text-align: center;
  margin: auto;
  padding: 48px 24px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 12px;
}
.welcome-icon {
  font-size: 48px;
  color: var(--color-primary);
  opacity: 0.6;
}
.welcome-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
  margin: 0;
}
.welcome-hint {
  font-size: 14px;
  color: var(--color-text-tertiary);
  margin: 0;
}

/* ---- 打字动画 ---- */
.typing-dots {
  display: flex;
  gap: 6px;
  align-items: center;
  min-height: 22px;
  padding: 2px 0;
}
.typing-dots .dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  animation: dot-bounce 1.4s infinite ease-in-out both;
}
.typing-dots .dot:nth-child(1) { animation-delay: 0s; }
.typing-dots .dot:nth-child(2) { animation-delay: 0.2s; }
.typing-dots .dot:nth-child(3) { animation-delay: 0.4s; }
@keyframes dot-bounce {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.4; }
  40% { transform: scale(1); opacity: 1; }
}

.message {
  max-width: 80%;
  padding: 12px 16px;
  border-radius: 8px;
  font-size: 14px;
  line-height: 1.6;
  overflow-wrap: break-word;
}
.message.user {
  align-self: flex-end;
  background: linear-gradient(135deg, #1294e8 0%, var(--color-primary) 58%, #005a9e 100%);
  color: #fff;
  white-space: pre-wrap;
  border-radius: 8px 8px 3px 8px;
  box-shadow: 0 12px 32px rgba(0, 122, 204, 0.24);
}
.message.assistant {
  position: relative;
  align-self: flex-start;
  background: linear-gradient(180deg, #ffffff 0%, #f9fcff 100%);
  border: 1px solid transparent;
  border-radius: 8px 8px 8px 3px;
  box-shadow: 0 18px 42px rgba(15, 23, 42, 0.09), 0 2px 8px rgba(0, 90, 158, 0.05);
}
.message.assistant::before {
  content: '';
  position: absolute;
  inset: 0 0 auto 0;
  height: 42px;
  border-radius: 8px 8px 0 0;
  background: linear-gradient(180deg, rgba(234, 245, 255, 0.82) 0%, rgba(255, 255, 255, 0) 100%);
  pointer-events: none;
}
.message.assistant > * {
  position: relative;
  z-index: 1;
}
.message.typing {
  opacity: 0.6;
}

/* ---- 智能体过程步骤 ---- */
.steps-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
  margin-bottom: 10px;
}
.workflow-summary {
  width: 100%;
  min-height: 44px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 10px;
  padding: 9px 12px;
  border: 1px solid var(--color-primary-border);
  border-radius: var(--radius-lg);
  background: linear-gradient(180deg, #f7fbff 0%, var(--color-primary-bg) 100%);
  color: var(--color-text-primary);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease;
}
.workflow-summary:hover,
.workflow-summary:focus-visible {
  border-color: #82c8f6;
  box-shadow: 0 0 0 3px rgba(0, 122, 204, 0.08);
  outline: none;
}
.workflow-summary.failed {
  border-color: #fecaca;
  background: linear-gradient(180deg, #fffafa 0%, #fef2f2 100%);
}
.workflow-summary.finished {
  border-color: #bbf7d0;
  background: linear-gradient(180deg, #fbfffd 0%, #f0fdf4 100%);
}
.workflow-status-icon {
  width: 22px;
  height: 22px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--color-primary);
  font-size: 16px;
}
.workflow-summary.finished .workflow-status-icon {
  color: var(--color-success);
}
.workflow-summary.failed .workflow-status-icon {
  color: var(--color-error);
}
.workflow-copy {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.workflow-title {
  font-size: 14px;
  font-weight: 600;
  line-height: 1.35;
  color: var(--color-text-primary);
}
.workflow-detail {
  overflow: hidden;
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1.35;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflow-count {
  min-width: 38px;
  padding: 3px 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.72);
  color: var(--color-text-secondary);
  font-size: 12px;
  line-height: 1;
  text-align: center;
  white-space: nowrap;
}
.workflow-chevron {
  color: var(--color-text-tertiary);
  font-size: 12px;
  transition: transform 0.2s ease;
}
.workflow-chevron.expanded {
  transform: rotate(180deg);
}
.step-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 8px 10px 4px 16px;
  border-left: 2px solid var(--color-primary-border);
  margin-left: 11px;
}
.step-item {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr) auto auto;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--color-text-secondary);
  min-height: 24px;
}
.step-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-primary);
}
.step-item.finished .step-dot {
  background: var(--color-success);
}
.step-item.retry .step-dot {
  background: var(--color-warning);
}
.step-item.failed .step-dot {
  background: var(--color-error);
}
.step-item.running .step-dot {
  animation: pulse 1.2s infinite;
}
.step-item.finished .step-title {
  color: var(--color-text-secondary);
}
.step-title {
  min-width: 0;
  overflow: hidden;
  color: var(--color-text-primary);
  text-overflow: ellipsis;
  white-space: nowrap;
}
.step-status {
  color: var(--color-text-tertiary);
  white-space: nowrap;
}
.step-time {
  color: var(--color-text-tertiary);
  font-size: 11px;
  white-space: nowrap;
}
.steps-divider {
  border-top: 1px solid var(--color-border);
  margin: 10px 0;
}
@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

/* ---- 思考过程 ---- */
.thought-section {
  margin-bottom: 8px;
}
.thought-content {
  color: var(--color-text-secondary);
  font-size: 13px;
  white-space: pre-wrap;
  font-style: italic;
  line-height: 1.5;
}

/* ---- Markdown 渲染 ---- */
.markdown-body {
  line-height: 1.7;
}
.markdown-body :deep(p) {
  margin: 0.5em 0;
}
.markdown-body :deep(pre) {
  background: var(--color-code-bg);
  color: var(--color-code-text);
  padding: 14px 16px;
  border-radius: var(--radius);
  overflow-x: auto;
  font-size: 13px;
  line-height: 1.5;
}
.markdown-body :deep(code) {
  background: var(--color-code-inline-bg);
  padding: 2px 6px;
  border-radius: var(--radius-sm);
  font-size: 0.875em;
  font-family: var(--font-mono);
}
.markdown-body :deep(pre code) {
  background: none;
  padding: 0;
}
.markdown-body :deep(ul),
.markdown-body :deep(ol) {
  padding-left: 1.5em;
}
.markdown-body :deep(blockquote) {
  border-left: 3px solid var(--color-blockquote-border);
  margin: 0.5em 0;
  padding: 12px 16px;
  color: var(--color-text-secondary);
}
.markdown-body :deep(table) {
  border-collapse: collapse;
  margin: 0.5em 0;
  width: 100%;
}
.markdown-body :deep(th),
.markdown-body :deep(td) {
  border: 1px solid var(--color-md-border);
  padding: 8px 12px;
  text-align: left;
}
.markdown-body :deep(th) {
  background: var(--color-table-header-bg);
  font-weight: 600;
}
.markdown-body :deep(h1),
.markdown-body :deep(h2),
.markdown-body :deep(h3),
.markdown-body :deep(h4) {
  margin: 1em 0 0.5em;
  line-height: 1.4;
}
.markdown-body :deep(h2) {
  font-size: 17px;
}
.markdown-body :deep(h3) {
  font-size: 15px;
}
.markdown-body :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-md-border);
  margin: 1em 0;
}

/* ---- 语音播报 ---- */
.speech-actions {
  margin-top: 6px;
  text-align: right;
}

/* ---- 输入区 ---- */
.composer {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 58px 112px;
  gap: 12px;
  align-items: stretch;
  padding: 14px 20px;
  border-top: 1px solid var(--color-border);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(247, 251, 255, 0.98) 100%);
  box-shadow: 0 -10px 28px rgba(15, 23, 42, 0.04);
}

.composer-input {
  width: 100%;
  min-height: 46px;
  resize: none;
}

.composer-icon-button {
  width: 58px;
  height: 46px;
  min-width: 58px;
  padding: 0;
}

.composer-send-button {
  height: 46px;
  min-width: 112px;
  padding: 0 16px;
}

.composer :deep(.ant-input) {
  min-height: 46px;
  padding: 11px 16px;
  border-color: #d8e2ee;
  background: #fbfdff;
  line-height: 21px;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.03);
}

.composer :deep(.ant-input:focus),
.composer :deep(.ant-input-focused) {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(0, 122, 204, 0.1);
}

.composer :deep(.ant-btn) {
  height: 46px;
}

/* ---- 错误条 ---- */
.error-bar {
  border-radius: 0;
  margin: 0;
}

@media (max-width: 767px) {
  .chat-page {
    padding: 0;
  }

  .conversation-sidebar {
    position: fixed;
    left: 0;
    top: 0;
    bottom: 0;
    z-index: 100;
    width: 260px;
    height: 100dvh;
    min-height: auto;
    border-radius: 0;
    border-right: 1px solid var(--color-border);
    transform: translateX(-100%);
    transition: transform 0.25s ease;
  }

  .conversation-sidebar.sidebar-open {
    transform: translateX(0);
  }

  .chat-panel {
    width: 100%;
    height: 100dvh;
    min-height: 100dvh;
    border: 0;
    border-radius: 0;
  }

  .chat-header {
    padding: 10px 12px;
  }

  .messages {
    padding: 16px 12px 20px;
  }

  .message {
    max-width: 92%;
  }

  .composer {
    grid-template-columns: minmax(0, 1fr) 46px 72px;
    padding: 10px 12px;
    gap: 8px;
  }

  .composer-icon-button {
    width: 46px;
    height: 42px;
    min-width: 46px;
  }

  .composer-send-button {
    height: 42px;
    min-width: 72px;
  }

  .composer :deep(.ant-input),
  .composer :deep(.ant-btn) {
    min-height: 42px;
    height: 42px;
  }

  .composer :deep(.ant-input) {
    padding: 10px 13px;
  }
}
</style>
