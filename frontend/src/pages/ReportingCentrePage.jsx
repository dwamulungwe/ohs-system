import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, CalendarRange, Download, LockKeyhole, RefreshCw } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { Badge } from '../components/Badge.jsx'
import { EmptyState } from '../components/EmptyState.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, formatNumber, humanize } from '../lib/formatters.js'
import { canViewReporting, hasRole, ROLES } from '../lib/rbac.js'

const topTabs = [
  ['periods', 'Reporting Periods'],
  ['workspace', 'Report Workspace'],
  ['workforce', 'Workforce Exposure'],
  ['targets', 'KPI Targets'],
]

const inputClass = 'mt-1.5 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200'
const primaryButton = 'rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-50'
const secondaryButton = 'rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50'

function Panel({ title, description, children, actions }) {
  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-stone-950">{title}</h2>
          {description ? <p className="mt-1 text-sm leading-6 text-stone-600">{description}</p> : null}
        </div>
        {actions ? <div className="flex flex-wrap gap-2">{actions}</div> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function formatMetric(value, unit) {
  if (value === null || value === undefined) return '--'
  if (unit === 'percent') return `${Number(value).toFixed(1)}%`
  if (unit === 'days') return `${Number(value).toFixed(1)} d`
  return formatNumber(value)
}

function downloadBlob({ blob, filename }) {
  const url = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = filename
  anchor.click()
  URL.revokeObjectURL(url)
}

function ScorecardTable({ rows }) {
  if (!rows?.length) {
    return <EmptyState title="No snapshots yet" message="Generate KPI snapshots for this reporting period to populate the scorecard." />
  }
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
        <thead className="bg-stone-50 text-xs uppercase tracking-[0.07em] text-stone-500">
          <tr>
            {['KPI', 'Target', 'Actual', 'Previous', 'YTD', 'Status'].map((label) => <th key={label} className="px-4 py-3 font-semibold">{label}</th>)}
          </tr>
        </thead>
        <tbody className="divide-y divide-stone-100">
          {rows.map((row) => (
            <tr key={row.kpi_key} className="align-top">
              <td className="px-4 py-3">
                <p className="font-medium text-stone-950">{row.kpi_name}</p>
                {row.denominator !== null && row.denominator !== undefined ? (
                  <p className="mt-1 text-xs text-stone-500">{formatNumber(row.numerator)} / {formatNumber(row.denominator)}</p>
                ) : null}
              </td>
              <td className="px-4 py-3 text-stone-600">{formatMetric(row.target, row.unit)}</td>
              <td className="px-4 py-3 font-semibold text-stone-950">{formatMetric(row.actual, row.unit)}</td>
              <td className="px-4 py-3 text-stone-600">{formatMetric(row.previous_period, row.unit)}</td>
              <td className="px-4 py-3 text-stone-600">{formatMetric(row.ytd, row.unit)}</td>
              <td className="px-4 py-3"><Badge value={row.status} /></td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function ReportingCentrePage() {
  const { token, user } = useAuth()
  const canManage = hasRole(user, [ROLES.ADMIN, ROLES.OHS_MANAGER])
  const [activeTab, setActiveTab] = useState('periods')
  const [workspaceTab, setWorkspaceTab] = useState('kpi_scorecard')
  const [periods, setPeriods] = useState([])
  const [selectedPeriodId, setSelectedPeriodId] = useState('')
  const [scorecard, setScorecard] = useState(null)
  const [sections, setSections] = useState([])
  const [definitions, setDefinitions] = useState([])
  const [targets, setTargets] = useState([])
  const [exposures, setExposures] = useState([])
  const [forwardView, setForwardView] = useState([])
  const [exceptions, setExceptions] = useState([])
  const [sites, setSites] = useState([])
  const [departments, setDepartments] = useState([])
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isBusy, setIsBusy] = useState(false)
  const [notice, setNotice] = useState('')
  const [periodForm, setPeriodForm] = useState({ name: '', period_type: 'monthly', start_date: '', end_date: '' })
  const [exposureForm, setExposureForm] = useState({ site_id: '', period_start: '', period_end: '', employee_headcount: '', contractor_headcount: '', employee_hours_worked: '', contractor_hours_worked: '' })
  const [targetForm, setTargetForm] = useState({ kpi_definition_id: '', site_id: '', department_id: '', target_value: '', warning_threshold: '', critical_threshold: '', effective_from: '' })
  const [summaryDraft, setSummaryDraft] = useState({})

  const selectedPeriod = useMemo(
    () => periods.find((item) => String(item.id) === String(selectedPeriodId)) ?? null,
    [periods, selectedPeriodId],
  )

  const loadBase = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [periodResponse, definitionResponse, targetResponse, exposureResponse, forwardResponse, exceptionResponse, siteResponse, departmentResponse] = await Promise.all([
        apiClient.getReportingPeriods(token, { limit: 250 }),
        apiClient.getKpiDefinitions(token),
        apiClient.getKpiTargets(token),
        apiClient.getWorkforceExposure(token, { limit: 250 }),
        apiClient.getReportingForwardView(token, { window_days: 90 }),
        apiClient.getReportingExceptions(token),
        apiClient.getCollection(token, '/sites'),
        canManage ? apiClient.getCollection(token, '/departments') : Promise.resolve([]),
      ])
      setPeriods(periodResponse.items ?? [])
      setDefinitions(definitionResponse)
      setTargets(targetResponse)
      setExposures(exposureResponse.items ?? [])
      setForwardView(forwardResponse)
      setExceptions(exceptionResponse)
      setSites(siteResponse)
      setDepartments(departmentResponse)
      setSelectedPeriodId((current) => current || String(periodResponse.items?.[0]?.id ?? ''))
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsLoading(false)
    }
  }, [token, canManage])

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      if (canViewReporting(user)) loadBase()
    }, 0)
    return () => window.clearTimeout(timeoutId)
  }, [user, loadBase])

  useEffect(() => {
    if (!selectedPeriodId) {
      return
    }
    let ignore = false
    Promise.all([
      apiClient.getReportingScorecard(token, selectedPeriodId),
      apiClient.getReportingSections(token, selectedPeriodId),
    ]).then(([scorecardResponse, sectionResponse]) => {
      if (ignore) return
      setScorecard(scorecardResponse)
      setSections(sectionResponse)
      const executive = sectionResponse.find((item) => item.section_key === 'executive_summary')
      setSummaryDraft(executive?.content ?? {})
    }).catch((requestError) => {
      if (!ignore) setError(requestError)
    })
    return () => { ignore = true }
  }, [token, selectedPeriodId])

  if (!canViewReporting(user)) {
    return <NotAuthorizedState message="Management reporting is available to authorised supervisors, safety officers, OHS managers, and tenant administrators." />
  }
  if (isLoading) return <LoadingState title="Loading reporting centre" message="Loading periods, immutable KPI snapshots, targets, exposure data, and management exceptions." />
  if (error) return <ErrorState title="Reporting centre unavailable" message={error.message} onRetry={loadBase} />

  async function run(action, successMessage) {
    setIsBusy(true)
    setNotice('')
    try {
      await action()
      setNotice(successMessage)
      await loadBase()
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsBusy(false)
    }
  }

  async function createPeriod(event) {
    event.preventDefault()
    await run(async () => {
      const created = await apiClient.createReportingPeriod(token, periodForm)
      setSelectedPeriodId(String(created.id))
      setPeriodForm({ name: '', period_type: 'monthly', start_date: '', end_date: '' })
    }, 'Reporting period created.')
  }

  async function lifecycle(command) {
    let body
    if (command === 'reopen') {
      const reason = window.prompt('Reason for reopening or restating this report:')
      if (!reason) return
      body = { reason }
    }
    await run(() => apiClient.runReportingCommand(token, selectedPeriodId, command, body), `Report ${command.replace('_', ' ')} completed.`)
  }

  async function exportReport(format) {
    setIsBusy(true)
    try {
      const result = await apiClient.downloadFile(token, `/reporting/periods/${selectedPeriodId}/exports/${format}`, { fallbackFilename: `management-report.${format === 'excel' ? 'xlsx' : 'pdf'}` })
      downloadBlob(result)
      setNotice(`${format === 'excel' ? 'Excel' : 'PDF'} report exported and recorded in the audit trail.`)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsBusy(false)
    }
  }

  async function saveSummary() {
    await run(() => apiClient.updateReportingSection(token, selectedPeriodId, 'executive_summary', summaryDraft), 'Executive summary saved.')
  }

  async function createExposure(event) {
    event.preventDefault()
    const body = Object.fromEntries(Object.entries(exposureForm).map(([key, value]) => {
      if (value === '') return [key, undefined]
      if (['site_id', 'employee_headcount', 'contractor_headcount'].includes(key)) return [key, Number(value)]
      if (['employee_hours_worked', 'contractor_hours_worked'].includes(key)) return [key, Number(value)]
      return [key, value]
    }).filter(([, value]) => value !== undefined))
    await run(() => apiClient.createWorkforceExposure(token, body), 'Workforce exposure saved.')
    setExposureForm({ site_id: '', period_start: '', period_end: '', employee_headcount: '', contractor_headcount: '', employee_hours_worked: '', contractor_hours_worked: '' })
  }

  async function createTarget(event) {
    event.preventDefault()
    const body = {
      kpi_definition_id: Number(targetForm.kpi_definition_id),
      site_id: targetForm.site_id ? Number(targetForm.site_id) : undefined,
      department_id: targetForm.department_id ? Number(targetForm.department_id) : undefined,
      target_value: Number(targetForm.target_value),
      warning_threshold: targetForm.warning_threshold === '' ? undefined : Number(targetForm.warning_threshold),
      critical_threshold: targetForm.critical_threshold === '' ? undefined : Number(targetForm.critical_threshold),
      effective_from: targetForm.effective_from,
    }
    await run(() => apiClient.createKpiTarget(token, body), 'New effective-dated KPI target version created.')
    setTargetForm({ kpi_definition_id: '', site_id: '', department_id: '', target_value: '', warning_threshold: '', critical_threshold: '', effective_from: '' })
  }

  const enabledSections = sections.filter((section) => section.is_enabled)
  const section = sections.find((item) => item.section_key === workspaceTab)

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Executive reporting"
        title="Management Reporting Centre"
        description="Period-locked HSE scorecards, explainable KPI calculations, approvals, restatements, exposure denominators, and management-ready exports."
        actions={selectedPeriod ? <div className="text-right"><p className="text-sm font-semibold text-stone-950">{selectedPeriod.report_reference ?? `Draft V${selectedPeriod.report_version}`}</p><p className="text-xs text-stone-500">{selectedPeriod.name}</p></div> : null}
      />
      {notice ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div> : null}

      <div className="flex gap-2 overflow-x-auto rounded-xl border border-stone-200 bg-white p-2">
        {topTabs.map(([key, label]) => (
          <button key={key} type="button" onClick={() => setActiveTab(key)} className={`shrink-0 rounded-lg px-4 py-2 text-sm font-medium transition ${activeTab === key ? 'bg-emerald-100 text-emerald-900' : 'text-stone-600 hover:bg-stone-50'}`}>{label}</button>
        ))}
      </div>

      {activeTab === 'periods' ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_340px]">
          <Panel title="Reporting periods" description="Approved and locked versions retain their original snapshots and approval history.">
            {periods.length ? (
              <div className="overflow-x-auto">
                <table className="min-w-full divide-y divide-stone-200 text-left text-sm">
                  <thead className="bg-stone-50 text-xs uppercase tracking-[0.07em] text-stone-500"><tr>{['Name', 'Type', 'Dates', 'Status', 'Prepared By', 'Approved By', 'Locked'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead>
                  <tbody className="divide-y divide-stone-100">
                    {periods.map((period) => (
                      <tr key={period.id} onClick={() => { setSelectedPeriodId(String(period.id)); setActiveTab('workspace') }} className="cursor-pointer hover:bg-emerald-50/50">
                        <td className="px-4 py-3"><p className="font-medium text-stone-950">{period.name}</p><p className="text-xs text-stone-500">{period.report_reference ?? `Version ${period.report_version}`}</p></td>
                        <td className="px-4 py-3 text-stone-600">{humanize(period.period_type)}</td>
                        <td className="px-4 py-3 text-stone-600">{formatDate(period.start_date)} – {formatDate(period.end_date)}</td>
                        <td className="px-4 py-3"><Badge value={period.status} /></td>
                        <td className="px-4 py-3 text-stone-600">{period.prepared_by_name ?? '--'}</td>
                        <td className="px-4 py-3 text-stone-600">{period.approved_by_name ?? '--'}</td>
                        <td className="px-4 py-3 text-stone-600">{formatDateTime(period.locked_at)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : <EmptyState title="No reporting periods" message="Create the first monthly, quarterly, annual, or custom management reporting period." />}
          </Panel>
          {canManage ? (
            <Panel title="New reporting period" description="Create a draft period. Snapshots are generated before submission.">
              <form className="space-y-4" onSubmit={createPeriod}>
                <label className="block text-sm font-medium text-stone-700">Name<input required value={periodForm.name} onChange={(event) => setPeriodForm((form) => ({ ...form, name: event.target.value }))} className={inputClass} placeholder="July 2026 Management Report" /></label>
                <label className="block text-sm font-medium text-stone-700">Period type<select value={periodForm.period_type} onChange={(event) => setPeriodForm((form) => ({ ...form, period_type: event.target.value }))} className={inputClass}>{['monthly', 'quarterly', 'annual', 'custom'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></label>
                <div className="grid grid-cols-2 gap-3"><label className="block text-sm font-medium text-stone-700">Start<input required type="date" value={periodForm.start_date} onChange={(event) => setPeriodForm((form) => ({ ...form, start_date: event.target.value }))} className={inputClass} /></label><label className="block text-sm font-medium text-stone-700">End<input required type="date" value={periodForm.end_date} onChange={(event) => setPeriodForm((form) => ({ ...form, end_date: event.target.value }))} className={inputClass} /></label></div>
                <button disabled={isBusy} className={`${primaryButton} w-full`}>Create draft period</button>
              </form>
            </Panel>
          ) : null}
        </div>
      ) : null}

      {activeTab === 'workspace' ? (
        selectedPeriod ? (
          <div className="space-y-5">
            <Panel title={selectedPeriod.name} description={`${formatDate(selectedPeriod.start_date)} – ${formatDate(selectedPeriod.end_date)}`} actions={<><Badge value={selectedPeriod.status} /><select value={selectedPeriodId} onChange={(event) => setSelectedPeriodId(event.target.value)} className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm">{periods.map((period) => <option key={period.id} value={period.id}>{period.name} · V{period.report_version}</option>)}</select></>}>
              <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-lg bg-stone-50 p-4"><p className="text-xs uppercase text-stone-500">Prepared by</p><p className="mt-1 font-medium">{selectedPeriod.prepared_by_name ?? '--'}</p></div><div className="rounded-lg bg-stone-50 p-4"><p className="text-xs uppercase text-stone-500">Approved by</p><p className="mt-1 font-medium">{selectedPeriod.approved_by_name ?? '--'}</p></div><div className="rounded-lg bg-stone-50 p-4"><p className="text-xs uppercase text-stone-500">Reference</p><p className="mt-1 font-medium">{selectedPeriod.report_reference ?? `Pending lock · V${selectedPeriod.report_version}`}</p></div></div>
            </Panel>
            <div className="flex gap-2 overflow-x-auto pb-1">
              {enabledSections.map((item) => <button key={item.section_key} type="button" onClick={() => setWorkspaceTab(item.section_key)} className={`shrink-0 rounded-full px-3 py-2 text-sm font-medium ${workspaceTab === item.section_key ? 'bg-emerald-600 text-white' : 'border border-stone-200 bg-white text-stone-600'}`}>{item.title}</button>)}
            </div>
            {workspaceTab === 'kpi_scorecard' ? <Panel title="Executive HSE scorecard" description="Targets and historical comparisons are copied into the period snapshot."><ScorecardTable rows={scorecard?.rows} /></Panel> : null}
            {workspaceTab === 'executive_summary' ? (
              <Panel title="Executive summary" description="Structured management commentary; no AI-generated narrative is used." actions={canManage && ['draft', 'reopened'].includes(selectedPeriod.status) ? <button onClick={saveSummary} disabled={isBusy} className={primaryButton}>Save commentary</button> : null}>
                <div className="grid gap-4 md:grid-cols-2">{['overall_performance', 'major_events', 'key_improvements', 'critical_concerns', 'management_attention', 'priorities_next_period'].map((field) => <label key={field} className="block text-sm font-medium text-stone-700">{humanize(field)}<textarea rows={4} disabled={!canManage || !['draft', 'reopened'].includes(selectedPeriod.status)} value={summaryDraft[field] ?? ''} onChange={(event) => setSummaryDraft((draft) => ({ ...draft, [field]: event.target.value }))} className={inputClass} /></label>)}</div>
              </Panel>
            ) : null}
            {workspaceTab === 'forward_view' ? <Panel title="90-day forward view" description="Upcoming operational and statutory obligations from enabled modules."><div className="space-y-2">{forwardView.map((item) => <div key={`${item.source_type}-${item.source_id}`} className="flex flex-col gap-2 rounded-lg border border-stone-200 p-3 sm:flex-row sm:items-center sm:justify-between"><div><p className="font-medium text-stone-950">{item.title}</p><p className="text-xs text-stone-500">{humanize(item.source_type)} · due {formatDate(item.obligation_date)}</p></div><Badge value={item.days_until_due <= 7 ? 'critical' : item.days_until_due <= 30 ? 'warning' : 'informational'} /></div>)}</div></Panel> : null}
            {workspaceTab === 'approvals' ? (
              <Panel title="Approval and locking" description="Lifecycle events are retained. Reopening a locked report creates a controlled restatement version." actions={canManage ? <div className="flex flex-wrap gap-2"><button onClick={() => run(() => apiClient.generateReportingSnapshots(token, selectedPeriodId), 'KPI snapshots regenerated.')} disabled={isBusy || selectedPeriod.status === 'locked'} className={secondaryButton}><RefreshCw className="mr-2 inline size-4" />Generate snapshots</button>{['draft', 'reopened'].includes(selectedPeriod.status) ? <button onClick={() => lifecycle('submit')} className={primaryButton}>Submit</button> : null}{selectedPeriod.status === 'under_review' ? <><button onClick={() => lifecycle('review')} className={secondaryButton}>Record review</button><button onClick={() => lifecycle('approve')} className={primaryButton}>Approve</button></> : null}{selectedPeriod.status === 'approved' ? <button onClick={() => lifecycle('lock')} className={primaryButton}><LockKeyhole className="mr-2 inline size-4" />Lock report</button> : null}{['approved', 'locked'].includes(selectedPeriod.status) ? <button onClick={() => lifecycle('reopen')} className={secondaryButton}>Reopen / restate</button> : null}</div> : null}>
                <div className="grid gap-3 sm:grid-cols-3"><div className="rounded-lg bg-stone-50 p-4">Submitted<br /><strong>{formatDateTime(selectedPeriod.submitted_at)}</strong></div><div className="rounded-lg bg-stone-50 p-4">Reviewed<br /><strong>{formatDateTime(selectedPeriod.reviewed_at)}</strong></div><div className="rounded-lg bg-stone-50 p-4">Approved<br /><strong>{formatDateTime(selectedPeriod.approved_at)}</strong></div></div>
              </Panel>
            ) : null}
            {workspaceTab === 'exports' ? <Panel title="Management-ready exports" description="Exports include branding, period identity, scorecard, commentary, management actions, and approval metadata." actions={<><button disabled={isBusy} onClick={() => exportReport('pdf')} className={primaryButton}><Download className="mr-2 inline size-4" />PDF</button><button disabled={isBusy} onClick={() => exportReport('excel')} className={secondaryButton}><Download className="mr-2 inline size-4" />Excel</button></>}><p className="text-sm text-stone-600">Each export is checksummed and written to the tenant audit trail against report version {selectedPeriod.report_version}.</p></Panel> : null}
            {!['kpi_scorecard', 'executive_summary', 'forward_view', 'approvals', 'exports'].includes(workspaceTab) ? <Panel title={section?.title ?? humanize(workspaceTab)} description="This section uses the immutable scorecard metrics and enabled operational module context."><ScorecardTable rows={(scorecard?.rows ?? []).filter((row) => row.kpi_key.startsWith(workspaceTab === 'actions' ? 'action_' : workspaceTab === 'sio' ? 'sio_' : workspaceTab === 'training' ? 'training' : '__none__'))} /></Panel> : null}
          </div>
        ) : <EmptyState title="Select a reporting period" message="Create or select a reporting period to open its report workspace." />
      ) : null}

      {activeTab === 'workforce' ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
          <Panel title="Monthly workforce exposure" description="TRIR and LTIFR remain unavailable unless real employee and contractor hours are recorded.">
            {exposures.length ? <div className="overflow-x-auto"><table className="min-w-full divide-y divide-stone-200 text-sm"><thead className="bg-stone-50 text-left text-xs uppercase text-stone-500"><tr>{['Period', 'Scope', 'Employees', 'Contractors', 'Employee hours', 'Contractor hours', 'Total hours'].map((value) => <th key={value} className="px-4 py-3">{value}</th>)}</tr></thead><tbody className="divide-y divide-stone-100">{exposures.map((item) => <tr key={item.id}><td className="px-4 py-3">{formatDate(item.period_start)} – {formatDate(item.period_end)}</td><td className="px-4 py-3">{item.site_id ? `Site #${item.site_id}` : item.department_id ? `Department #${item.department_id}` : 'Organisation'}</td><td className="px-4 py-3">{formatNumber(item.employee_headcount)}</td><td className="px-4 py-3">{formatNumber(item.contractor_headcount)}</td><td className="px-4 py-3">{formatNumber(item.employee_hours_worked)}</td><td className="px-4 py-3">{formatNumber(item.contractor_hours_worked)}</td><td className="px-4 py-3 font-semibold">{formatNumber(item.total_hours_worked)}</td></tr>)}</tbody></table></div> : <EmptyState title="No exposure data" message="Add actual monthly workforce hours before using rate KPIs." />}
          </Panel>
          {canManage ? <Panel title="Add exposure data" description="Leave scope empty for an organisation aggregate."><form className="space-y-3" onSubmit={createExposure}><label className="block text-sm">Site (optional)<select value={exposureForm.site_id} onChange={(event) => setExposureForm((form) => ({ ...form, site_id: event.target.value }))} className={inputClass}><option value="">Organisation total</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label><div className="grid grid-cols-2 gap-3"><label className="text-sm">Start<input required type="date" value={exposureForm.period_start} onChange={(event) => setExposureForm((form) => ({ ...form, period_start: event.target.value }))} className={inputClass} /></label><label className="text-sm">End<input required type="date" value={exposureForm.period_end} onChange={(event) => setExposureForm((form) => ({ ...form, period_end: event.target.value }))} className={inputClass} /></label></div>{[['employee_headcount', 'Employee headcount'], ['contractor_headcount', 'Contractor headcount'], ['employee_hours_worked', 'Employee hours'], ['contractor_hours_worked', 'Contractor hours']].map(([key, label]) => <label key={key} className="block text-sm">{label}<input type="number" min="0" step={key.includes('hours') ? '0.01' : '1'} value={exposureForm[key]} onChange={(event) => setExposureForm((form) => ({ ...form, [key]: event.target.value }))} className={inputClass} /></label>)}<button disabled={isBusy} className={`${primaryButton} w-full`}>Save exposure</button></form></Panel> : null}
        </div>
      ) : null}

      {activeTab === 'targets' ? (
        <div className="grid gap-6 xl:grid-cols-[1fr_380px]">
          <Panel title="Effective-dated KPI targets" description="Organisation defaults can be overridden by site or department without rewriting historical snapshots.">{targets.length ? <div className="overflow-x-auto"><table className="min-w-full divide-y divide-stone-200 text-sm"><thead className="bg-stone-50 text-left text-xs uppercase text-stone-500"><tr>{['KPI', 'Scope', 'Target', 'Warning', 'Critical', 'Effective', 'Version'].map((value) => <th key={value} className="px-4 py-3">{value}</th>)}</tr></thead><tbody className="divide-y divide-stone-100">{targets.map((item) => <tr key={item.id}><td className="px-4 py-3 font-medium">{humanize(item.kpi_key)}</td><td className="px-4 py-3">{item.site_id ? `Site #${item.site_id}` : item.department_id ? `Department #${item.department_id}` : 'Organisation'}</td><td className="px-4 py-3">{formatNumber(item.target_value)}</td><td className="px-4 py-3">{formatNumber(item.warning_threshold)}</td><td className="px-4 py-3">{formatNumber(item.critical_threshold)}</td><td className="px-4 py-3">{formatDate(item.effective_from)} – {formatDate(item.effective_to)}</td><td className="px-4 py-3">V{item.version}</td></tr>)}</tbody></table></div> : <EmptyState title="No KPI targets" message="Create targets for decision-relevant KPIs. KPIs without targets remain informational." />}</Panel>
          {canManage ? <Panel title="New target version" description="The previous open-ended version will be closed the day before this one takes effect."><form className="space-y-3" onSubmit={createTarget}><label className="block text-sm">KPI<select required value={targetForm.kpi_definition_id} onChange={(event) => setTargetForm((form) => ({ ...form, kpi_definition_id: event.target.value }))} className={inputClass}><option value="">Select KPI</option>{definitions.filter((item, index, all) => all.findIndex((candidate) => candidate.key === item.key) === index).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label><label className="block text-sm">Site override<select value={targetForm.site_id} onChange={(event) => setTargetForm((form) => ({ ...form, site_id: event.target.value, department_id: '' }))} className={inputClass}><option value="">Organisation target</option>{sites.map((site) => <option key={site.id} value={site.id}>{site.name}</option>)}</select></label><label className="block text-sm">Department override<select value={targetForm.department_id} onChange={(event) => setTargetForm((form) => ({ ...form, department_id: event.target.value, site_id: '' }))} className={inputClass}><option value="">No department override</option>{departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>{[['target_value', 'Target'], ['warning_threshold', 'Warning threshold'], ['critical_threshold', 'Critical threshold']].map(([key, label]) => <label key={key} className="block text-sm">{label}<input required={key === 'target_value'} type="number" step="any" value={targetForm[key]} onChange={(event) => setTargetForm((form) => ({ ...form, [key]: event.target.value }))} className={inputClass} /></label>)}<label className="block text-sm">Effective from<input required type="date" value={targetForm.effective_from} onChange={(event) => setTargetForm((form) => ({ ...form, effective_from: event.target.value }))} className={inputClass} /></label><button disabled={isBusy} className={`${primaryButton} w-full`}>Create target version</button></form></Panel> : null}
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4"><div className="flex gap-3"><AlertTriangle className="mt-0.5 size-5 text-amber-700" /><div><p className="font-semibold text-amber-950">{exceptions.length} management exceptions</p><p className="mt-1 text-sm text-amber-800">Ranked by deterministic severity and age; no AI ranking is used.</p></div></div></div>
        <div className="rounded-xl border border-sky-200 bg-sky-50 p-4"><div className="flex gap-3"><CalendarRange className="mt-0.5 size-5 text-sky-700" /><div><p className="font-semibold text-sky-950">{forwardView.length} obligations in the 90-day view</p><p className="mt-1 text-sm text-sky-800">Permits, training, medical, compliance, documents, audits, inspections, contractors, actions, and equipment.</p></div></div></div>
      </div>
    </div>
  )
}
