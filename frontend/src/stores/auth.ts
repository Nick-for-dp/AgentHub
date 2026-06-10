import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import {
  getSessionStatus,
  login as apiLogin,
  logout as apiLogout,
  refreshSession as apiRefreshSession,
} from '../api/auth'
import type { SessionResponse, SessionStatusResponse, UserSummary } from '../api/auth'

const DEFAULT_REFRESH_SKEW_MS = 5 * 60 * 1000
const CHAT_STREAM_MIN_TTL_MS = 10 * 60 * 1000
const IDLE_LOGOUT_CHECK_MS = 30 * 1000
const ACTIVITY_EVENTS = ['click', 'keydown', 'pointerdown', 'mousemove', 'scroll'] as const
const LEGACY_TOKEN_KEYS = [
  'agenthub_access_token',
  'agenthub_token_expires_at',
  'agenthub_admin_key',
  'agenthub_api_key',
] as const

export const useAuthStore = defineStore('auth', () => {
  clearLegacyTokenStorage()

  const currentUser = ref<UserSummary | null>(null)
  const accessExpiresAt = ref(0)
  const idleExpiresAt = ref(0)
  let refreshPromise: Promise<void> | null = null
  let idleTimer: ReturnType<typeof setInterval> | null = null
  let unauthorizedListenerInstalled = false

  const isLoggedIn = computed(() => !!currentUser.value)
  const isAccessExpired = computed(() => accessExpiresAt.value > 0 && Date.now() >= accessExpiresAt.value)
  const isAccessExpiringSoon = computed(() => shouldRefreshSession(DEFAULT_REFRESH_SKEW_MS))
  const isIdleExpired = computed(() => idleExpiresAt.value > 0 && Date.now() >= idleExpiresAt.value)
  const defaultHomePath = computed(() => currentUser.value?.is_admin ? '/admin/agents' : '/chat')

  async function login(phone: string, password: string): Promise<void> {
    const resp = await apiLogin({ phone, password })
    saveSessionResponse(resp)
    startIdleLogoutWatcher()
  }

  function saveSessionResponse(resp: SessionResponse): void {
    currentUser.value = resp.user
    accessExpiresAt.value = Date.parse(resp.access_expires_at)
    idleExpiresAt.value = Date.parse(resp.idle_expires_at)
  }

  function saveSessionStatus(resp: SessionStatusResponse): boolean {
    if (!resp.authenticated || !resp.user || !resp.access_expires_at || !resp.idle_expires_at) {
      clearSession()
      return false
    }
    currentUser.value = resp.user
    accessExpiresAt.value = Date.parse(resp.access_expires_at)
    idleExpiresAt.value = Date.parse(resp.idle_expires_at)
    return true
  }

  function shouldRefreshSession(requiredTtlMs = DEFAULT_REFRESH_SKEW_MS): boolean {
    if (!currentUser.value || accessExpiresAt.value <= 0) return false
    return Date.now() >= accessExpiresAt.value - requiredTtlMs
  }

  async function restoreSession(): Promise<boolean> {
    try {
      const resp = await getSessionStatus()
      if (!saveSessionStatus(resp)) return false
      startIdleLogoutWatcher()
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function doRefreshSession(): Promise<void> {
    if (refreshPromise) return refreshPromise
    refreshPromise = apiRefreshSession().then((resp) => {
      saveSessionResponse(resp)
    }).finally(() => {
      refreshPromise = null
    })
    return refreshPromise
  }

  async function ensureFreshSession(requiredTtlMs = DEFAULT_REFRESH_SKEW_MS): Promise<boolean> {
    if (!currentUser.value) {
      return restoreSession()
    }
    if (isIdleExpired.value) {
      await doLogout()
      return false
    }
    if (!isAccessExpired.value && !shouldRefreshSession(requiredTtlMs)) {
      return true
    }
    try {
      await doRefreshSession()
      return true
    } catch {
      clearSession()
      return false
    }
  }

  async function ensureFreshSessionForChat(): Promise<boolean> {
    return ensureFreshSession(CHAT_STREAM_MIN_TTL_MS)
  }

  async function doLogout(): Promise<void> {
    try {
      await apiLogout()
    } catch {
      // 登出接口失败不影响前端状态收敛。
    }
    clearSession()
  }

  function clearSession(): void {
    currentUser.value = null
    accessExpiresAt.value = 0
    idleExpiresAt.value = 0
    stopIdleLogoutWatcher()
  }

  function installUnauthorizedListener(): void {
    if (unauthorizedListenerInstalled || typeof window === 'undefined') return
    window.addEventListener('agenthub:unauthorized', () => {
      clearSession()
    })
    unauthorizedListenerInstalled = true
  }

  function startIdleLogoutWatcher(): void {
    if (typeof window === 'undefined' || idleTimer) return
    installUnauthorizedListener()
    for (const eventName of ACTIVITY_EVENTS) {
      window.addEventListener(eventName, handleUserActivity, { passive: true })
    }
    document.addEventListener('visibilitychange', handleVisibilityChange)
    idleTimer = setInterval(checkIdleExpiry, IDLE_LOGOUT_CHECK_MS)
  }

  function stopIdleLogoutWatcher(): void {
    if (typeof window === 'undefined') return
    if (idleTimer) {
      clearInterval(idleTimer)
      idleTimer = null
    }
    for (const eventName of ACTIVITY_EVENTS) {
      window.removeEventListener(eventName, handleUserActivity)
    }
    document.removeEventListener('visibilitychange', handleVisibilityChange)
  }

  function handleVisibilityChange(): void {
    if (document.visibilityState === 'visible') {
      void checkIdleExpiry()
    }
  }

  function handleUserActivity(): void {
    if (!currentUser.value || isIdleExpired.value) return
    if (shouldRefreshSession(DEFAULT_REFRESH_SKEW_MS)) {
      void doRefreshSession().catch(() => clearSession())
    }
  }

  async function checkIdleExpiry(): Promise<void> {
    if (currentUser.value && isIdleExpired.value) {
      await doLogout()
      window.location.assign('/login')
    }
  }

  function clearLegacyTokenStorage(): void {
    for (const key of LEGACY_TOKEN_KEYS) {
      localStorage.removeItem(key)
    }
  }

  return {
    currentUser,
    accessExpiresAt,
    idleExpiresAt,
    isLoggedIn,
    isAccessExpired,
    isAccessExpiringSoon,
    isIdleExpired,
    defaultHomePath,
    login,
    restoreSession,
    doRefreshSession,
    ensureFreshSession,
    ensureFreshSessionForChat,
    doLogout,
    clearSession,
    installUnauthorizedListener,
    startIdleLogoutWatcher,
  }
})
