/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_DEPLOYMENT_PROFILE?: 'external' | 'internal'
  readonly VITE_CONTRACT_REVIEW_EXECUTE_TIMEOUT_MS?: string
  readonly VITE_API_HOST?: string
  readonly VITE_API_PORT?: string
  readonly VITE_API_PROXY_TARGET?: string
  readonly VITE_DEV_HOST?: string
  readonly VITE_DEV_PORT?: string
  readonly VITE_EMBED_ALLOWED_PARENT_ORIGINS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}

declare module '*.vue' {
  import type { DefineComponent } from 'vue'

  const component: DefineComponent<Record<string, unknown>, Record<string, unknown>, unknown>
  export default component
}
