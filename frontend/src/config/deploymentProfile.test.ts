import { describe, expect, it } from 'vitest'

import { getDefaultHomePath, resolveDeploymentProfile } from './deploymentProfile'
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
    expect(getDefaultHomePath(false, 'external')).toBe('/chat')
  })

  it('registers a login-protected workbench only for internal builds', () => {
    const route = createAppRoutes('internal').find((item) => item.path === '/internal')
    expect(route?.meta?.requiresAuth).toBe(true)
    expect(route?.children?.some((item) => item.path === 'contract-review')).toBe(true)
    expect(getDefaultHomePath(false, 'internal')).toBe('/internal/contract-review')
    expect(getDefaultHomePath(true, 'internal')).toBe('/admin/agents')
  })
})
