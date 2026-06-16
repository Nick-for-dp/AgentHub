/** Cloud ASR composable. Records browser audio and sends 16k mono WAV to backend ASR. */

import { onUnmounted, ref } from 'vue'
import { transcribeAudio } from '../api/audio'

interface SpeechRecognitionStartOptions {
  onEnd?: (transcript: string) => void
  onError?: (error: string) => void
}

export function useCloudSpeechRecognition() {
  const isStarting = ref(false)
  const isRecording = ref(false)
  const isTranscribing = ref(false)
  const isSupported = ref(
    typeof navigator !== 'undefined'
    && !!navigator.mediaDevices?.getUserMedia
    && typeof AudioContext !== 'undefined',
  )
  const transcript = ref('')
  const error = ref('')

  let stream: MediaStream | null = null
  let audioContext: AudioContext | null = null
  let source: MediaStreamAudioSourceNode | null = null
  let processor: ScriptProcessorNode | null = null
  let silentGain: GainNode | null = null
  let chunks: Float32Array[] = []
  let sampleRate = 44100
  let stopRequested = false
  let options: SpeechRecognitionStartOptions = {}

  async function start(startOptions: SpeechRecognitionStartOptions = {}): Promise<void> {
    if (!isSupported.value || isStarting.value || isRecording.value || isTranscribing.value) return
    isStarting.value = true
    stopRequested = false
    options = startOptions
    error.value = ''
    transcript.value = ''
    chunks = []

    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
      audioContext = new AudioContext()
      await audioContext.resume()
      sampleRate = audioContext.sampleRate
      source = audioContext.createMediaStreamSource(stream)
      processor = audioContext.createScriptProcessor(4096, 1, 1)
      silentGain = audioContext.createGain()
      silentGain.gain.value = 0
      processor.onaudioprocess = (event) => {
        if (!isRecording.value) return
        chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)))
      }
      source.connect(processor)
      processor.connect(silentGain)
      silentGain.connect(audioContext.destination)
      if (stopRequested) {
        cleanup()
        return
      }
      isRecording.value = true
    } catch (err) {
      const message = err instanceof Error ? err.message : 'microphone-error'
      error.value = message
      cleanup()
      options.onError?.(message)
    } finally {
      isStarting.value = false
    }
  }

  async function stop(): Promise<void> {
    if (isStarting.value) {
      stopRequested = true
      return
    }
    if (!isRecording.value) return
    isRecording.value = false
    const audioChunks = chunks
    cleanup()
    if (!audioChunks.length) return

    isTranscribing.value = true
    try {
      const merged = mergeChunks(audioChunks)
      const wav = encodeWav(merged, sampleRate, 16000)
      if (import.meta.env.DEV) {
        console.debug('[AgentHub ASR] captured audio', {
          inputSampleRate: sampleRate,
          inputSamples: merged.length,
          durationMs: Math.round((merged.length / sampleRate) * 1000),
          wavBytes: wav.size,
        })
      }
      const result = await transcribeAudio(wav)
      transcript.value = result.text.trim()
      options.onEnd?.(transcript.value)
    } catch (err) {
      const message = err instanceof Error ? err.message : '语音转写失败'
      error.value = message
      options.onError?.(message)
    } finally {
      isTranscribing.value = false
      options = {}
      chunks = []
    }
  }

  function clearTranscript(): void {
    transcript.value = ''
    error.value = ''
  }

  function cleanup(): void {
    processor && (processor.onaudioprocess = null)
    processor?.disconnect()
    silentGain?.disconnect()
    source?.disconnect()
    processor = null
    silentGain = null
    source = null
    stream?.getTracks().forEach(track => track.stop())
    stream = null
    void audioContext?.close()
    audioContext = null
  }

  onUnmounted(() => {
    cleanup()
  })

  return {
    isStarting,
    isRecording,
    isTranscribing,
    isListening: isRecording,
    isSupported,
    transcript,
    error,
    start,
    stop,
    clearTranscript,
  }
}

function mergeChunks(chunks: Float32Array[]): Float32Array {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0)
  const merged = new Float32Array(length)
  let offset = 0
  for (const chunk of chunks) {
    merged.set(chunk, offset)
    offset += chunk.length
  }
  return merged
}

function downsample(input: Float32Array, inputRate: number, outputRate: number): Float32Array {
  if (inputRate === outputRate) return input
  const ratio = inputRate / outputRate
  const outputLength = Math.round(input.length / ratio)
  const output = new Float32Array(outputLength)
  for (let i = 0; i < outputLength; i++) {
    const start = Math.floor(i * ratio)
    const end = Math.min(Math.floor((i + 1) * ratio), input.length)
    let sum = 0
    for (let j = start; j < end; j++) sum += input[j]
    output[i] = sum / Math.max(1, end - start)
  }
  return output
}

function encodeWav(samples: Float32Array, inputRate: number, outputRate: number): Blob {
  const pcm = downsample(samples, inputRate, outputRate)
  const buffer = new ArrayBuffer(44 + pcm.length * 2)
  const view = new DataView(buffer)
  writeString(view, 0, 'RIFF')
  view.setUint32(4, 36 + pcm.length * 2, true)
  writeString(view, 8, 'WAVE')
  writeString(view, 12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, outputRate, true)
  view.setUint32(28, outputRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(view, 36, 'data')
  view.setUint32(40, pcm.length * 2, true)

  let offset = 44
  for (const sample of pcm) {
    const clamped = Math.max(-1, Math.min(1, sample))
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true)
    offset += 2
  }
  return new Blob([buffer], { type: 'audio/wav' })
}

function writeString(view: DataView, offset: number, value: string): void {
  for (let i = 0; i < value.length; i++) {
    view.setUint8(offset + i, value.charCodeAt(i))
  }
}
