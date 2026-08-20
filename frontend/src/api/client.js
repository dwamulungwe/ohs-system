const API_PREFIX = '/api/v1'
const DEFAULT_API_URL = 'https://ohs-system.onrender.com'

function normalizeApiBaseUrl(value) {
  const apiUrl = (value || DEFAULT_API_URL).replace(/\/+$/, '')
  return apiUrl.endsWith(API_PREFIX) ? apiUrl : `${apiUrl}${API_PREFIX}`
}

const API_BASE_URL = normalizeApiBaseUrl(import.meta.env.VITE_API_URL)

export class ApiError extends Error {
  constructor(message, status, payload) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.payload = payload
  }
}

async function parseResponse(response) {
  const contentType = response.headers.get('content-type') ?? ''

  if (contentType.includes('application/json')) {
    return response.json()
  }

  return response.text()
}

function parseErrorMessage(payload, status) {
  return (
    payload?.detail ??
    payload?.message ??
    `Request failed with status ${status}`
  )
}

function parseFilenameFromDisposition(header) {
  if (!header) {
    return null
  }

  const utfMatch = header.match(/filename\*=UTF-8''([^;]+)/i)
  if (utfMatch?.[1]) {
    return decodeURIComponent(utfMatch[1])
  }

  const basicMatch = header.match(/filename="?([^"]+)"?/i)
  return basicMatch?.[1] ?? null
}

function withQuery(path, params = {}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== '') {
      searchParams.set(key, String(value))
    }
  })
  const queryString = searchParams.toString()
  return queryString ? `${path}?${queryString}` : path
}

function buildHeaders({ token, isForm, headers = {} }) {
  const mergedHeaders = { ...headers }

  if (!isForm && !mergedHeaders['Content-Type']) {
    mergedHeaders['Content-Type'] = 'application/json'
  }

  if (token) {
    mergedHeaders.Authorization = `Bearer ${token}`
  }

  return mergedHeaders
}

async function request(path, options = {}) {
  const { token, body, isForm = false, headers } = options
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const response = await fetch(`${API_BASE_URL}${normalizedPath}`, {
    method: options.method ?? 'GET',
    headers: buildHeaders({ token, isForm, headers }),
    body: body
      ? isForm
        ? body
        : JSON.stringify(body)
      : undefined,
  })

  const payload = await parseResponse(response)

  if (!response.ok) {
    const message = parseErrorMessage(payload, response.status)
    throw new ApiError(message, response.status, payload)
  }

  return payload
}

async function requestResponse(path, options = {}) {
  const { token, body, isForm = false, headers } = options
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  const response = await fetch(`${API_BASE_URL}${normalizedPath}`, {
    method: options.method ?? 'GET',
    headers: buildHeaders({ token, isForm, headers }),
    body: body
      ? isForm
        ? body
        : JSON.stringify(body)
      : undefined,
  })

  if (!response.ok) {
    const payload = await parseResponse(response)
    const message = parseErrorMessage(payload, response.status)
    throw new ApiError(message, response.status, payload)
  }

  return response
}

export function normalizePaginatedResponse(payload, skip = 0, limit = 25) {
  if (Array.isArray(payload)) {
    return {
      items: payload,
      total: skip + payload.length,
      skip,
      limit,
    }
  }

  return {
    items: payload.items ?? [],
    total: payload.total ?? 0,
    skip: payload.skip ?? skip,
    limit: payload.limit ?? limit,
  }
}

