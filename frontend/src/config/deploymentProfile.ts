export type DeploymentProfile = 'external' | 'internal'

export interface DeploymentPresentation {
  productName: string
  subtitle: string
  environmentLabel: string
  defaultHomePath: string
}

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

const EXTERNAL_PRESENTATION: DeploymentPresentation = {
  productName: 'AgentHub 营销智能体',
  subtitle: '产品咨询与营销问答服务',
  environmentLabel: '外部服务',
  defaultHomePath: '/chat',
}

const INTERNAL_PRESENTATION: DeploymentPresentation | null = __INTERNAL_BUILD__
  ? {
    productName: 'AgentHub 内部智能体',
    subtitle: '合同审查与风控工作台',
    environmentLabel: '内部试用',
    defaultHomePath: '/internal/contract-review',
    }
  : null

export function getDeploymentPresentation(
  profile: DeploymentProfile = deploymentProfile,
): DeploymentPresentation {
  if (__INTERNAL_BUILD__ && profile === 'internal' && INTERNAL_PRESENTATION) {
    return INTERNAL_PRESENTATION
  }
  return EXTERNAL_PRESENTATION
}

export const deploymentPresentation = getDeploymentPresentation()

export function getDefaultHomePath(isAdmin: boolean, profile = deploymentProfile): string {
  if (isAdmin) return '/admin/agents'
  return getDeploymentPresentation(profile).defaultHomePath
}
