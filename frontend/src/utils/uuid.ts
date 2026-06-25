/**
 * 生成 UUID v4，兼容非安全上下文（HTTP / 非 localhost）。
 *
 * 浏览器只在以下两种"安全上下文"暴露 crypto.randomUUID()：
 *   - HTTPS 站点
 *   - localhost 站点
 *
 * AgentHub MVP 阶段走纯 HTTP 内网部署（http://10.128.140.208/），
 * crypto.randomUUID 在该环境下为 undefined，调用会抛 TypeError，
 * 整个发送链路被打断。
 *
 * 优先使用浏览器原生（HTTPS 上线后自动启用），不可用时回退到
 * crypto.getRandomValues + 手写 v4 规范（HTTP 下仍可用，
 * getRandomValues 不受安全上下文限制）。最差情况降级到 Math.random
 * 兜底，仅用于纯展示，不参与安全关键路径。
 */
export function randomUUID(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID()
  }
  if (typeof crypto !== 'undefined' && typeof crypto.getRandomValues === 'function') {
    const bytes = new Uint8Array(16)
    crypto.getRandomValues(bytes)
    // RFC 4122 v4 标识位
    bytes[6] = (bytes[6] & 0x0f) | 0x40
    bytes[8] = (bytes[8] & 0x3f) | 0x80
    const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('')
    return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20, 32)}`
  }
  // 极端兜底：Math.random 非密码学强度，仅用于业务非关键 id
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0
    const v = c === 'x' ? r : (r & 0x3) | 0x8
    return v.toString(16)
  })
}
