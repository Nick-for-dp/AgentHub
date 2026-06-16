import axios from 'axios'
import { isEmbedSessionActive } from '../utils/embedAuth'

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
})

http.interceptors.request.use((config) => {
  if (isEmbedSessionActive()) {
    config.headers['X-AgentHub-Embed'] = 'true'
  }
  return config
})

// 401 响应拦截：通知页面逻辑清理内存登录态并跳转。
http.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      window.dispatchEvent(new CustomEvent('agenthub:unauthorized'))
    }
    return Promise.reject(error)
  },
)