export const apiClient = {
  baseUrl: API_BASE_URL,
  buildPath(path, params = {}) {
    return withQuery(path, params)
  },
  login(email, password) {
    const body = new URLSearchParams()
    body.set('username', email)
    body.set('password', password)
    return request('/auth/login', {
      method: 'POST',
      body,
      isForm: true,
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
  },
  getCurrentUser(token) {
    return request('/auth/me', { token })
  },
  getOrganisations(token) {
    return request('/organisations', { token })
  },
  createOrganisation(token, payload) {
    return request('/organisations', { token, method: 'POST', body: payload })
  },
  updateOrganisation(token, organisationId, payload) {
    return request(`/organisations/${organisationId}`, { token, method: 'PATCH', body: payload })
  },
  getOrganisationFeatures(token, organisationId) {
    return request(`/organisations/${organisationId}/features`, { token })
  },
  updateOrganisationFeatures(token, organisationId, features) {
    return request(`/organisations/${organisationId}/features`, {
      token,
      method: 'PATCH',
      body: { features },
    })
  },
  getOrganisationSettings(token, organisationId) {
    return request(`/organisations/${organisationId}/settings`, { token })
  },
  updateOrganisationSettings(token, organisationId, payload) {
    return request(`/organisations/${organisationId}/settings`, {
      token,
      method: 'PATCH',
      body: payload,
    })
  },
  getDashboardOverview(token, params = {}) {
    return request(withQuery('/dashboard/overview', params), { token })
  },
  getDashboardSites(token, params = {}) {
    return request(withQuery('/dashboard/sites', params), { token })
  },
  getDashboardTrends(token, params = {}) {
    return request(withQuery('/dashboard/trends', params), { token })
  },
  getDashboardRisk(token, params = {}) {
    return request(withQuery('/dashboard/risk', params), { token })
  },
  getDashboardActions(token, params = {}) {
    return request(withQuery('/dashboard/actions', params), { token })
  },
  getDashboardCompliance(token, params = {}) {
    return request(withQuery('/dashboard/compliance', params), { token })
  },
  getDashboardPermits(token, params = {}) {
    return request(withQuery('/dashboard/permits', params), { token })
  },
  getDashboardApprovals(token, params = {}) {
    return request(withQuery('/dashboard/approvals', params), { token })
  },
  getDashboardManagementSummary(token, params = {}) {
    return request(withQuery('/dashboard/management-summary', params), { token })
  },
  getDashboardSios(token, params = {}) {
    return request(withQuery('/dashboard/sios', params), { token })
  },
  getPpeDashboard(token, params = {}) {
    return request(withQuery('/ppe/dashboard', params), { token })
  },
  getIncidentDashboard(token, params = {}) {
    return request(withQuery('/incidents/dashboard', params), { token })
  },
  getIncidents(token, params = {}) {
    return request(withQuery('/incidents', params), { token }).then((payload) => normalizePaginatedResponse(payload, params.skip ?? 0, params.limit ?? 25))
  },
  getIncidentWorkspace(token, incidentId) {
    return request(`/incidents/${incidentId}/workspace`, { token })
  },
  getIncidentMedical(token, incidentId) {
    return request(`/incidents/${incidentId}/medical`, { token })
  },
  getOccupationalHealth(token, path = '', params = {}) {
    const suffix = path ? `/${path.replace(/^\/+/, '')}` : ''
    return request(withQuery(`/medical-surveillance${suffix}`, params), { token })
  },
  createOccupationalHealth(token, path, body) {
    const suffix = path ? `/${path.replace(/^\/+/, '')}` : ''
    return request(`/medical-surveillance${suffix}`, { token, method: 'POST', body })
  },
  updateOccupationalHealth(token, path, body) {
    return request(`/medical-surveillance/${path.replace(/^\/+/, '')}`, { token, method: 'PATCH', body })
  },
  incidentCommand(token, incidentId, command, body = {}) {
    return request(`/incidents/${incidentId}/${command}`, { token, method: 'POST', body })
  },
  getPpeCollection(token, path, params = {}) {
    return request(withQuery(`/ppe/${path}`, params), { token })
  },
  ppeCommand(token, path, body = {}) {
    return request(`/ppe/${path}`, { token, method: 'POST', body })
  },
  updatePpeRecord(token, path, body = {}) {
    return request(`/ppe/${path}`, { token, method: 'PATCH', body })
  },
  getReportingPeriods(token, params = {}) {
    return request(withQuery('/reporting/periods', params), { token })
  },
  createReportingPeriod(token, body) {
    return request('/reporting/periods', { token, method: 'POST', body })
  },
  getReportingScorecard(token, periodId, params = {}) {
    return request(withQuery(`/reporting/periods/${periodId}/scorecard`, params), { token })
  },
  getReportingSections(token, periodId) {
    return request(`/reporting/periods/${periodId}/sections`, { token })
  },
  updateReportingSection(token, periodId, sectionKey, content) {
    return request(`/reporting/periods/${periodId}/sections/${sectionKey}`, {
      token,
      method: 'PATCH',
      body: { content },
    })
  },
  runReportingCommand(token, periodId, command, body) {
    return request(`/reporting/periods/${periodId}/${command}`, {
      token,
      method: 'POST',
      body,
    })
  },
  generateReportingSnapshots(token, periodId) {
    return request(`/reporting/periods/${periodId}/snapshots`, { token, method: 'POST' })
  },
  getKpiDefinitions(token, params = {}) {
    return request(withQuery('/reporting/kpi-definitions', params), { token })
  },
  getKpiTargets(token, params = {}) {
    return request(withQuery('/reporting/kpi-targets', params), { token })
  },
  createKpiTarget(token, body) {
    return request('/reporting/kpi-targets', { token, method: 'POST', body })
  },
  getWorkforceExposure(token, params = {}) {
    return request(withQuery('/reporting/workforce-exposure', params), { token })
  },
  createWorkforceExposure(token, body) {
    return request('/reporting/workforce-exposure', { token, method: 'POST', body })
  },
  getReportingForwardView(token, params = {}) {
    return request(withQuery('/reporting/forward-view', params), { token })
  },
  getReportingExceptions(token, params = {}) {
    return request(withQuery('/reporting/exceptions', params), { token })
  },
  getSioComments(token, sioId) {
    return request(`/sios/${sioId}/comments`, { token })
  },
  addSioComment(token, sioId, body) {
    return request(`/sios/${sioId}/comments`, { token, method: 'POST', body: { body } })
  },
  getSioActivity(token, sioId) {
    return request(`/sios/${sioId}/activity`, { token })
  },
  sioAction(token, sioId, action, body = {}) {
    return request(`/sios/${sioId}/${action}`, { token, method: 'POST', body })
  },
  updateSioInvestigation(token, sioId, body) {
    return request(`/sios/${sioId}/investigation`, { token, method: 'PATCH', body })
  },
  bulkUpdateSios(token, body) {
    return request('/sios/bulk', { token, method: 'POST', body })
  },
  getActionDashboard(token, params = {}) {
    return request(withQuery('/corrective-actions/dashboard', params), { token })
  },
  getActionComments(token, actionId) {
    return request(`/corrective-actions/${actionId}/comments`, { token })
  },
  addActionComment(token, actionId, body) {
    return request(`/corrective-actions/${actionId}/comments`, { token, method: 'POST', body: { body } })
  },
  getActionActivity(token, actionId) {
    return request(`/corrective-actions/${actionId}/activity`, { token })
  },
  actionCommand(token, actionId, command, body = {}) {
    return request(`/corrective-actions/${actionId}/${command}`, { token, method: 'POST', body })
  },
  updateActionProgress(token, actionId, body) {
    return request(`/corrective-actions/${actionId}/progress`, { token, method: 'PATCH', body })
  },
  createActionTask(token, actionId, body) {
    return request(`/corrective-actions/${actionId}/tasks`, { token, method: 'POST', body })
  },
  updateActionTask(token, actionId, taskId, body) {
    return request(`/corrective-actions/${actionId}/tasks/${taskId}`, { token, method: 'PATCH', body })
  },
  requestActionExtension(token, actionId, body) {
    return request(`/corrective-actions/${actionId}/extensions`, { token, method: 'POST', body })
  },
  decideActionExtension(token, actionId, extensionId, body) {
    return request(`/corrective-actions/${actionId}/extensions/${extensionId}/decision`, { token, method: 'POST', body })
  },
  bulkUpdateActions(token, body) {
    return request('/corrective-actions/bulk', { token, method: 'POST', body })
  },
  async bulkExportActions(token, actionIds) {
    const response = await requestResponse('/corrective-actions/bulk/export', {
      token,
      method: 'POST',
      body: { action_ids: actionIds },
    })
    return {
      blob: await response.blob(),
      filename: parseFilenameFromDisposition(response.headers.get('content-disposition')) ?? 'actions-selected.csv',
    }
  },
  async bulkExportSios(token, sioIds) {
    const response = await requestResponse('/sios/bulk/export', {
      token,
      method: 'POST',
      body: { sio_ids: sioIds },
    })
    return {
      blob: await response.blob(),
      filename: parseFilenameFromDisposition(response.headers.get('content-disposition')) ?? 'sios-selected.csv',
    }
  },
  previewDataImport(token, file, importerType = 'yalelo_sio') {
    const body = new FormData()
    body.append('file', file)
    body.append('importer_type', importerType)
    return request('/data-imports/preview', {
      method: 'POST',
      token,
      body,
      isForm: true,
    })
  },
  confirmDataImport(token, jobId, body) {
    return request(`/data-imports/${jobId}/confirm`, {
      method: 'POST',
      token,
      body,
    })
  },
  runScheduledJobs(token) {
    return request('/job-runs/run-scheduled', {
      method: 'POST',
      token,
    })
  },
  getUnreadNotificationCount(token) {
    return request('/notifications/unread-count', { token })
  },
  markAllNotificationsAsRead(token) {
    return request('/notifications/mark-all-as-read', {
      method: 'PATCH',
      token,
    })
  },
  markNotificationAsRead(token, notificationId) {
    return request(`/notifications/${notificationId}/read`, {
      method: 'PATCH',
      token,
    })
  },
  getList(token, endpoint, { skip = 0, limit = 25 } = {}) {
    const divider = endpoint.includes('?') ? '&' : '?'
    return request(`${endpoint}${divider}skip=${skip}&limit=${limit}`, { token })
      .then((payload) => normalizePaginatedResponse(payload, skip, limit))
  },
  getCollection(token, endpoint) {
    return request(endpoint, { token }).then((payload) => {
      if (Array.isArray(payload)) {
        return payload
      }

      return payload.items ?? []
    })
  },
  getDetail(token, endpoint) {
    return request(endpoint, { token })
  },
  createRecord(token, endpoint, body) {
    return request(endpoint, {
      method: 'POST',
      token,
      body,
    })
  },
  updateRecord(token, endpoint, body) {
    return request(endpoint, {
      method: 'PATCH',
      token,
      body,
    })
  },
  requestApproval(token, entityType, entityId, body) {
    return request(`/approvals/${entityType}/${entityId}/request`, {
      method: 'POST',
      token,
      body,
    })
  },
  decideApproval(token, approvalId, body) {
    return request(`/approvals/${approvalId}/decision`, {
      method: 'PATCH',
      token,
      body,
    })
  },
  listAttachments(token, entityType, entityId) {
    return request(`/attachments/${entityType}/${entityId}`, { token })
  },
  uploadAttachment(token, entityType, entityId, { file, description, evidenceType }) {
    const body = new FormData()
    body.append('file', file)
    if (description) {
      body.append('description', description)
    }
    if (evidenceType) {
      body.append('evidence_type', evidenceType)
    }

    return request(`/attachments/${entityType}/${entityId}`, {
      method: 'POST',
      token,
      body,
      isForm: true,
    })
  },
  deleteAttachment(token, attachmentId) {
    return request(`/attachments/${attachmentId}`, {
      method: 'DELETE',
      token,
    })
  },
  async downloadAttachment(token, attachmentId) {
    const response = await requestResponse(`/attachments/${attachmentId}/download`, {
      token,
      isForm: true,
    })
    return {
      blob: await response.blob(),
      filename:
        parseFilenameFromDisposition(response.headers.get('content-disposition')) ??
        `attachment-${attachmentId}`,
    }
  },
  async downloadFile(token, path, { params = {}, fallbackFilename = 'export' } = {}) {
    const response = await requestResponse(withQuery(path, params), {
      token,
      isForm: true,
    })
    return {
      blob: await response.blob(),
      filename:
        parseFilenameFromDisposition(response.headers.get('content-disposition')) ??
        fallbackFilename,
    }
  },
  async getHtmlReport(token, path, { params = {} } = {}) {
    const response = await requestResponse(withQuery(path, params), {
      token,
      isForm: true,
      headers: {
        Accept: 'text/html',
      },
    })
    return response.text()
  },
}
