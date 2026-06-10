import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue';
import { useRouter } from 'vue-router';
import { AudioOutlined, CheckCircleFilled, CloseCircleFilled, DeleteOutlined, DownOutlined, LoadingOutlined, MenuOutlined, PauseCircleOutlined, PlusOutlined, RobotOutlined, SoundOutlined, } from '@ant-design/icons-vue';
import { marked } from 'marked';
import DOMPurify from 'dompurify';
import { streamChat } from '../../api/chat';
import { createConversation, deleteConversation, getConversation, getConversationMessages, getCurrentConversation, listConversations, } from '../../api/conversations';
import { useAuthStore } from '../../stores/auth';
import { useCloudSpeechRecognition } from '../../composables/useCloudSpeechRecognition';
import { useCloudSpeechSynthesis } from '../../composables/useCloudSpeechSynthesis';
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
const conversationList = ref([]);
const loadingConversations = ref(false);
const conversationPage = ref(1);
const conversationTotal = ref(0);
const conversationPageSize = 30;
const switchingConversationId = ref(null);
const deletingConversationId = ref(null);
let switchRequestSeq = 0;
const hasMoreConversations = computed(() => conversationList.value.length < conversationTotal.value);
const windowWidth = ref(window.innerWidth);
const isMobile = computed(() => windowWidth.value < 768);
const sidebarVisible = ref(window.innerWidth >= 768);
// 语音能力
const speech = useCloudSpeechRecognition();
const synth = useCloudSpeechSynthesis();
const speechPlaceholder = computed(() => {
    if (speech.isRecording.value)
        return '正在录音，松开发送识别';
    if (speech.isTranscribing.value)
        return '正在转写语音...';
    return '输入问题，Enter 发送';
});
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
function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();
    const isToday = date.toDateString() === now.toDateString();
    if (isToday) {
        return date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' });
    }
    return date.toLocaleDateString('zh-CN', { month: 'short', day: 'numeric' });
}
function mergeConversationList(items, append) {
    const existing = append ? conversationList.value : [];
    const byId = new Map(existing.map(item => [item.id, item]));
    for (const item of items) {
        byId.set(item.id, item);
    }
    conversationList.value = Array.from(byId.values()).sort((a, b) => new Date(b.last_message_at).getTime() - new Date(a.last_message_at).getTime());
}
async function loadConversationList(page = 1, append = false) {
    if (!auth.isLoggedIn)
        return;
    loadingConversations.value = true;
    try {
        const result = await listConversations(agentCode.value, page, conversationPageSize);
        conversationPage.value = result.page;
        conversationTotal.value = result.total;
        mergeConversationList(result.items, append);
    }
    catch {
        // 静默失败，不影响聊天主体验
    }
    finally {
        loadingConversations.value = false;
    }
}
async function refreshConversationList() {
    await loadConversationList(1, false);
}
async function loadMoreConversations() {
    if (loadingConversations.value || !hasMoreConversations.value)
        return;
    await loadConversationList(conversationPage.value + 1, true);
}
async function deleteConversationItem(id) {
    if (deletingConversationId.value || loading.value)
        return;
    deletingConversationId.value = id;
    errorMsg.value = '';
    try {
        await deleteConversation(id);
        conversationList.value = conversationList.value.filter(item => item.id !== id);
        conversationTotal.value = Math.max(0, conversationTotal.value - 1);
        if (conversationId.value === id) {
            conversationId.value = null;
            conversationTitle.value = '';
            messages.value = [];
            expandedSteps.value = {};
            syncConversationUrl(null);
        }
    }
    catch {
        errorMsg.value = '删除会话失败，请稍后重试';
    }
    finally {
        deletingConversationId.value = null;
    }
}
async function switchConversation(id) {
    if (id === conversationId.value || loading.value)
        return;
    const requestSeq = ++switchRequestSeq;
    switchingConversationId.value = id;
    errorMsg.value = '';
    if (isMobile.value) {
        sidebarVisible.value = false;
    }
    try {
        const [conversation, storedMessages] = await Promise.all([
            getConversation(id),
            getConversationMessages(id),
        ]);
        if (requestSeq !== switchRequestSeq)
            return;
        if (conversation.agent_code !== agentCode.value) {
            throw new Error('conversation agent mismatch');
        }
        conversationId.value = conversation.id;
        conversationTitle.value = conversation.title;
        messages.value = storedMessages
            .map(mapConversationMessage)
            .filter((item) => item !== null);
        syncConversationUrl(conversation.id);
        await scrollBottom();
    }
    catch {
        if (requestSeq !== switchRequestSeq)
            return;
        errorMsg.value = '切换会话失败，请稍后重试';
    }
    finally {
        if (requestSeq === switchRequestSeq) {
            switchingConversationId.value = null;
        }
    }
}
async function restoreCurrentConversation() {
    if (!auth.isLoggedIn)
        return;
    restoringConversation.value = true;
    try {
        const routeConversationId = router.currentRoute.value.query.conversation_id;
        const requestedId = typeof routeConversationId === 'string' ? routeConversationId : null;
        let currentState = requestedId ? null : await getCurrentConversation(agentCode.value);
        let current = requestedId ? await getConversation(requestedId) : currentState?.conversation;
        let storedMessages = requestedId
            ? await getConversationMessages(requestedId)
            : currentState?.messages ?? [];
        if (current && current.agent_code !== agentCode.value) {
            syncConversationUrl(null);
            currentState = await getCurrentConversation(agentCode.value);
            current = currentState.conversation;
            storedMessages = currentState.messages;
        }
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
    const conversation = await createConversation(agentCode.value);
    conversationId.value = conversation.id;
    conversationTitle.value = conversation.title;
    messages.value = [];
    expandedSteps.value = {};
    syncConversationUrl(conversation.id);
    await scrollBottom();
    if (isMobile.value) {
        sidebarVisible.value = false;
    }
    await refreshConversationList();
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
// 语音输入：长按录音，松开后将云端识别结果填入输入框
function startSpeechInput() {
    if (speech.isRecording.value || speech.isTranscribing.value || !canChat.value)
        return;
    speech.clearTranscript();
    void speech.start({
        onEnd: (text) => {
            void finishSpeechInput(text);
        },
        onError: (error) => {
            errorMsg.value = getSpeechErrorMessage(error);
        },
    });
}
function stopSpeechInput() {
    if (!speech.isRecording.value)
        return;
    void speech.stop();
}
function finishSpeechInput(text) {
    const recognizedText = (text || speech.transcript.value).trim();
    if (!recognizedText) {
        speech.clearTranscript();
        return;
    }
    question.value = recognizedText;
    speech.clearTranscript();
}
function getSpeechErrorMessage(error) {
    if (error.includes('Permission') || error.includes('NotAllowed')) {
        return '浏览器未允许使用麦克风，请检查权限设置';
    }
    if (error.includes('uploaded WAV')) {
        return '录音格式不符合要求，请重试';
    }
    return error || '语音输入失败，请重试';
}
// 语音播报：播放/停止
function toggleSpeechOutput(text) {
    if (synth.isSpeaking.value) {
        synth.stop();
    }
    else {
        void synth.speak(text);
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
function onWindowResize() {
    const wasMobile = isMobile.value;
    windowWidth.value = window.innerWidth;
    if (wasMobile && !isMobile.value) {
        sidebarVisible.value = true;
    }
}
onMounted(() => {
    window.addEventListener('resize', onWindowResize);
    void restoreCurrentConversation();
    if (auth.isLoggedIn) {
        void refreshConversationList();
    }
});
onUnmounted(() => {
    window.removeEventListener('resize', onWindowResize);
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
    const current = (question.value || speech.transcript.value).trim();
    if (!current || loading.value || !canChat.value)
        return;
    question.value = current;
    speech.clearTranscript();
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
        if (auth.isLoggedIn) {
            await refreshConversationList();
            const currentConversation = conversationList.value.find(item => item.id === conversationId.value);
            if (currentConversation) {
                conversationTitle.value = currentConversation.title;
            }
        }
        await scrollBottom();
    }
}
debugger; /* PartiallyEnd: #3632/scriptSetup.vue */
const __VLS_ctx = {};
let __VLS_components;
let __VLS_directives;
/** @type {__VLS_StyleScopedClasses['conversation-sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['conversation-sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-collapsed']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-toggle-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-panel']} */ ;
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
/** @type {__VLS_StyleScopedClasses['conversation-sidebar']} */ ;
/** @type {__VLS_StyleScopedClasses['conversation-sidebar']} */ ;
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
if (__VLS_ctx.auth.isLoggedIn) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.aside, __VLS_intrinsicElements.aside)({
        ...{ class: (['conversation-sidebar', {
                    'sidebar-open': __VLS_ctx.sidebarVisible,
                    'sidebar-collapsed': !__VLS_ctx.sidebarVisible,
                    'sidebar-mobile': __VLS_ctx.isMobile
                }]) },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "sidebar-header" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
        ...{ class: "sidebar-title" },
    });
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "sidebar-list" },
    });
    for (const [conv] of __VLS_getVForSourceType((__VLS_ctx.conversationList))) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ onClick: (...[$event]) => {
                    if (!(__VLS_ctx.auth.isLoggedIn))
                        return;
                    __VLS_ctx.switchConversation(conv.id);
                } },
            key: (conv.id),
            ...{ class: (['sidebar-item', {
                        active: conv.id === __VLS_ctx.conversationId,
                        switching: conv.id === __VLS_ctx.switchingConversationId,
                    }]) },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "sidebar-item-main" },
        });
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "sidebar-item-title" },
        });
        (conv.title || '新对话');
        __VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
            ...{ class: "sidebar-item-time" },
        });
        (__VLS_ctx.formatTime(conv.last_message_at));
        const __VLS_0 = {}.APopconfirm;
        /** @type {[typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, typeof __VLS_components.APopconfirm, typeof __VLS_components.aPopconfirm, ]} */ ;
        // @ts-ignore
        const __VLS_1 = __VLS_asFunctionalComponent(__VLS_0, new __VLS_0({
            ...{ 'onConfirm': {} },
            title: "确认删除该会话？",
            okText: "删除",
            cancelText: "取消",
            placement: "right",
        }));
        const __VLS_2 = __VLS_1({
            ...{ 'onConfirm': {} },
            title: "确认删除该会话？",
            okText: "删除",
            cancelText: "取消",
            placement: "right",
        }, ...__VLS_functionalComponentArgsRest(__VLS_1));
        let __VLS_4;
        let __VLS_5;
        let __VLS_6;
        const __VLS_7 = {
            onConfirm: (...[$event]) => {
                if (!(__VLS_ctx.auth.isLoggedIn))
                    return;
                __VLS_ctx.deleteConversationItem(conv.id);
            }
        };
        __VLS_3.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
            ...{ onClick: () => { } },
            type: "button",
            ...{ class: "sidebar-delete-btn" },
            title: "删除会话",
            disabled: (__VLS_ctx.deletingConversationId === conv.id),
        });
        const __VLS_8 = {}.DeleteOutlined;
        /** @type {[typeof __VLS_components.DeleteOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_9 = __VLS_asFunctionalComponent(__VLS_8, new __VLS_8({}));
        const __VLS_10 = __VLS_9({}, ...__VLS_functionalComponentArgsRest(__VLS_9));
        var __VLS_3;
    }
    if (__VLS_ctx.conversationList.length === 0 && !__VLS_ctx.loadingConversations) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "sidebar-empty" },
        });
    }
    if (__VLS_ctx.loadingConversations) {
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "sidebar-loading" },
        });
    }
    else if (__VLS_ctx.hasMoreConversations) {
        const __VLS_12 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_13 = __VLS_asFunctionalComponent(__VLS_12, new __VLS_12({
            ...{ 'onClick': {} },
            block: true,
            size: "small",
            ...{ class: "sidebar-load-more" },
        }));
        const __VLS_14 = __VLS_13({
            ...{ 'onClick': {} },
            block: true,
            size: "small",
            ...{ class: "sidebar-load-more" },
        }, ...__VLS_functionalComponentArgsRest(__VLS_13));
        let __VLS_16;
        let __VLS_17;
        let __VLS_18;
        const __VLS_19 = {
            onClick: (__VLS_ctx.loadMoreConversations)
        };
        __VLS_15.slots.default;
        var __VLS_15;
    }
}
if (__VLS_ctx.isMobile && __VLS_ctx.sidebarVisible) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.isMobile && __VLS_ctx.sidebarVisible))
                    return;
                __VLS_ctx.sidebarVisible = false;
            } },
        ...{ class: "sidebar-overlay" },
    });
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.section, __VLS_intrinsicElements.section)({
    ...{ class: (['chat-panel', { 'sidebar-hidden-panel': !__VLS_ctx.auth.isLoggedIn || !__VLS_ctx.sidebarVisible }]) },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.header, __VLS_intrinsicElements.header)({
    ...{ class: "chat-header" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-left" },
});
if (__VLS_ctx.auth.isLoggedIn) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.button, __VLS_intrinsicElements.button)({
        ...{ onClick: (...[$event]) => {
                if (!(__VLS_ctx.auth.isLoggedIn))
                    return;
                __VLS_ctx.sidebarVisible = !__VLS_ctx.sidebarVisible;
            } },
        type: "button",
        ...{ class: "sidebar-toggle-btn" },
        title: (__VLS_ctx.sidebarVisible ? '收起历史会话' : '展开历史会话'),
        'aria-label': (__VLS_ctx.sidebarVisible ? '收起历史会话' : '展开历史会话'),
    });
    const __VLS_20 = {}.MenuOutlined;
    /** @type {[typeof __VLS_components.MenuOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_21 = __VLS_asFunctionalComponent(__VLS_20, new __VLS_20({}));
    const __VLS_22 = __VLS_21({}, ...__VLS_functionalComponentArgsRest(__VLS_21));
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.span, __VLS_intrinsicElements.span)({
    ...{ class: "header-title" },
});
__VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
    ...{ class: "header-right" },
});
const __VLS_24 = {}.ATooltip;
/** @type {[typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, typeof __VLS_components.ATooltip, typeof __VLS_components.aTooltip, ]} */ ;
// @ts-ignore
const __VLS_25 = __VLS_asFunctionalComponent(__VLS_24, new __VLS_24({
    title: "新对话",
}));
const __VLS_26 = __VLS_25({
    title: "新对话",
}, ...__VLS_functionalComponentArgsRest(__VLS_25));
__VLS_27.slots.default;
if (__VLS_ctx.auth.isLoggedIn) {
    const __VLS_28 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_29 = __VLS_asFunctionalComponent(__VLS_28, new __VLS_28({
        ...{ 'onClick': {} },
        shape: "circle",
        disabled: (__VLS_ctx.loading || __VLS_ctx.restoringConversation),
        ...{ class: "header-icon-button" },
        'aria-label': "新对话",
    }));
    const __VLS_30 = __VLS_29({
        ...{ 'onClick': {} },
        shape: "circle",
        disabled: (__VLS_ctx.loading || __VLS_ctx.restoringConversation),
        ...{ class: "header-icon-button" },
        'aria-label': "新对话",
    }, ...__VLS_functionalComponentArgsRest(__VLS_29));
    let __VLS_32;
    let __VLS_33;
    let __VLS_34;
    const __VLS_35 = {
        onClick: (__VLS_ctx.handleNewConversation)
    };
    __VLS_31.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_31.slots;
        const __VLS_36 = {}.PlusOutlined;
        /** @type {[typeof __VLS_components.PlusOutlined, ]} */ ;
        // @ts-ignore
        const __VLS_37 = __VLS_asFunctionalComponent(__VLS_36, new __VLS_36({}));
        const __VLS_38 = __VLS_37({}, ...__VLS_functionalComponentArgsRest(__VLS_37));
    }
    var __VLS_31;
}
var __VLS_27;
if (__VLS_ctx.auth.isLoggedIn && __VLS_ctx.auth.currentUser) {
    const __VLS_40 = {}.ADropdown;
    /** @type {[typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, typeof __VLS_components.ADropdown, typeof __VLS_components.aDropdown, ]} */ ;
    // @ts-ignore
    const __VLS_41 = __VLS_asFunctionalComponent(__VLS_40, new __VLS_40({
        trigger: "click",
        placement: "bottomRight",
    }));
    const __VLS_42 = __VLS_41({
        trigger: "click",
        placement: "bottomRight",
    }, ...__VLS_functionalComponentArgsRest(__VLS_41));
    __VLS_43.slots.default;
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
        const { overlay: __VLS_thisSlot } = __VLS_43.slots;
        const __VLS_44 = {}.AMenu;
        /** @type {[typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, typeof __VLS_components.AMenu, typeof __VLS_components.aMenu, ]} */ ;
        // @ts-ignore
        const __VLS_45 = __VLS_asFunctionalComponent(__VLS_44, new __VLS_44({}));
        const __VLS_46 = __VLS_45({}, ...__VLS_functionalComponentArgsRest(__VLS_45));
        __VLS_47.slots.default;
        const __VLS_48 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_49 = __VLS_asFunctionalComponent(__VLS_48, new __VLS_48({
            key: "user",
            disabled: true,
        }));
        const __VLS_50 = __VLS_49({
            key: "user",
            disabled: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_49));
        __VLS_51.slots.default;
        (__VLS_ctx.auth.currentUser.name);
        var __VLS_51;
        const __VLS_52 = {}.AMenuDivider;
        /** @type {[typeof __VLS_components.AMenuDivider, typeof __VLS_components.aMenuDivider, ]} */ ;
        // @ts-ignore
        const __VLS_53 = __VLS_asFunctionalComponent(__VLS_52, new __VLS_52({}));
        const __VLS_54 = __VLS_53({}, ...__VLS_functionalComponentArgsRest(__VLS_53));
        const __VLS_56 = {}.AMenuItem;
        /** @type {[typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, typeof __VLS_components.AMenuItem, typeof __VLS_components.aMenuItem, ]} */ ;
        // @ts-ignore
        const __VLS_57 = __VLS_asFunctionalComponent(__VLS_56, new __VLS_56({
            ...{ 'onClick': {} },
            key: "logout",
        }));
        const __VLS_58 = __VLS_57({
            ...{ 'onClick': {} },
            key: "logout",
        }, ...__VLS_functionalComponentArgsRest(__VLS_57));
        let __VLS_60;
        let __VLS_61;
        let __VLS_62;
        const __VLS_63 = {
            onClick: (__VLS_ctx.handleLogout)
        };
        __VLS_59.slots.default;
        var __VLS_59;
        var __VLS_47;
    }
    var __VLS_43;
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
    const __VLS_64 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_65 = __VLS_asFunctionalComponent(__VLS_64, new __VLS_64({
        ...{ 'onClick': {} },
        type: "primary",
    }));
    const __VLS_66 = __VLS_65({
        ...{ 'onClick': {} },
        type: "primary",
    }, ...__VLS_functionalComponentArgsRest(__VLS_65));
    let __VLS_68;
    let __VLS_69;
    let __VLS_70;
    const __VLS_71 = {
        onClick: (...[$event]) => {
            if (!(!__VLS_ctx.canChat))
                return;
            __VLS_ctx.$router.push('/login');
        }
    };
    __VLS_67.slots.default;
    var __VLS_67;
}
else if (__VLS_ctx.messages.length === 0 && !__VLS_ctx.loading) {
    __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
        ...{ class: "welcome-banner" },
    });
    const __VLS_72 = {}.RobotOutlined;
    /** @type {[typeof __VLS_components.RobotOutlined, ]} */ ;
    // @ts-ignore
    const __VLS_73 = __VLS_asFunctionalComponent(__VLS_72, new __VLS_72({
        ...{ class: "welcome-icon" },
    }));
    const __VLS_74 = __VLS_73({
        ...{ class: "welcome-icon" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_73));
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
            const __VLS_76 = {}.LoadingOutlined;
            /** @type {[typeof __VLS_components.LoadingOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_77 = __VLS_asFunctionalComponent(__VLS_76, new __VLS_76({
                spin: true,
            }));
            const __VLS_78 = __VLS_77({
                spin: true,
            }, ...__VLS_functionalComponentArgsRest(__VLS_77));
        }
        else if (__VLS_ctx.getWorkflowStatus(msg) === 'failed') {
            const __VLS_80 = {}.CloseCircleFilled;
            /** @type {[typeof __VLS_components.CloseCircleFilled, ]} */ ;
            // @ts-ignore
            const __VLS_81 = __VLS_asFunctionalComponent(__VLS_80, new __VLS_80({}));
            const __VLS_82 = __VLS_81({}, ...__VLS_functionalComponentArgsRest(__VLS_81));
        }
        else {
            const __VLS_84 = {}.CheckCircleFilled;
            /** @type {[typeof __VLS_components.CheckCircleFilled, ]} */ ;
            // @ts-ignore
            const __VLS_85 = __VLS_asFunctionalComponent(__VLS_84, new __VLS_84({}));
            const __VLS_86 = __VLS_85({}, ...__VLS_functionalComponentArgsRest(__VLS_85));
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
            const __VLS_88 = {}.DownOutlined;
            /** @type {[typeof __VLS_components.DownOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_89 = __VLS_asFunctionalComponent(__VLS_88, new __VLS_88({
                ...{ class: (['workflow-chevron', { expanded: __VLS_ctx.expandedSteps[msg.id] }]) },
            }));
            const __VLS_90 = __VLS_89({
                ...{ class: (['workflow-chevron', { expanded: __VLS_ctx.expandedSteps[msg.id] }]) },
            }, ...__VLS_functionalComponentArgsRest(__VLS_89));
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
        const __VLS_92 = {}.ACollapse;
        /** @type {[typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, typeof __VLS_components.ACollapse, typeof __VLS_components.aCollapse, ]} */ ;
        // @ts-ignore
        const __VLS_93 = __VLS_asFunctionalComponent(__VLS_92, new __VLS_92({
            activeKey: (__VLS_ctx.thoughtOpen ? ['thought'] : []),
            ghost: true,
        }));
        const __VLS_94 = __VLS_93({
            activeKey: (__VLS_ctx.thoughtOpen ? ['thought'] : []),
            ghost: true,
        }, ...__VLS_functionalComponentArgsRest(__VLS_93));
        __VLS_95.slots.default;
        const __VLS_96 = {}.ACollapsePanel;
        /** @type {[typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, typeof __VLS_components.ACollapsePanel, typeof __VLS_components.aCollapsePanel, ]} */ ;
        // @ts-ignore
        const __VLS_97 = __VLS_asFunctionalComponent(__VLS_96, new __VLS_96({
            key: "thought",
            header: "思考过程",
        }));
        const __VLS_98 = __VLS_97({
            key: "thought",
            header: "思考过程",
        }, ...__VLS_functionalComponentArgsRest(__VLS_97));
        __VLS_99.slots.default;
        __VLS_asFunctionalElement(__VLS_intrinsicElements.div, __VLS_intrinsicElements.div)({
            ...{ class: "thought-content" },
        });
        (msg.displayThought);
        var __VLS_99;
        var __VLS_95;
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
        const __VLS_100 = {}.AButton;
        /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
        // @ts-ignore
        const __VLS_101 = __VLS_asFunctionalComponent(__VLS_100, new __VLS_100({
            ...{ 'onClick': {} },
            size: "small",
            type: "link",
            loading: (__VLS_ctx.synth.isLoading.value),
            title: (__VLS_ctx.synth.isSpeaking.value ? '停止播报' : '播报回复'),
        }));
        const __VLS_102 = __VLS_101({
            ...{ 'onClick': {} },
            size: "small",
            type: "link",
            loading: (__VLS_ctx.synth.isLoading.value),
            title: (__VLS_ctx.synth.isSpeaking.value ? '停止播报' : '播报回复'),
        }, ...__VLS_functionalComponentArgsRest(__VLS_101));
        let __VLS_104;
        let __VLS_105;
        let __VLS_106;
        const __VLS_107 = {
            onClick: (...[$event]) => {
                if (!(msg.role === 'assistant' && msg.content && __VLS_ctx.synth.isSupported.value))
                    return;
                __VLS_ctx.toggleSpeechOutput(msg.content);
            }
        };
        __VLS_103.slots.default;
        if (__VLS_ctx.synth.isSpeaking.value) {
            const __VLS_108 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_109 = __VLS_asFunctionalComponent(__VLS_108, new __VLS_108({}));
            const __VLS_110 = __VLS_109({}, ...__VLS_functionalComponentArgsRest(__VLS_109));
        }
        else {
            const __VLS_112 = {}.SoundOutlined;
            /** @type {[typeof __VLS_components.SoundOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_113 = __VLS_asFunctionalComponent(__VLS_112, new __VLS_112({}));
            const __VLS_114 = __VLS_113({}, ...__VLS_functionalComponentArgsRest(__VLS_113));
        }
        var __VLS_103;
    }
}
if (__VLS_ctx.errorMsg) {
    const __VLS_116 = {}.AAlert;
    /** @type {[typeof __VLS_components.AAlert, typeof __VLS_components.aAlert, ]} */ ;
    // @ts-ignore
    const __VLS_117 = __VLS_asFunctionalComponent(__VLS_116, new __VLS_116({
        ...{ 'onClose': {} },
        type: "error",
        message: (__VLS_ctx.errorMsg),
        showIcon: true,
        closable: true,
        ...{ class: "error-bar" },
    }));
    const __VLS_118 = __VLS_117({
        ...{ 'onClose': {} },
        type: "error",
        message: (__VLS_ctx.errorMsg),
        showIcon: true,
        closable: true,
        ...{ class: "error-bar" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_117));
    let __VLS_120;
    let __VLS_121;
    let __VLS_122;
    const __VLS_123 = {
        onClose: (...[$event]) => {
            if (!(__VLS_ctx.errorMsg))
                return;
            __VLS_ctx.errorMsg = '';
        }
    };
    var __VLS_119;
}
__VLS_asFunctionalElement(__VLS_intrinsicElements.footer, __VLS_intrinsicElements.footer)({
    ...{ class: "composer" },
});
const __VLS_124 = {}.ATextarea;
/** @type {[typeof __VLS_components.ATextarea, typeof __VLS_components.aTextarea, ]} */ ;
// @ts-ignore
const __VLS_125 = __VLS_asFunctionalComponent(__VLS_124, new __VLS_124({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.question),
    ...{ class: "composer-input" },
    autoSize: ({ minRows: 1, maxRows: 4 }),
    placeholder: (__VLS_ctx.speechPlaceholder),
    disabled: (!__VLS_ctx.canChat || __VLS_ctx.speech.isRecording.value || __VLS_ctx.speech.isTranscribing.value),
}));
const __VLS_126 = __VLS_125({
    ...{ 'onPressEnter': {} },
    value: (__VLS_ctx.question),
    ...{ class: "composer-input" },
    autoSize: ({ minRows: 1, maxRows: 4 }),
    placeholder: (__VLS_ctx.speechPlaceholder),
    disabled: (!__VLS_ctx.canChat || __VLS_ctx.speech.isRecording.value || __VLS_ctx.speech.isTranscribing.value),
}, ...__VLS_functionalComponentArgsRest(__VLS_125));
let __VLS_128;
let __VLS_129;
let __VLS_130;
const __VLS_131 = {
    onPressEnter: (__VLS_ctx.safeSend)
};
var __VLS_127;
if (__VLS_ctx.speech.isSupported.value) {
    const __VLS_132 = {}.AButton;
    /** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
    // @ts-ignore
    const __VLS_133 = __VLS_asFunctionalComponent(__VLS_132, new __VLS_132({
        ...{ 'onMousedown': {} },
        ...{ 'onMouseup': {} },
        ...{ 'onMouseleave': {} },
        ...{ 'onTouchstart': {} },
        ...{ 'onTouchend': {} },
        type: (__VLS_ctx.speech.isRecording.value ? 'primary' : 'default'),
        danger: (__VLS_ctx.speech.isRecording.value),
        loading: (__VLS_ctx.speech.isTranscribing.value),
        title: (__VLS_ctx.speech.isRecording.value ? '松开结束录音' : '长按语音输入'),
        size: "large",
        ...{ class: "composer-icon-button" },
    }));
    const __VLS_134 = __VLS_133({
        ...{ 'onMousedown': {} },
        ...{ 'onMouseup': {} },
        ...{ 'onMouseleave': {} },
        ...{ 'onTouchstart': {} },
        ...{ 'onTouchend': {} },
        type: (__VLS_ctx.speech.isRecording.value ? 'primary' : 'default'),
        danger: (__VLS_ctx.speech.isRecording.value),
        loading: (__VLS_ctx.speech.isTranscribing.value),
        title: (__VLS_ctx.speech.isRecording.value ? '松开结束录音' : '长按语音输入'),
        size: "large",
        ...{ class: "composer-icon-button" },
    }, ...__VLS_functionalComponentArgsRest(__VLS_133));
    let __VLS_136;
    let __VLS_137;
    let __VLS_138;
    const __VLS_139 = {
        onMousedown: (__VLS_ctx.startSpeechInput)
    };
    const __VLS_140 = {
        onMouseup: (__VLS_ctx.stopSpeechInput)
    };
    const __VLS_141 = {
        onMouseleave: (__VLS_ctx.stopSpeechInput)
    };
    const __VLS_142 = {
        onTouchstart: (__VLS_ctx.startSpeechInput)
    };
    const __VLS_143 = {
        onTouchend: (__VLS_ctx.stopSpeechInput)
    };
    __VLS_135.slots.default;
    {
        const { icon: __VLS_thisSlot } = __VLS_135.slots;
        if (__VLS_ctx.speech.isRecording.value) {
            const __VLS_144 = {}.PauseCircleOutlined;
            /** @type {[typeof __VLS_components.PauseCircleOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_145 = __VLS_asFunctionalComponent(__VLS_144, new __VLS_144({}));
            const __VLS_146 = __VLS_145({}, ...__VLS_functionalComponentArgsRest(__VLS_145));
        }
        else {
            const __VLS_148 = {}.AudioOutlined;
            /** @type {[typeof __VLS_components.AudioOutlined, ]} */ ;
            // @ts-ignore
            const __VLS_149 = __VLS_asFunctionalComponent(__VLS_148, new __VLS_148({}));
            const __VLS_150 = __VLS_149({}, ...__VLS_functionalComponentArgsRest(__VLS_149));
        }
    }
    var __VLS_135;
}
const __VLS_152 = {}.AButton;
/** @type {[typeof __VLS_components.AButton, typeof __VLS_components.aButton, typeof __VLS_components.AButton, typeof __VLS_components.aButton, ]} */ ;
// @ts-ignore
const __VLS_153 = __VLS_asFunctionalComponent(__VLS_152, new __VLS_152({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    disabled: (!__VLS_ctx.canChat || (!__VLS_ctx.question.trim() && !__VLS_ctx.speech.transcript.value)),
    size: "large",
    ...{ class: "composer-send-button" },
}));
const __VLS_154 = __VLS_153({
    ...{ 'onClick': {} },
    type: "primary",
    loading: (__VLS_ctx.loading),
    disabled: (!__VLS_ctx.canChat || (!__VLS_ctx.question.trim() && !__VLS_ctx.speech.transcript.value)),
    size: "large",
    ...{ class: "composer-send-button" },
}, ...__VLS_functionalComponentArgsRest(__VLS_153));
let __VLS_156;
let __VLS_157;
let __VLS_158;
const __VLS_159 = {
    onClick: (__VLS_ctx.safeSend)
};
__VLS_155.slots.default;
var __VLS_155;
/** @type {__VLS_StyleScopedClasses['chat-page']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-header']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-title']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-list']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item-main']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item-title']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-item-time']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-delete-btn']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-empty']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-loading']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-load-more']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-overlay']} */ ;
/** @type {__VLS_StyleScopedClasses['chat-header']} */ ;
/** @type {__VLS_StyleScopedClasses['header-left']} */ ;
/** @type {__VLS_StyleScopedClasses['sidebar-toggle-btn']} */ ;
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
            DeleteOutlined: DeleteOutlined,
            DownOutlined: DownOutlined,
            LoadingOutlined: LoadingOutlined,
            MenuOutlined: MenuOutlined,
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
            conversationId: conversationId,
            conversationList: conversationList,
            loadingConversations: loadingConversations,
            switchingConversationId: switchingConversationId,
            deletingConversationId: deletingConversationId,
            hasMoreConversations: hasMoreConversations,
            isMobile: isMobile,
            sidebarVisible: sidebarVisible,
            speech: speech,
            synth: synth,
            speechPlaceholder: speechPlaceholder,
            formatTime: formatTime,
            loadMoreConversations: loadMoreConversations,
            deleteConversationItem: deleteConversationItem,
            switchConversation: switchConversation,
            handleNewConversation: handleNewConversation,
            startSpeechInput: startSpeechInput,
            stopSpeechInput: stopSpeechInput,
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
