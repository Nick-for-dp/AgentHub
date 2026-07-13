export type DeploymentProfile = 'external' | 'internal'

const DEFAULT_DEPLOYMENT_PROFILE: DeploymentProfile = 'external'

export function resolveDeploymentProfile(
  rawProfile: string | undefined = import.meta.env.VITE_DEPLOYMENT_PROFILE,
): DeploymentProfile {
  return rawProfile?.trim().toLowerCase() === 'internal'
    ? 'internal'
    : DEFAULT_DEPLOYMENT_PROFILE
}

export const deploymentProfile = resolveDeploymentProfile()
export const isInternalProfile = deploymentProfile === 'internal'

export function getDefaultHomePath(isAdmin: boolean, profile = deploymentProfile): string {
  if (isAdmin) return '/admin/agents'
  return profile === 'internal' ? '/internal/contract-review' : '/chat'
}
