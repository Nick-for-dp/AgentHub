let embedAccessToken = ''

export function setEmbedAccessToken(token: string): void {
  embedAccessToken = token
}

export function getEmbedAccessToken(): string {
  return embedAccessToken
}

export function clearEmbedAccessToken(): void {
  embedAccessToken = ''
}

export function getJwtExpiresAt(token: string): number {
  try {
    const [, payload] = token.split('.')
    if (!payload) return 0
    const normalized = payload.replace(/-/g, '+').replace(/_/g, '/')
    const padded = normalized.padEnd(Math.ceil(normalized.length / 4) * 4, '=')
    const claims = JSON.parse(atob(padded)) as { exp?: number }
    return claims.exp ? claims.exp * 1000 : 0
  } catch {
    return 0
  }
}
