import type { RouteRecordRaw } from 'vue-router'

import { deploymentProfile, type DeploymentProfile } from '../config/deploymentProfile'

export function createAppRoutes(profile: DeploymentProfile = deploymentProfile): RouteRecordRaw[] {
  const routes: RouteRecordRaw[] = [
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

  if (__INTERNAL_BUILD__ && profile === 'internal') {
    const internalChildren: RouteRecordRaw[] = [
      {
        path: '',
        redirect: '/internal/contract-review',
      },
      {
        path: 'contract-review',
        component: () => import('../pages/internal/ContractReviewPage.vue'),
      },
      {
        path: 'risk-assistant',
        component: () => import('../pages/internal/RiskAssistantPage.vue'),
      },
      {
        path: 'risk-assistant/tasks/:taskId',
        component: () => import('../pages/internal/RiskAssistantPage.vue'),
        props: true,
      },
    ]
    routes.push({
      path: '/internal',
      component: () => import('../layouts/InternalLayout.vue'),
      meta: { requiresAuth: true },
      children: internalChildren,
    })
  }

  return routes
}
