import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { AudioOutlined, CheckCircleFilled, CloseCircleFilled, DownOutlined, LoadingOutlined, PauseCircleOutlined, PlusOutlined, RobotOutlined, SoundOutlined, } from '@ant-design/icons-vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { streamChat } from '../../api/chat';
import { archiveConversation, createConversation, getConversation, getConversationMessages, getCurrentConversation, } from '../../api/conversations';
import { useAuthStore } from '../../stores/auth';
import { useSpeechRecognition } from '../../composables/useSpeechRecognition';
import { useSpeechSynthesis } from '../../composables/useSpeechSynthesis';
// 配置 marked
marked.setOptions({ breaks: true, gfm: true });
// 配置 DOMPurify：链接安全策略
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
    if (node instanceof HTMLAnchorElement) {
        node.setAttribute('target', '_blank');
        node.setAttribute('rel', 'noopener noreferrer');
    }
});
function renderMarkdown(text) {
    if (!text)
        return '';
    const rawHtml = marked(text);
    return DOMPurify.sanitize(rawHtml, { ALLOWED_TAGS: [
            'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'p', 'br', 'hr',
            'ul', 'ol', 'li',
            'blockquote', 'pre', 'code',
            'table', 'thead', 'tbody', 'tr', 'th', 'td',
            'strong', 'em', 'del', 'ins', 's',
            'a', 'img',
            'span', 'div',
        ] });
}
/** 根据节点类型/标题决定是否展示及对应 emoji 与颜色。返回 null 表示跳过该节点。 */
function getStepMeta(node) {
    const type = node.node_type || '';
    const title = node.title || '';
    // 不展示的节点：workflow 占位、用户输入、结束、条件分支、最终回复。
    if (!type && !title)
        return null;
    if (type === 'start' || type === 'end' || type === 'answer')
        return null;
    if (title === '处理中')
        return null;
    if (title.includes('用户输入') || title === '开始' || title === '结束')
        return null;
    if (title.includes('条件分支') || title.includes('条件判断') || type === 'if-else')
        return null;
    if (title === 'answer'
        || title.includes('智能回复')
        || title.includes('智能问答回复')
        || title.includes('直接回复'))
        return null;
    // 按标题关键词匹配
    if (title.includes('意图') || title.includes('识别'))
        return { emoji: '🎯', color: '#722ed1' };
    if (title.includes('润色') || title.includes('改写') || title.includes('重写'))
        return { emoji: '✨', color: '#fa8c16' };
    if (title.includes('知识库') || title.includes('检索'))
        return { emoji: '📚', color: '#1677ff' };
    // 按节点类型匹配
    if (type === 'knowledge-retrieval')
        return { emoji: '📚', color: '#1677ff' };
    if (type === 'llm')
        return { emoji: '🤖', color: '#52c41a' };
    if (type === 'http-request')
        return { emoji: '🌐', color: '#13c2c2' };
    if (type === 'code')
        return { emoji: '💻', color: '#eb2f96' };
    // 其他类型默认展示
    return { emoji: '⚙️', color: '#8c8c8c' };
}
function buildStoredSteps(rawSteps) {
    if (!rawSteps?.length)
        return [];
    const result = [];
    const seen = new Set();
    for (const raw of rawSteps) {
        const node = raw;
        const meta = getStepMeta(node);
        if (!meta)
            continue;
        const { id, title } = getNodeIdentity(node);
        const status = node.status === 'failed' ? 'failed' : 'finished';
        const existing = result.find(step => step.id === id || step.title === title);
        if (existing) {
            existing.status = status;
            existing.elapsedTime = node.elapsed_time;
            continue;
        }
        if (seen.has(id))
            continue;
        seen.add(id);
        result.push({
            id,
            title,
            emoji: meta.emoji,
            color: meta.color,
            status,
            elapsedTime: node.elapsed_time,
        });
    }
    return result;
}
function isWorkflowRunning(message) {
    return message.isStreaming || message.steps.some(step => step.status === 'running' || step.status === 'retry');
}
function getWorkflowStatus(message) {
    if (message.steps.some(step => step.status === 'failed'))
        return 'failed';
    return isWorkflowRunning(message) ? 'running' : 'finished';
}
function getWorkflowTitle(message) {
    const status = getWorkflowStatus(message);
    if (status === 'failed')
        return '工作流执行失败';
    if (status === 'finished')
        return '工作流已完成';
    return '工作流正在执行';
}
function getWorkflowDetail(message) {
    const latest = message.steps[message.steps.length - 1];
    if (!latest)
        return '正在准备处理流程';
    if (latest.status === 'running')
        return `正在处理：${latest.title}`;
    if (latest.status === 'retry')
        return `正在重试：${latest.title}`;
    if (latest.status === 'failed')
        return `失败节点：${latest.title}`;
    return `最近完成：${latest.title}`;
}
function getWorkflowCountText(message) {
    return message.steps.length > 0 ? `${message.steps.length} 步` : '准备中';
}
function getStepStatusText(status) {
    const statusText = {
        running: '进行中',
        finished: '已完成',
        failed: '失败',
        retry: '重试中',
    };
    return statusText[status];
}
function getUserInitial(name) {
    return name.trim().slice(0, 1).toUpperCase() || '用';
}
function mapConversationMessage(item) {
    if (item.role === 'SYSTEM')
        return null;
    const role = item.role === 'USER' ? 'user' : 'assistant';
    return {
        id: item.id,
        role,
        content: item.content,
        thought: item.thought || '',
        displayContent: role === 'assistant' ? item.content : '',
        displayThought: item.thought || '',
        steps: role === 'assistant' ? buildStoredSteps(item.steps) : [],
        isStreaming: false,
    };
}
const router = useRouter();
const auth = useAuthStore();
const canChat = computed(() => auth.isLoggedIn);
const agentCode = ref('qa');
const question = ref('');
const loading = ref(false);
const restoringConversation = ref(false);
const errorMsg = ref('');
const messages = ref([]);
const msgContainer = ref(null);
const thoughtOpen = ref(true);
const expandedSteps = ref({});
const conversationId = ref(null);
const conversationTitle = ref('');
// 语音能力
const speech = useSpeechRecognition();
const synth = useSpeechSynthesis();
// 节点事件通常会在几十毫秒内连续到达。这里用前端队列把步骤逐个展示，
// 同时保证每一步至少可见一小段时间，避免用户看到“一整串步骤瞬间出现”。
const STEP_REVEAL_GAP_MS = 520;
const STEP_MIN_VISIBLE_MS = 700;
const queuedSteps = [];
const stepTimers = new Set();
let isDrainingStepQueue = false;
let scrollTimer = null;
function syncConversationUrl(id) {
    const query = { ...router.currentRoute.value.query };
    if (id) {
        query.conversation_id = id;
    }
    else {
        delete query.conversation_id;
    }
    void router.replace({ query });
}
async function restoreCurrentConversation() {
    if (!auth.isLoggedIn)
        return;
    restoringConversation.value = true;
    try {
        const routeConversationId = router.currentRoute.value.query.conversation_id;
        const requestedId = typeof routeConversationId === 'string' ? routeConversationId : null;
        const currentState = requestedId ? null : await getCurrentConversation(agentCode.value);
        const current = requestedId ? await getConversation(requestedId) : currentState?.conversation;
        const storedMessages = requestedId
            ? await getConversationMessages(requestedId)
            : currentState?.messages ?? [];
        conversationId.value = current?.id ?? null;
        conversationTitle.value = current?.title ?? '';
        messages.value = storedMessages
            .map(mapConversationMessage)
            .filter((item) => item !== null);
        syncConversationUrl(conversationId.value);
        await scrollBottom();
    }
    catch {
        errorMsg.value = '恢复对话失败，请稍后重试';
    }
    finally {
        restoringConversation.value = false;
    }
}
async function handleNewConversation() {
    if (loading.value)
        return;
    errorMsg.value = '';
    if (conversationId.value) {
        try {
            await archiveConversation(conversationId.value);
        }
        catch {
            // 新对话体验优先，归档失败不阻断创建新上下文。
        }
    }
    const conversation = await createConversation(agentCode.value);
    conversationId.value = conversation.id;
    conversationTitle.value = conversation.title;
    messages.value = [];
    expandedSteps.value = {};
    syncConversationUrl(conversation.id);
    await scrollBottom();
}
function scheduleStepTimer(callback, delayMs) {
    const timer = setTimeout(() => {
        stepTimers.delete(timer);
        callback();
    }, delayMs);
    stepTimers.add(timer);
}
function waitForStepTimer(delayMs) {
    return new Promise(resolve => scheduleStepTimer(resolve, delayMs));
}
function getNodeIdentity(node) {
    const title = node.title || node.node_type || '处理中';
    return {
        id: node.node_id || title,
        title,
    };
}
function findVisibleStep(message, id, title) {
    return message.steps.find(step => step.id === id || step.title === title);
}
function findQueuedStep(message, id, title) {
    return queuedSteps.find(step => step.message.id === message.id && (step.id === id || step.title === title));
}
function mergeQueuedStep(queued, status, elapsedTime) {
    if (status === 'finished' || status === 'failed') {
        queued.finalStatus = status;
        queued.finalElapsedTime = elapsedTime;
        return;
    }
    queued.status = status;
    queued.elapsedTime = elapsedTime;
}
function applyVisibleStepUpdate(step, status, elapsedTime) {
    step.status = status;
    step.elapsedTime = elapsedTime;
}
function finishVisibleStepAfterMinimum(step, status, elapsedTime) {
    const visibleAt = step.visibleAt ?? Date.now();
    const remainingMs = Math.max(0, STEP_MIN_VISIBLE_MS - (Date.now() - visibleAt));
    scheduleStepTimer(() => {
        applyVisibleStepUpdate(step, status, elapsedTime);
        scrollLatestMessageIntoView('smooth');
    }, remainingMs);
}
async function drainStepQueue() {
    if (isDrainingStepQueue)
        return;
    isDrainingStepQueue = true;
    try {
        while (queuedSteps.length > 0) {
            const queued = queuedSteps.shift();
            if (!queued || !messages.value.some(message => message.id === queued.message.id)) {
                continue;
            }
            const existing = findVisibleStep(queued.message, queued.id, queued.title);
            const step = existing ?? {
                id: queued.id,
                title: queued.title,
                emoji: queued.emoji,
                color: queued.color,
                status: queued.status,
                elapsedTime: queued.elapsedTime,
                visibleAt: Date.now(),
            };
            if (!existing) {
                queued.message.steps.push(step);
            }
            else {
                applyVisibleStepUpdate(step, queued.status, queued.elapsedTime);
            }
            scrollLatestMessageIntoView('smooth');
            if (queued.finalStatus) {
                finishVisibleStepAfterMinimum(step, queued.finalStatus, queued.finalElapsedTime);
            }
            await waitForStepTimer(STEP_REVEAL_GAP_MS);
        }
    }
    finally {
        isDrainingStepQueue = false;
        if (queuedSteps.length > 0) {
            void drainStepQueue();
        }
    }
}
function enqueueStepUpdate(message, node, eventName) {
    if (eventName === 'workflow_started' || eventName === 'workflow_finished')
        return;
    const meta = getStepMeta(node);
    if (!meta)
        return;
    const { id, title } = getNodeIdentity(node);
    const status = eventName === 'node_finished'
        ? (node.status === 'failed' ? 'failed' : 'finished')
        : eventName === 'node_retry'
            ? 'retry'
            : 'running';
    const visible = findVisibleStep(message, id, title);
    if (visible) {
        if (status === 'finished' || status === 'failed') {
            finishVisibleStepAfterMinimum(visible, status, node.elapsed_time);
        }
        else {
            applyVisibleStepUpdate(visible, status, node.elapsed_time);
        }
        return;
    }
    const queued = findQueuedStep(message, id, title);
    if (queued) {
        mergeQueuedStep(queued, status, node.elapsed_time);
        return;
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
    });
    void drainStepQueue();
}
// 语音输入：将识别结果填入输入框，识别结束时可自动发送
function toggleSpeechInput() {
    if (speech.isListening.value) {
        speech.stop();
        // 识别结束后将文本写入输入框
        if (speech.transcript.value) {
            question.value = speech.transcript.value;
            speech.clearTranscript();
        }
    }
    else {
        speech.clearTranscript();
        speech.start();
    }
}
// 语音播报：播放/停止
function toggleSpeechOutput(text) {
    if (synth.isSpeaking.value) {
        synth.stop();
    }
    else {
        synth.speak(text);
    }
}
// 发送新问题时停止播报
async function safeSend() {
    synth.stop();
    await send();
}
// ── 打字机效果 ──────────────────────────────
const typewriterTimer = ref(null);
const typewriterCursors = ref(new Map());
function startTypewriter() {
    typewriterTimer.value = setInterval(() => {
        let anyTyping = false;
        for (const msg of messages.value) {
            if (msg.role !== 'assistant')
                continue;
            let cursor = typewriterCursors.value.get(msg.id) ?? (msg.displayContent?.length ?? 0);
            if (cursor < msg.content.length) {
                // 自适应步长：长文本一次多输出几个字符，保证约 1.5 秒打完
                const chunkSize = Math.max(1, Math.floor(msg.content.length / 50));
                cursor = Math.min(msg.content.length, cursor + chunkSize);
                msg.displayContent = msg.content.slice(0, cursor);
                typewriterCursors.value.set(msg.id, cursor);
                anyTyping = true;
            }
            const thoughtKey = `${msg.id}:thought`;
            let thoughtCursor = typewriterCursors.value.get(thoughtKey) ?? msg.displayThought.length;
            if (thoughtCursor < msg.thought.length) {
                const chunkSize = Math.max(1, Math.floor(msg.thought.length / 80));
                thoughtCursor = Math.min(msg.thought.length, thoughtCursor + chunkSize);
                msg.displayThought = msg.thought.slice(0, thoughtCursor);
                typewriterCursors.value.set(thoughtKey, thoughtCursor);
                anyTyping = true;
            }
        }
        // 流未结束时不停止，避免内容尚未到达时 timer 自杀
        if (!anyTyping && !loading.value && typewriterTimer.value) {
            clearInterval(typewriterTimer.value);
            typewriterTimer.value = null;
        }
    }, 30);
}
function stopTypewriter() {
    if (typewriterTimer.value) {
        clearInterval(typewriterTimer.value);
        typewriterTimer.value = null;
    }
    // 全部显示完整内容
    for (const msg of messages.value) {
        if (msg.role === 'assistant' && msg.content) {
            msg.displayContent = msg.content;
        }
        if (msg.role === 'assistant' && msg.thought) {
            msg.displayThought = msg.thought;
        }
    }
    typewriterCursors.value.clear();
}
onMounted(() => {
    void restoreCurrentConversation();
});
onUnmounted(() => {
    if (scrollTimer) {
        clearTimeout(scrollTimer);
        scrollTimer = null;
    }
    queuedSteps.length = 0;
    for (const timer of stepTimers) {
        clearTimeout(timer);
    }
    stepTimers.clear();
    stopTypewriter();
    synth.stop();
});
async function handleLogout() {
    await auth.doLogout();
    router.push('/login');
}
// ── 滚动 ───────────────────────────────────
async function scrollLatestMessageIntoView(behavior = 'auto') {
    await nextTick();
    const container = msgContainer.value;
    if (!container)
        return;
    const messageNodes = container.querySelectorAll('.message');
    const latestMessage = messageNodes[messageNodes.length - 1];
    if (latestMessage) {
        latestMessage.scrollIntoView({ block: 'center', inline: 'nearest', behavior });
    }
    else {
        container.scrollTop = container.scrollHeight;
    }
}
async function scrollBottom() {
    await scrollLatestMessageIntoView('auto');
}
function scheduleScrollLatest(behavior = 'auto') {
    if (scrollTimer)
        return;
    scrollTimer = setTimeout(() => {
        scrollTimer = null;
        void scrollLatestMessageIntoView(behavior);
    }, 80);
}
// ── 发送消息 ───────────────────────────────
async function send() {
    const current = question.value.trim();
    if (!current || loading.value || !canChat.value)
        return;
    errorMsg.value = '';
    thoughtOpen.value = true;
    const sessionReady = await auth.ensureFreshSessionForChat();
    if (!sessionReady) {
        errorMsg.value = '登录已失效，请重新登录';
        router.push('/login');
        return;
    }
    const userMsg = {
        id: crypto.randomUUID(),
        role: 'user',
        content: current,
        thought: '',
        displayContent: '',
        displayThought: '',
        steps: [],
        isStreaming: false,
    };
    const assistantMsg = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: '',
        thought: '',
        displayContent: '',
        displayThought: '',
        steps: [],
        isStreaming: true,
    };
    messages.value.push(userMsg, assistantMsg);
    question.value = '';
    loading.value = true;
    startTypewriter();
    await scrollBottom();
    try {
        await streamChat(agentCode.value, { question: current, stream: true, conversation_id: conversationId.value || undefined }, (event) => {
            // 流式错误事件 — 包括 Dify 顶层 error（event.error）和 chat.py 异常（event.message）
            if (event.event === 'error') {
                throw { status: 0, message: event.error || event.message || '流式处理异常' };
            }
            // done 事件 — 流正常结束，无需额外处理
            if (event.event === 'done')
                return;
            // workflow 节点事件由聊天页按队列渐进展示，避免多个节点瞬间堆叠。
            if (event.node) {
                enqueueStepUpdate(assistantMsg, event.node, event.event);
            }
            if (event.thought) {
                assistantMsg.thought += event.thought;
            }
            if (event.answer) {
                assistantMsg.content += event.answer;
            }
            if (event.conversation_id) {
                conversationId.value = event.conversation_id;
                conversationTitle.value = conversationTitle.value || current.slice(0, 30);
                syncConversationUrl(event.conversation_id);
            }
            scheduleScrollLatest();
        });
        // 流结束：让打字机继续跑完剩余内容
        // 不做 stopTypewriter，由 setInterval 自动检测 completed 后停止
    }
    catch (err) {
        const e = err;
        // 清除空的 assistant 消息
        if (!assistantMsg.content && !assistantMsg.thought && assistantMsg.steps.length === 0) {
            messages.value = messages.value.filter((m) => m.id !== assistantMsg.id);
        }
        stopTypewriter();
        // 让显示内容保持已有内容，不清空
        assistantMsg.displayContent = assistantMsg.content;
        assistantMsg.displayThought = assistantMsg.thought;
        if (e.status === 401) {
            // token 过期或无效，清理登录态并跳转
            auth.clearSession();
            errorMsg.value = '登录已失效，请重新登录';
            router.push('/login');
        }
        else if (e.status === 403) {
            errorMsg.value = `权限不足（403）：${e.message}`;
        }
        else if (e.status === 503) {
            errorMsg.value = '服务未就绪（503）：Agent 运行时未配置，请联系管理员。';
        }
        else {
            errorMsg.value = `调用失败：${e.message || '未知错误'}`;
        }
    }
    finally {
        assistantMsg.isStreaming = false;
        loading.value = false;
        await scrollBottom();
    }
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['chat-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-icon-button']} */ ;
/** @type {__VLS_StyleScopedClasses['header-icon-button']} */ ;
/** @type {__VLS_StyleScopedClasses['user-avatar-button']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-dots']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-dots']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-dots']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['typing-dots']} */ ;
/** @type {__VLS_StyleScopedClasses['dot']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['assistant']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['assistant']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['finished']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-summary']} */ ;
/** @type {__VLS_StyleScopedClasses['failed']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-chevron']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['finished']} */ ;
/** @type {__VLS_StyleScopedClasses['step-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['step-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['failed']} */ ;
/** @type {__VLS_StyleScopedClasses['step-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['step-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['step-item']} */ ;
/** @type {__VLS_StyleScopedClasses['finished']} */ ;
/** @type {__VLS_StyleScopedClasses['step-title']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-page']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-header']} */ ;
/** @type {__VLS_StyleScopedClasses['messages']} */ ;
/** @type {__VLS_StyleScopedClasses['message']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-icon-button']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-send-button']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['ant-input']} */ ;
// CSS variable injection 
// CSS variable injection end 
__VLS_asFunctionalElement(__VLS_intrinsicElements.main, __VLS_intrinsicElements.main)({
    ...{ class: "chat-page" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: "chat-panel" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "chat-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "header-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-right" },
});
const __VLS_0 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
    title: "新对话",
}));
const __VLS_2 = __VLS_1({
    title: "新对话",
}, ...__VLS_functionalComponentArgsRest(__VLS_1));
__VLS_3.slots.default;
if (__VLS_ctx.auth.isLoggedIn) {
    const __VLS_4 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_5 = __VLS_asFunctionalComponent(__VLS_4, new __VLS_4({
        ...{ 'onClick': {} },
        shape: "circle",
        disabled: (__VLS_ctx.loading || __VLS_ctx.restoringConversation),
        ...{ class: "header-icon-button" },
        'aria-label': "新对话",
    }));
    const __VLS_6 = __VLS_5({
        ...{ 'onClick': {} },
        shape: "circle",
        disabled: (__VLS_ctx.loading || __VLS_ctx.restoringConversation),
        ...{ class: "header-icon-button" },
        'aria-label': "新对话",
    }, ...__VLS_functionalComponentArgsRest(__VLS_5));
    let __VLS_8;
    let __VLS_9;
    let __VLS_10;
    const __VLS_11 = {
        onClick: (__VLS_ctx.handleNewConversation)
    };
    __VLS_7.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_7.slots;
        const __VLS_12 = {}.PlusOutlined;
        /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({}));
        const __VLS_14 = __VLS_13({}, ...__VLS_functionalComponentArgsRest(__VLS_13));
    }
    var __VLS_7;
}
var __VLS_3;
if (__VLS_ctx.auth.isLoggedIn && __VLS_ctx.auth.currentUser) {
    const __VLS_16 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_17 = __VLS_asFunctionalComponent(__VLS_16, new __VLS_16({
        trigger: "click",
        placement: "bottomRight",
    }));
    const __VLS_18 = __VLS_17({
        trigger: "click",
        placement: "bottomRight",
    }, ...__VLS_functionalComponentArgsRest(__VLS_17));
    __VLS_19.slots.default;
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        type: "button",
        ...{ class: "user-avatar-button" },
        title: (__VLS_ctx.auth.currentUser.name),
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "user-avatar" },
    });
    (__VLS_ctx.getUserInitial(__VLS_ctx.auth.currentUser.name));
    {
        const { overlay: __VLS_thisSlot } = __VLS_19.slots;
        const __VLS_20 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
        const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
        __VLS_23.slots.default;
        const __VLS_24 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
            key: "user",
            disabled: true,
        }));
        const __VLS_26 = __VLS_25({
            key: "user",
            disabled: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_25));
        __VLS_27.slots.default;
        (__VLS_ctx.auth.currentUser.name);
        var __VLS_27;
        const __VLS_28 = {}.AMenuDivider;
        /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
        // @ts-ignore
        const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({}));
        const __VLS_30 = __VLS_29({}, ...__VLS_functionalComponentArgsRest(__VLS_29));
        const __VLS_32 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_33 = __VLS_asFunctionalComponent(__VLS_32, new __VLS_32({
            ...{ 'onClick': {} },
            key: "logout",
        }));
        const __VLS_34 = __VLS_33({
            ...{ 'onClick': {} },
            key: "logout",
        }, ...__VLS_functionalComponentArgsRest(__VLS_33));
        let __VLS_36;
        let __VLS_37;
        let __VLS_38;
        const __VLS_39 = {
            onClick: (__VLS_ctx.handleLogout)
        };
        __VLS_35.slots.default;
        var __VLS_35;
        var __VLS_23;
    }
    var __VLS_19;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ref: "msgContainer",
    ...{ class: "messages" },
});
/** @type {typeof __VLS_ctx.msgContainer} */ ;
if (!__VLS_ctx.canChat) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "hint-banner" },
    });
    const __VLS_40 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_42 = __VLS_41({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    let __VLS_44;
    let __VLS_45;
    let __VLS_46;
    const __VLS_47 = {
        onClick: (...[$event]) => {
            if (!(!__VLS_ctx.canChat))
                return;
            __VLS_ctx.$router.push('/login');
        }
    };
    __VLS_43.slots.default;
    var __VLS_43;
}
else if (__VLS_ctx.messages.length === 0 && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "welcome-banner" },
    });
    const __VLS_48 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
        ...{ class: "welcome-icon" },
    }));
    const __VLS_50 = __VLS_49({
        ...{ class: "welcome-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_49));
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "welcome-text" },
    });
    (__VLS_ctx.agentCode);
    __VLS_asFunctionalElement(__VLS_intrinsicElements.p, __VLS_intrinsicElements.p)({
        ...{ class: "welcome-hint" },
    });
    (__VLS_ctx.restoringConversation ? '正在恢复对话...' : '智能问答助手已就绪');
}
for (const [msg] of __VLS_getVForSourceType((__VLS_ctx.messages))) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        key: (msg.id),
        'data-message-id': (msg.id),
        ...{ class: (['message', msg.role]) },
    });
    if (msg.role === 'assistant' && (msg.steps.length > 0 || msg.isStreaming)) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "steps-section" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: (...[$event]) => {
                    if (!(msg.role === 'assistant' && (msg.steps.length > 0 || msg.isStreaming)))
                        return;
                    msg.steps.length > 0 && (__VLS_ctx.expandedSteps[msg.id] = !__VLS_ctx.expandedSteps[msg.id]);
                } },
            type: "button",
            ...{ class: (['workflow-summary', __VLS_ctx.getWorkflowStatus(msg)]) },
            'aria-expanded': (__VLS_ctx.expandedSteps[msg.id] ? 'true' : 'false'),
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "workflow-status-icon" },
        });
        if (__VLS_ctx.isWorkflowRunning(msg)) {
            const __VLS_52 = {}.LoadingOutlined;
            /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({
                spin: true,
            }));
            const __VLS_54 = __VLS_53({
                spin: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_53));
        }
        else if (__VLS_ctx.getWorkflowStatus(msg) === 'failed') {
            const __VLS_56 = {}.CloseCircleFilled;
            /** @type {[typeof __VLS_components.CloseCircleFilled, ]} */ ;
            // @ts-ignore
            const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({}));
            const __VLS_58 = __VLS_57({}, ...__VLS_functionalComponentArgsRest(__VLS_57));
        }
        else {
            const __VLS_60 = {}.CheckCircleFilled;
            /** @type {[typeof __VLS_components.CheckCircleFilled, ]} */ ;
            // @ts-ignore
            const __VLS_61 = __VLS_asFunctionalComponent(__VLS_60, new __VLS_60({}));
            const __VLS_62 = __VLS_61({}, ...__VLS_functionalComponentArgsRest(__VLS_61));
        }
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "workflow-copy" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "workflow-title" },
        });
        (__VLS_ctx.getWorkflowTitle(msg));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "workflow-detail" },
        });
        (__VLS_ctx.getWorkflowDetail(msg));
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "workflow-count" },
        });
        (__VLS_ctx.getWorkflowCountText(msg));
        if (msg.steps.length > 0) {
            const __VLS_64 = {}.DownOutlined;
            /** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
                ...{ class: (['workflow-chevron', { expanded: __VLS_ctx.expandedSteps[msg.id] }]) },
            }));
            const __VLS_66 = __VLS_65({
                ...{ class: (['workflow-chevron', { expanded: __VLS_ctx.expandedSteps[msg.id] }]) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_65));
        }
        if (msg.steps.length > 0 && __VLS_ctx.expandedSteps[msg.id]) {
            __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                ...{ class: "step-list" },
            });
            for (const [step] of __VLS_getVForSourceType((msg.steps))) {
                __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
                    key: (step.id || step.title),
                    ...{ class: (['step-item', step.status]) },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "step-dot" },
                });
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "step-title" },
                });
                (step.title);
                __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                    ...{ class: "step-status" },
                });
                (__VLS_ctx.getStepStatusText(step.status));
                if (step.elapsedTime != null) {
                    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
                        ...{ class: "step-time" },
                    });
                    (step.elapsedTime.toFixed(1));
                }
            }
        }
    }
    if (msg.role === 'assistant' && (msg.steps.length > 0 || msg.isStreaming) && msg.content) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "steps-divider" },
        });
    }
    if (msg.displayThought) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "thought-section" },
        });
        const __VLS_68 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_69 = __VLS_asFunctionalComponent(__VLS_68, new __VLS_68({
            activeKey: (__VLS_ctx.thoughtOpen ? ['thought'] : []),
            ghost: true,
        }));
        const __VLS_70 = __VLS_69({
            activeKey: (__VLS_ctx.thoughtOpen ? ['thought'] : []),
            ghost: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_69));
        __VLS_71.slots.default;
        const __VLS_72 = {}.ACollapsePanel;
        /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
        // @ts-ignore
        const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
            key: "thought",
            header: "思考过程",
        }));
        const __VLS_74 = __VLS_73({
            key: "thought",
            header: "思考过程",
        }, ...__VLS_functionalComponentArgsRest(__VLS_73));
        __VLS_75.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "thought-content" },
        });
        (msg.displayThought);
        var __VLS_75;
        var __VLS_71;
    }
    if (msg.role === 'assistant' && msg.displayContent) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div)({
            ...{ class: "markdown-body" },
        });
        __VLS_asFunctionalDirective(__VLS_directives.vHtml)(null, { ...__VLS_directiveBindingRestFields, value: (__VLS_ctx.renderMarkdown(msg.displayContent ?? msg.content)) }, null, null);
    }
    else {
        (msg.content);
    }
    if (msg.role === 'assistant' && msg.content && __VLS_ctx.synth.isSupported.value) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "speech-actions" },
        });
        const __VLS_76 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
            ...{ 'onClick': {} },
            size: "small",
            type: "link",
            title: (__VLS_ctx.synth.isSpeaking.value ? '停止播报' : '播报回复'),
        }));
        const __VLS_78 = __VLS_77({
            ...{ 'onClick': {} },
            size: "small",
            type: "link",
            title: (__VLS_ctx.synth.isSpeaking.value ? '停止播报' : '播报回复'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        let __VLS_80;
        let __VLS_81;
        let __VLS_82;
        const __VLS_83 = {
            onClick: (...[$event]) => {
                if (!(msg.role === 'assistant' && msg.content && __VLS_ctx.synth.isSupported.value))
                    return;
                __VLS_ctx.toggleSpeechOutput(msg.content);
            }
        };
        __VLS_79.slots.default;
        if (__VLS_ctx.synth.isSpeaking.value) {
            const __VLS_84 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
            const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
        }
        else {
            const __VLS_88 = {}.SoundOutlined;
            /** @type {[typeof __VLS_components.SoundOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({}));
            const __VLS_90 = __VLS_89({}, ...__VLS_functionalComponentArgsRest(__VLS_89));
        }
        var __VLS_79;
    }
}
if (__VLS_ctx.errorMsg) {
    const __VLS_92 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
        ...{ 'onClose': {} },
        type: "error",
        showIcon: true,
        closable: true,
        ...{ class: "error-bar" },
    }));
    const __VLS_94 = __VLS_93({
        ...{ 'onClose': {} },
        type: "error",
        showIcon: true,
        closable: true,
        ...{ class: "error-bar" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_93));
    let __VLS_96;
    let __VLS_97;
    let __VLS_98;
    const __VLS_99 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.errorMsg))
                return;
            __VLS_ctx.errorMsg = '';
        }
    };
    __VLS_95.slots.default;
    (__VLS_ctx.errorMsg);
    var __VLS_95;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({
    ...{ class: "composer" },
});
const __VLS_100 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.question),
    ...{ class: "composer-input" },
    autoSize: ({ minRows: 1, maxRows: 4 }),
    placeholder: (__VLS_ctx.speech.isListening.value ? '正在聆听...' : '输入问题，Enter 发送'),
    disabled: (!__VLS_ctx.canChat || __VLS_ctx.speech.isListening.value),
}));
const __VLS_102 = __VLS_101({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.question),
    ...{ class: "composer-input" },
    autoSize: ({ minRows: 1, maxRows: 4 }),
    placeholder: (__VLS_ctx.speech.isListening.value ? '正在聆听...' : '输入问题，Enter 发送'),
    disabled: (!__VLS_ctx.canChat || __VLS_ctx.speech.isListening.value),
}, ...__VLS_functionalComponentArgsRest(__VLS_101));
let __VLS_104;
let __VLS_105;
let __VLS_106;
const __VLS_107 = {
    onPressEnter: (__VLS_ctx.safeSend)
};
var __VLS_103;
if (__VLS_ctx.speech.isSupported.value) {
    const __VLS_108 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({
        ...{ 'onClick': {} },
        type: (__VLS_ctx.speech.isListening.value ? 'primary' : 'default'),
        danger: (__VLS_ctx.speech.isListening.value),
        title: (__VLS_ctx.speech.isListening.value ? '停止聆听' : '语音输入'),
        size: "large",
        ...{ class: "composer-icon-button" },
    }));
    const __VLS_110 = __VLS_109({
        ...{ 'onClick': {} },
        type: (__VLS_ctx.speech.isListening.value ? 'primary' : 'default'),
        danger: (__VLS_ctx.speech.isListening.value),
        title: (__VLS_ctx.speech.isListening.value ? '停止聆听' : '语音输入'),
        size: "large",
        ...{ class: "composer-icon-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_109));
    let __VLS_112;
    let __VLS_113;
    let __VLS_114;
    const __VLS_115 = {
        onClick: (__VLS_ctx.toggleSpeechInput)
    };
    __VLS_111.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_111.slots;
        if (__VLS_ctx.speech.isListening.value) {
            const __VLS_116 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({}));
            const __VLS_118 = __VLS_117({}, ...__VLS_functionalComponentArgsRest(__VLS_117));
        }
        else {
            const __VLS_120 = {}.AudioOutlined;
            /** @type {[typeof __VLS_components.AudioOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_121 = __VLS_asFunctionalComponent(__VLS_120, new __VLS_120({}));
            const __VLS_122 = __VLS_121({}, ...__VLS_functionalComponentArgsRest(__VLS_121));
        }
    }
    var __VLS_111;
}
const __VLS_124 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    disabled: (!__VLS_ctx.canChat || (!__VLS_ctx.question.trim() && !__VLS_ctx.speech.transcript.value)),
    size: "large",
    ...{ class: "composer-send-button" },
}));
const __VLS_126 = __VLS_125({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    disabled: (!__VLS_ctx.canChat || (!__VLS_ctx.question.trim() && !__VLS_ctx.speech.transcript.value)),
    size: "large",
    ...{ class: "composer-send-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
let __VLS_128;
let __VLS_129;
let __VLS_130;
const __VLS_131 = {
    onClick: (__VLS_ctx.safeSend)
};
__VLS_127.slots.default;
var __VLS_127;
/** @type {__VLS_StyleScopedClasses['chat-page']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['header-title']} */ ;
/** @type {__VLS_StyleScopedClasses['header-right']} */ ;
/** @type {__VLS_StyleScopedClasses['header-icon-button']} */ ;
/** @type {__VLS_StyleScopedClasses['user-avatar-button']} */ ;
/** @type {__VLS_StyleScopedClasses['user-avatar']} */ ;
/** @type {__VLS_StyleScopedClasses['messages']} */ ;
/** @type {__VLS_StyleScopedClasses['hint-banner']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome-banner']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome-text']} */ ;
/** @type {__VLS_StyleScopedClasses['welcome-hint']} */ ;
/** @type {__VLS_StyleScopedClasses['steps-section']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-status-icon']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-copy']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-title']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-detail']} */ ;
/** @type {__VLS_StyleScopedClasses['workflow-count']} */ ;
/** @type {__VLS_StyleScopedClasses['step-list']} */ ;
/** @type {__VLS_StyleScopedClasses['step-dot']} */ ;
/** @type {__VLS_StyleScopedClasses['step-title']} */ ;
/** @type {__VLS_StyleScopedClasses['step-status']} */ ;
/** @type {__VLS_StyleScopedClasses['step-time']} */ ;
/** @type {__VLS_StyleScopedClasses['steps-divider']} */ ;
/** @type {__VLS_StyleScopedClasses['thought-section']} */ ;
/** @type {__VLS_StyleScopedClasses['thought-content']} */ ;
/** @type {__VLS_StyleScopedClasses['markdown-body']} */ ;
/** @type {__VLS_StyleScopedClasses['speech-actions']} */ ;
/** @type {__VLS_StyleScopedClasses['error-bar']} */ ;
/** @type {__VLS_StyleScopedClasses['composer']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-input']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-icon-button']} */ ;
/** @type {__VLS_StyleScopedClasses['composer-send-button']} */ ;
var __VLS_dollars;
const __VLS_self = (await import('vue')).defineComponent({
    setup() {
        return {
            AudioOutlined: AudioOutlined,
            CheckCircleFilled: CheckCircleFilled,
            CloseCircleFilled: CloseCircleFilled,
            DownOutlined: DownOutlined,
            LoadingOutlined: LoadingOutlined,
            PauseCircleOutlined: PauseCircleOutlined,
            PlusOutlined: PlusOutlined,
            RobotOutlined: RobotOutlined,
            SoundOutlined: SoundOutlined,
            renderMarkdown: renderMarkdown,
            isWorkflowRunning: isWorkflowRunning,
            getWorkflowStatus: getWorkflowStatus,
            getWorkflowTitle: getWorkflowTitle,
            getWorkflowDetail: getWorkflowDetail,
            getWorkflowCountText: getWorkflowCountText,
            getStepStatusText: getStepStatusText,
            getUserInitial: getUserInitial,
            auth: auth,
            canChat: canChat,
            agentCode: agentCode,
            question: question,
            loading: loading,
            restoringConversation: restoringConversation,
            errorMsg: errorMsg,
            messages: messages,
            msgContainer: msgContainer,
            thoughtOpen: thoughtOpen,
            expandedSteps: expandedSteps,
            speech: speech,
            synth: synth,
            handleNewConversation: handleNewConversation,
            toggleSpeechInput: toggleSpeechInput,
            toggleSpeechOutput: toggleSpeechOutput,
            safeSend: safeSend,
            handleLogout: handleLogout,
        };
    },
});
export default (await import('vue')).defineComponent({
    setup() {
        return {};
    },
});
; /* PartiallyEnd: #4569/main.vue */
