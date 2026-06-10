/** Compatibility wrapper for the cloud ASR implementation. */

import { ref } from 'vue'
import { useCloudSpeechRecognition } from './useCloudSpeechRecognition'

export function useSpeechRecognition() {
  return {
    ...useCloudSpeechRecognition(),
    isServiceUnavailable: ref(false),
  }
}

