/** Cloud TTS composable. Streams backend audio when possible and falls back to Blob playback. */

import { onUnmounted, ref } from 'vue'
import { fetchSpeechAudio, requestSpeechAudio } from '../api/audio'

const MPEG_MIME = 'audio/mpeg'
const MPEG_MIME_CANDIDATES = [MPEG_MIME, 'audio/mpeg; codecs="mp3"']

function getSupportedMpegMime(): string | null {
  if (typeof MediaSource === 'undefined') return null
  return MPEG_MIME_CANDIDATES.find(mime => MediaSource.isTypeSupported(mime)) || null
}

export function useCloudSpeechSynthesis() {
  const isSpeaking = ref(false)
  const isLoading = ref(false)
  const isSupported = ref(typeof Audio !== 'undefined')
  const error = ref('')

  let audio: HTMLAudioElement | null = null
  let objectUrl: string | null = null
  let mediaSource: MediaSource | null = null
  let abortController: AbortController | null = null
  let playSeq = 0

  async function speak(text: string): Promise<void> {
    if (!isSupported.value || !text.trim()) return
    stop()
    const seq = playSeq + 1
    playSeq = seq
    isLoading.value = true
    error.value = ''
    try {
      const streamMime = getSupportedMpegMime()
      if (streamMime) {
        try {
          await streamAndPlay(text, seq, streamMime)
        } catch (err) {
          if (err instanceof DOMException && err.name === 'AbortError') throw err
          cleanupPlayback()
          await fetchAndPlay(text, seq)
        }
      } else {
        await fetchAndPlay(text, seq)
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return
      error.value = err instanceof Error ? err.message : '语音播报失败'
      stop()
    } finally {
      if (seq === playSeq) {
        isLoading.value = false
      }
    }
  }

  async function fetchAndPlay(text: string, seq: number): Promise<void> {
    abortController = new AbortController()
    const blob = await fetchSpeechAudio(text, undefined, abortController.signal)
    if (seq !== playSeq) return
    objectUrl = URL.createObjectURL(blob)
    audio = createAudio(objectUrl, seq)
    await audio.play()
    if (seq === playSeq) {
      isSpeaking.value = true
    }
  }

  async function streamAndPlay(text: string, seq: number, streamMime: string): Promise<void> {
    abortController = new AbortController()
    const response = await requestSpeechAudio(text, undefined, abortController.signal)
    if (!response.body) {
      throw new Error('语音合成响应为空')
    }

    const contentType = response.headers.get('content-type') || MPEG_MIME
    if (!contentType.includes('mpeg')) {
      throw new Error(`不支持的语音格式：${contentType}`)
    }

    mediaSource = new MediaSource()
    objectUrl = URL.createObjectURL(mediaSource)
    audio = createAudio(objectUrl, seq)

    await new Promise<void>((resolve, reject) => {
      const currentAudio = audio
      const currentMediaSource = mediaSource
      if (!currentAudio || !currentMediaSource) {
        reject(new Error('语音播放器初始化失败'))
        return
      }

      currentMediaSource.addEventListener('sourceopen', () => {
        void pumpMediaSource(response, currentMediaSource, seq, streamMime).catch(reject)
      }, { once: true })

      currentAudio.addEventListener('canplay', () => {
        if (seq !== playSeq) return
        isLoading.value = false
        isSpeaking.value = true
        void currentAudio.play().then(resolve).catch(reject)
      }, { once: true })
      currentAudio.addEventListener('error', () => {
        reject(new Error('语音播报失败'))
      }, { once: true })
    })
  }

  async function pumpMediaSource(
    response: Response,
    source: MediaSource,
    seq: number,
    streamMime: string,
  ): Promise<void> {
    const reader = response.body?.getReader()
    if (!reader) {
      throw new Error('语音合成响应为空')
    }

    const sourceBuffer = source.addSourceBuffer(streamMime)
    try {
      while (seq === playSeq) {
        const { done, value } = await reader.read()
        if (done) break
        if (!value) continue
        await appendBuffer(sourceBuffer, copyChunk(value))
      }
      if (source.readyState === 'open') {
        source.endOfStream()
      }
    } finally {
      reader.releaseLock()
    }
  }

  function copyChunk(value: Uint8Array): ArrayBuffer {
    const buffer = new ArrayBuffer(value.byteLength)
    new Uint8Array(buffer).set(value)
    return buffer
  }

  function appendBuffer(sourceBuffer: SourceBuffer, value: ArrayBuffer): Promise<void> {
    return new Promise((resolve, reject) => {
      const cleanup = () => {
        sourceBuffer.removeEventListener('updateend', onUpdateEnd)
        sourceBuffer.removeEventListener('error', onError)
      }
      const onUpdateEnd = () => {
        cleanup()
        resolve()
      }
      const onError = () => {
        cleanup()
        reject(new Error('语音流播放失败'))
      }

      sourceBuffer.addEventListener('updateend', onUpdateEnd, { once: true })
      sourceBuffer.addEventListener('error', onError, { once: true })
      sourceBuffer.appendBuffer(value)
    })
  }

  function createAudio(src: string, seq: number): HTMLAudioElement {
    const player = new Audio(src)
    player.onended = () => {
      if (seq === playSeq) stop()
    }
    player.onerror = () => {
      if (seq === playSeq) {
        error.value = '语音播报失败'
        stop()
      }
    }
    return player
  }

  function stop(): void {
    playSeq += 1
    cleanupPlayback()
    isSpeaking.value = false
    isLoading.value = false
  }

  function cleanupPlayback(): void {
    abortController?.abort()
    abortController = null
    if (audio) {
      audio.pause()
      audio.src = ''
      audio = null
    }
    if (mediaSource?.readyState === 'open') {
      try {
        mediaSource.endOfStream()
      } catch {
        // MediaSource may be mid-update; releasing the object URL is enough for cleanup.
      }
    }
    mediaSource = null
    if (objectUrl) {
      URL.revokeObjectURL(objectUrl)
      objectUrl = null
    }
  }

  onUnmounted(() => {
    stop()
  })

  return { isSpeaking, isLoading, isSupported, error, speak, stop }
}
