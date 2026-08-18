import type { RouteRecordRaw } from 'vue-router'

export function createAppRoutes(): RouteRecordRaw[] {
  return [
    {
      path: '/',
      redirect: '/login',
    },
    {
      path: '/login',
      component: () => import('../pages/auth/LoginPage.vue'),
    },
    {
      path: '/chat',
      component: () => import('../pages/chat/ChatPage.vue'),
      meta: { requiresAuth: true },
    },
    {
      path: '/embed/chat',
      component: () => import('../pages/chat/ChatPage.vue'),
      meta: { embed: true },
    },
    {
      path: '/admin',
      component: () => import('../layouts/AdminLayout.vue'),
      meta: { requiresAuth: true },
      children: [
        {
          path: '',
          redirect: '/admin/agents',
        },
        {
          path: 'agents',
          component: () => import('../pages/admin/AgentsPage.vue'),
        },
        {
          path: 'knowledge-bases',
          component: () => import('../pages/admin/KnowledgeBasesPage.vue'),
        },
        {
          path: 'api-keys',
          component: () => import('../pages/admin/ApiKeysPage.vue'),
        },
        {
          path: 'invocation-records',
          component: () => import('../pages/admin/InvocationRecordsPage.vue'),
        },
        {
          path: 'leads',
          component: () => import('../pages/admin/LeadsPage.vue'),
        },
        {
          path: 'analytics',
          component: () => import('../pages/admin/AnalyticsPage.vue'),
        },
      ],
    },
  ]
}
