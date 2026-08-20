export const ROLES = {
  ADMIN: 'admin',
  OHS_MANAGER: 'ohs_manager',
  SAFETY_OFFICER: 'safety_officer',
  SUPERVISOR: 'supervisor',
  EMPLOYEE: 'employee',
}

const LEGACY_ROLE_MAP = {
  safety_manager: ROLES.OHS_MANAGER,
  worker: ROLES.EMPLOYEE,
  auditor: ROLES.SAFETY_OFFICER,
}

const ROLE_PRIORITY = [
  ROLES.ADMIN,
  ROLES.OHS_MANAGER,
  ROLES.SAFETY_OFFICER,
  ROLES.SUPERVISOR,
  ROLES.EMPLOYEE,
]

const RESOURCE_RULES = {
  sites: { view: ROLE_PRIORITY, nav: [ROLES.ADMIN, ROLES.OHS_MANAGER], create: [ROLES.ADMIN, ROLES.OHS_MANAGER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER] },
  departments: { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER], create: [ROLES.ADMIN, ROLES.OHS_MANAGER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER] },
  users: { view: [ROLES.ADMIN], nav: [ROLES.ADMIN], create: [ROLES.ADMIN], edit: [ROLES.ADMIN] },
  roles: { view: [ROLES.ADMIN], nav: [ROLES.ADMIN], create: [ROLES.ADMIN], edit: [ROLES.ADMIN] },
  'audit-logs': { view: [ROLES.ADMIN], nav: [ROLES.ADMIN], create: [], edit: [] },
  'data-imports': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER], create: [ROLES.ADMIN, ROLES.OHS_MANAGER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER] },
  sios: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: ROLE_PRIORITY, edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  incidents: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: ROLE_PRIORITY, edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  hazards: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: ROLE_PRIORITY, edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  inspections: { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'corrective-actions': { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  notifications: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER], edit: ROLE_PRIORITY },
  approvals: { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [], edit: [] },
  training: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR, ROLES.EMPLOYEE], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR, ROLES.EMPLOYEE] },
  'compliance-acknowledgements': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.EMPLOYEE], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.EMPLOYEE], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.EMPLOYEE] },
  permits: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: ROLE_PRIORITY, edit: ROLE_PRIORITY },
  'incident-investigations': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'legal-compliance': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  jsas: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  contractors: { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'asset-register': { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  'medical-surveillance': { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'emergency-drills': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  documents: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  audits: { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'notification-deliveries': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], create: [], edit: [] },
  'job-runs': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], create: [], edit: [] },
  'safety-kpis': { view: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], nav: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER] },
  'safety-communications': { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  'behaviour-observations': { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: ROLE_PRIORITY, edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
  ppe: { view: ROLE_PRIORITY, nav: ROLE_PRIORITY, create: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR, ROLES.EMPLOYEE], edit: [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR] },
}

const RESOURCE_MODULES = {
  'data-imports': 'data_imports', incidents: 'incidents', sios: 'sios', hazards: 'hazards',
  inspections: 'inspections', 'corrective-actions': 'corrective_actions', training: 'training',
  'compliance-acknowledgements': 'compliance', permits: 'permits',
  'incident-investigations': 'incident_investigations', 'legal-compliance': 'compliance',
  jsas: 'jsas', contractors: 'contractors', 'asset-register': 'assets',
  'medical-surveillance': 'medical_surveillance', 'emergency-drills': 'emergency_drills',
  documents: 'document_control', audits: 'audits', 'safety-kpis': 'safety_kpis',
  'safety-communications': 'safety_communications',
  'behaviour-observations': 'behaviour_observations',
  ppe: 'ppe',
}

const DASHBOARD_VIEW_ROLES = [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR]
const REPORTING_VIEW_ROLES = [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR]

const DEFAULT_ROUTE_ORDER = [
  '/dashboard',
  '/ppe',
  '/sios',
  '/incidents',
  '/hazards',
  '/corrective-actions',
  '/permits',
  '/incident-investigations',
  '/legal-compliance',
  '/jsas',
  '/contractors',
  '/asset-register',
  '/medical-surveillance',
  '/emergency-drills',
  '/documents',
  '/audits',
  '/notification-deliveries',
  '/job-runs',
  '/behaviour-observations',
  '/safety-communications',
  '/safety-kpis',
  '/approvals',
  '/training',
  '/compliance-acknowledgements',
  '/notifications',
]

function normalizeRoleName(roleName) {
  return LEGACY_ROLE_MAP[roleName] ?? roleName
}

export function getRoleNames(user) {
  if (!user) {
    return []
  }

  const fromRoleNames = Array.isArray(user.role_names) ? user.role_names : []
  const fromRoles = Array.isArray(user.roles) ? user.roles.map((role) => role.name) : []

  return [...new Set([...fromRoleNames, ...fromRoles].filter(Boolean).map(normalizeRoleName))]
}

