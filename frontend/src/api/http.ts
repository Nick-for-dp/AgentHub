import axios from 'axios'

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 30000,
  withCredentials: true,
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
