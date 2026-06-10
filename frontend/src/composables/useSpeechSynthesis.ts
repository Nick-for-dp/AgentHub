/** Compatibility wrapper for the cloud TTS implementation. */

import { useCloudSpeechSynthesis } from './useCloudSpeechSynthesis'

export function useSpeechSynthesis() {
  return useCloudSpeechSynthesis()
}

