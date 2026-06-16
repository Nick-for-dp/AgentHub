let embedSessionActive = false

export function setEmbedSessionActive(active: boolean): void {
  embedSessionActive = active
}

export function isEmbedSessionActive(): boolean {
  return embedSessionActive
}
