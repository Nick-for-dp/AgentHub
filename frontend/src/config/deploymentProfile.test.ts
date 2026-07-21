import { describe, expect, it } from 'vitest'

import {
  getDefaultHomePath,
  getDeploymentPresentation,
  resolveDeploymentProfile,
} from './deploymentProfile'
import { createAppRoutes } from '../router/routes'

describe('deployment profile', () => {
  it('defaults unknown configuration to external', () => {
    expect(resolveDeploymentProfile(undefined)).toBe('external')
    expect(resolveDeploymentProfile('unexpected')).toBe('external')
    expect(resolveDeploymentProfile(' INTERNAL ')).toBe('internal')
  })

  it('does not register the internal workbench route for external builds', () => {
    const routes = createAppRoutes('external')
    expect(routes.some((route) => route.path === '/internal')).toBe(false)
    expect(JSON.stringify(routes)).not.toContain('risk-assistant')
    expect(JSON.stringify(routes)).not.toContain('RiskAssistantPage')
    expect(getDefaultHomePath(false, 'external')).toBe('/chat')
    expect(getDeploymentPresentation('external')).toEqual({
      productName: 'AgentHub 营销智能体',
      subtitle: '产品咨询与营销问答服务',
      environmentLabel: '外部服务',
      defaultHomePath: '/chat',
    })
  })

  it('registers a login-protected workbench only for internal builds', () => {
    const route = createAppRoutes('internal').find((item) => item.path === '/internal')
    expect(route?.meta?.requiresAuth).toBe(true)
    expect(route?.children?.some((item) => item.path === 'contract-review')).toBe(true)
    expect(route?.children?.some((item) => item.path === 'risk-assistant')).toBe(true)
    const detail = route?.children?.find((item) => item.path === 'risk-assistant/tasks/:taskId')
    expect(detail?.props).toBe(true)
    expect(getDefaultHomePath(false, 'internal')).toBe('/internal/contract-review')
    expect(getDefaultHomePath(true, 'internal')).toBe('/admin/agents')
    expect(getDeploymentPresentation('internal')).toEqual({
      productName: 'AgentHub 内部智能体',
      subtitle: '合同审查与风控工作台',
      environmentLabel: '内部试用',
      defaultHomePath: '/internal/contract-review',
    })
  })
})
