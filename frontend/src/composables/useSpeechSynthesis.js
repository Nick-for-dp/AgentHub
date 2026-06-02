/** 浏览器语音合成 composable。使用 Web Speech API 播放文本。 */
import { ref, onUnmounted } from 'vue';
export function useSpeechSynthesis() {
    const isSpeaking = ref(false);
    const isSupported = ref(false);
    isSupported.value = typeof window !== 'undefined' && 'speechSynthesis' in window;
    function speak(text) {
        if (!isSupported.value || !text)
            return;
        stop(); // 先停止当前播报
        // 去除 Markdown 标记，保留纯文本
        const plainText = text
            .replace(/```[\s\S]*?```/g, '') // 代码块
            .replace(/`([^`]+)`/g, '$1') // 行内代码
            .replace(/#{1,6}\s+/g, '') // 标题
            .replace(/[*_~>|]/g, '') // 强调/引用/表格
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // 链接
            .replace(/\n{2,}/g, '。') // 空行 → 停顿
            .replace(/\n/g, '') // 剩余换行
            .trim();
        if (!plainText)
            return;
        // 浏览器对长文本有字数限制，分段播报
        const maxLength = 200;
        const chunks = [];
        for (let i = 0; i < plainText.length; i += maxLength) {
            chunks.push(plainText.slice(i, i + maxLength));
        }
        const utterance = new SpeechSynthesisUtterance(chunks[0]);
        utterance.lang = 'zh-CN';
        utterance.rate = 1.0;
        let chunkIndex = 0;
        utterance.onend = () => {
            chunkIndex++;
            if (chunkIndex < chunks.length) {
                const nextUtterance = new SpeechSynthesisUtterance(chunks[chunkIndex]);
                nextUtterance.lang = 'zh-CN';
                nextUtterance.rate = 1.0;
                nextUtterance.onend = utterance.onend;
                window.speechSynthesis.speak(nextUtterance);
            }
            else {
                isSpeaking.value = false;
            }
        };
        utterance.onerror = () => {
            isSpeaking.value = false;
        };
        window.speechSynthesis.speak(utterance);
        isSpeaking.value = true;
    }
    function stop() {
        if (isSupported.value) {
            window.speechSynthesis.cancel();
        }
        isSpeaking.value = false;
    }
    onUnmounted(() => {
        stop();
    });
    return { isSpeaking, isSupported, speak, stop };
}
