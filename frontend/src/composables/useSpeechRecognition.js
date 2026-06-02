/** 浏览器语音识别 composable。使用 Web Speech API 将语音转为文本。 */
import { ref, onUnmounted } from 'vue';
export function useSpeechRecognition() {
    const isListening = ref(false);
    const isSupported = ref(false);
    const transcript = ref('');
    let recognition = null;
    // 检测浏览器支持
    const SpeechRecognitionClass = window.SpeechRecognition || window.webkitSpeechRecognition;
    isSupported.value = !!SpeechRecognitionClass;
    function start() {
        if (!isSupported.value || !SpeechRecognitionClass)
            return;
        recognition = new SpeechRecognitionClass();
        recognition.continuous = false;
        recognition.interimResults = true;
        recognition.lang = 'zh-CN';
        recognition.onresult = (event) => {
            let interim = '';
            let final = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                const result = event.results[i];
                if (result.isFinal) {
                    final += result[0].transcript;
                }
                else {
                    interim += result[0].transcript;
                }
            }
            transcript.value = final + interim;
        };
        recognition.onerror = (event) => {
            console.warn('SpeechRecognition error:', event.error);
            stop();
        };
        recognition.onend = () => {
            isListening.value = false;
        };
        recognition.start();
        isListening.value = true;
    }
    function stop() {
        if (recognition) {
            recognition.stop();
            recognition = null;
        }
        isListening.value = false;
    }
    function clearTranscript() {
        transcript.value = '';
    }
    onUnmounted(() => {
        stop();
    });
    return { isListening, isSupported, transcript, start, stop, clearTranscript };
}