export function getPrimaryRole(user) {
  if (!user) {
    return null
  }

  if (user.primary_role) {
    return normalizeRoleName(user.primary_role)
  }

  const roleNames = getRoleNames(user)
  return ROLE_PRIORITY.find((roleName) => roleNames.includes(roleName)) ?? null
}

export function hasRole(user, allowedRoles = []) {
  const roleNames = getRoleNames(user)
  return allowedRoles.some((roleName) => roleNames.includes(roleName))
}

export function hasPermission(user, permission) {
  const permissions = Array.isArray(user?.effective_permissions) ? user.effective_permissions : []
  return permissions.includes('*') || permissions.includes(permission)
}

export function formatRoleLabel(roleName) {
  return roleName ? roleName.replaceAll('_', ' ') : 'User'
}

export function canViewDashboard(user) {
  return hasModule(user, 'dashboard') && hasRole(user, DASHBOARD_VIEW_ROLES)
}

export function canViewReporting(user) {
  return hasModule(user, 'reporting') && hasRole(user, REPORTING_VIEW_ROLES)
}

export function hasModule(user, moduleKey) {
  return !moduleKey || (
    Array.isArray(user?.enabled_modules) && user.enabled_modules.includes(moduleKey)
  )
}

function resourceModuleEnabled(resourceKey, user) {
  return hasModule(user, RESOURCE_MODULES[resourceKey])
}

export function canViewResource(resourceKey, user) {
  return resourceModuleEnabled(resourceKey, user) && hasRole(user, RESOURCE_RULES[resourceKey]?.view ?? [])
}

export function canShowResourceInNav(resourceKey, user) {
  return resourceModuleEnabled(resourceKey, user) && hasRole(user, RESOURCE_RULES[resourceKey]?.nav ?? [])
}

export function canCreateResource(resourceKey, user) {
  return resourceModuleEnabled(resourceKey, user) && hasRole(user, RESOURCE_RULES[resourceKey]?.create ?? [])
}

export function canEditRecord(resourceKey, user, item) {
  if (!resourceModuleEnabled(resourceKey, user) || !hasRole(user, RESOURCE_RULES[resourceKey]?.edit ?? [])) {
    return false
  }

  const primaryRole = getPrimaryRole(user)
  if (resourceKey === 'corrective-actions' && primaryRole === ROLES.SUPERVISOR) {
    return item?.owner_user_id === user?.id || item?.assigned_to_user_id === user?.id
  }

  if (resourceKey === 'training' && primaryRole === ROLES.EMPLOYEE) {
    return item?.assigned_to_user_id === user?.id
  }

  if (resourceKey === 'compliance-acknowledgements' && primaryRole === ROLES.EMPLOYEE) {
    return item?.assigned_to_user_id === user?.id
  }

  if (resourceKey === 'permits' && [ROLES.SUPERVISOR, ROLES.EMPLOYEE].includes(primaryRole)) {
    return item?.requested_by_user_id === user?.id
  }

  return true
}

export function canDeleteAttachment(user, attachment) {
  return (
    attachment?.uploaded_by_user_id === user?.id ||
    hasRole(user, [ROLES.ADMIN, ROLES.OHS_MANAGER])
  )
}

export function canDecideApproval(user) {
  return hasRole(user, [ROLES.ADMIN, ROLES.OHS_MANAGER])
}

export function canRequestApproval(resourceKey, user, item) {
  if (!hasRole(user, [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER, ROLES.SUPERVISOR])) {
    return false
  }

  if (!item) {
    return false
  }

  if (resourceKey === 'incidents') {
    return item.status !== 'closed' && !item.closure_requested
  }

  if (resourceKey === 'hazards') {
    return ['high', 'critical'].includes(item.risk_level) && !item.reviewed_at
  }

  if (resourceKey === 'corrective-actions') {
    return !['closed', 'cancelled'].includes(item.status)
  }

  if (resourceKey === 'permits') {
    return !['approved', 'active', 'closed', 'cancelled'].includes(item.status)
  }

  return false
}

export function canUseUserReferences(user) {
  return hasRole(user, [ROLES.ADMIN, ROLES.OHS_MANAGER, ROLES.SAFETY_OFFICER])
}

export function canAccessQuickReport(user) {
  return hasRole(user, ROLE_PRIORITY) && ['incidents', 'hazards', 'sios', 'behaviour_observations'].some(
    (moduleKey) => hasModule(user, moduleKey),
  )
}

export function getDefaultRoute(user) {
  for (const route of DEFAULT_ROUTE_ORDER) {
    if (route === '/dashboard' && canViewDashboard(user)) {
      return route
    }

    const resourceKey = route.slice(1)
    if (resourceKey && canViewResource(resourceKey, user)) {
      return route
    }
  }

  return '/notifications'
}

export function isForbiddenError(error) {
  return error?.status === 403
}
