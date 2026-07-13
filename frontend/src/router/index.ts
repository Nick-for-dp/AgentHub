import { createRouter, createWebHistory } from 'vue-router'

import { createAppRoutes } from './routes'

export { createAppRoutes } from './routes'

const router = createRouter({
  history: createWebHistory(),
  routes: createAppRoutes(),
})

// 路由守卫：需要登录的页面未认证时跳转登录页
router.beforeEach(async (to, _from, next) => {
  let auth: ReturnType<typeof import('../stores/auth')['useAuthStore']> | null = null
  const getAuthStore = async () => {
    if (!auth) {
      const { useAuthStore } = await import('../stores/auth')
      auth = useAuthStore()
    }
    return auth
  }

  if (to.meta.requiresAuth) {
    // 动态导入避免循环依赖
    const auth = await getAuthStore()
    if (!auth.isLoggedIn) {
      // 尝试从 HttpOnly Cookie 恢复会话
      const restored = await auth.restoreSession()
      if (!restored) {
        next('/login')
        return
      }
    } else if (!auth.currentUser || auth.isAccessExpiringSoon) {
      // 刷新页面后 Pinia 内存态会丢失；session 临近过期时也提前刷新。
      try {
        const restored = await auth.restoreSession()
        if (!restored) {
          next('/login')
          return
        }
      } catch {
        auth.clearSession()
        next('/login')
        return
      }
    }
  }
  // 已登录用户访问 /login 时重定向到自己的默认首页
  if (to.path === '/login') {
    const auth = await getAuthStore()
    if (auth.isLoggedIn || await auth.restoreSession()) {
      next(auth.defaultHomePath)
      return
    }
  }
  next()
})

export default router
