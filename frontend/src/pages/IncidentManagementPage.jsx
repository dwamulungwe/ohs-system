import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { AlertTriangle, Download, FilePlus2, Search } from 'lucide-react'

import { apiClient } from '../api/client.js'
import { Badge } from '../components/Badge.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, humanize } from '../lib/formatters.js'

const tabs = [
  'Overview', 'People', 'Immediate Response', 'Injury / Treatment', 'Witnesses',
  'Investigation', 'Event Timeline', 'Root Causes', 'Findings', 'Actions',
  'Regulatory', 'Return to Work', 'Evidence', 'Activity', 'Closure',
]

function Field({ label, value, badge = false }) {
  return (
    <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
      <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p>
      <div className="mt-2 text-sm font-medium text-stone-900">
        {badge ? <Badge value={value} /> : (value ?? '--')}
      </div>
    </div>
  )
}

function EmptyPanel({ text }) {
  return <p className="rounded-lg border border-dashed border-stone-300 px-4 py-8 text-center text-sm text-stone-500">{text}</p>
}

function RecordCards({ records, render }) {
  if (!records?.length) return <EmptyPanel text="No records have been added in this section." />
  return <div className="grid gap-3">{records.map((record) => <div key={record.id} className="rounded-lg border border-stone-200 bg-stone-50 p-4">{render(record)}</div>)}</div>
}

function IncidentDetail({ incidentId }) {
  const { token } = useAuth()
  const [workspace, setWorkspace] = useState(null)
  const [medical, setMedical] = useState(null)
  const [investigations, setInvestigations] = useState([])
  const [actions, setActions] = useState([])
  const [activeTab, setActiveTab] = useState('Overview')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const [incident, investigationItems, actionItems] = await Promise.all([
        apiClient.getIncidentWorkspace(token, incidentId),
        apiClient.getCollection(token, `/incident-investigations?incident_id=${incidentId}`),
        apiClient.getCollection(token, '/corrective-actions?source_type=incident&limit=500'),
      ])
      setWorkspace(incident)
      setInvestigations(investigationItems)
      setActions(actionItems.filter((item) => Number(item.source_id) === Number(incidentId)))
      try {
        setMedical(await apiClient.getIncidentMedical(token, incidentId))
      } catch {
        setMedical(null)
      }
    } catch (loadError) {
      setError(loadError.message)
    } finally {
      setLoading(false)
    }
  }, [incidentId, token])

  useEffect(() => {
    const timer = window.setTimeout(load, 0)
    return () => window.clearTimeout(timer)
  }, [load])

  if (loading) return <LoadingState title="Loading incident workspace" />
  if (error) return <ErrorState message={error} onRetry={load} />
  if (!workspace) return null

  const panel = {
    Overview: (
      <div className="grid gap-3 md:grid-cols-3">
        <Field label="Reference" value={workspace.incident_reference} />
        <Field label="Lifecycle" value={workspace.status} badge />
        <Field label="Severity" value={workspace.severity} badge />
        <Field label="Classification" value={humanize(workspace.incident_type)} />
        <Field label="Occurred" value={formatDateTime(workspace.occurred_at)} />
        <Field label="Reported" value={formatDateTime(workspace.reported_at)} />
        <Field label="Site" value={`Site #${workspace.site_id}`} />
        <Field label="Department" value={workspace.department_id ? `Department #${workspace.department_id}` : '--'} />
        <Field label="Area / Location" value={workspace.area_location} />
        <div className="md:col-span-3 rounded-lg border border-stone-200 bg-stone-50 p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">What happened</p>
          <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-stone-800">{workspace.description}</p>
        </div>
      </div>
    ),
    People: <RecordCards records={workspace.people} render={(person) => <><div className="flex items-center justify-between"><p className="font-semibold text-stone-900">{person.external_name || `User #${person.user_id}`}</p><Badge value={person.involvement_role} /></div><p className="mt-2 text-sm text-stone-600">{person.job_title || 'Role not recorded'} · {person.department_name || 'Department not recorded'}</p></>} />,
    'Immediate Response': (
      <div className="space-y-4">
        <div className="grid gap-3 md:grid-cols-3"><Field label="Scene Secured" value={workspace.scene_secured ? 'Yes' : 'No'} /><Field label="Work Stopped" value={workspace.work_stopped ? 'Yes' : 'No'} /><Field label="Emergency Services" value={workspace.emergency_services_called ? 'Called' : 'Not called'} /></div>
        <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">{Object.entries(workspace.immediate_response || {}).map(([key, value]) => <Field key={key} label={humanize(key)} value={value ? 'Yes' : 'No'} />)}</div>
        <p className="rounded-lg bg-stone-50 p-4 text-sm leading-6 text-stone-700">{workspace.immediate_response_notes || workspace.immediate_actions_taken || 'No narrative response notes.'}</p>
      </div>
    ),
    'Injury / Treatment': medical ? <div className="space-y-5"><h3 className="font-semibold">Injuries / illnesses</h3><RecordCards records={medical.injuries} render={(item) => <><div className="flex justify-between"><span className="font-semibold">Person #{item.incident_person_id}</span><Badge value={item.fatality ? 'critical' : item.injury_type || 'recorded'} /></div><p className="mt-2 text-sm text-stone-600">{item.diagnosis_description || 'Diagnosis not recorded'} · {item.days_lost} days lost · {item.restricted_work_days} restricted days</p></>} /><h3 className="font-semibold">Treatment</h3><RecordCards records={medical.treatments} render={(item) => <><div className="flex justify-between"><span className="font-semibold">{humanize(item.treatment_type)}</span><span className="text-sm text-stone-500">{formatDateTime(item.treatment_at)}</span></div><p className="mt-2 text-sm text-stone-600">{item.treatment_summary || 'Summary not recorded'}</p></>} /></div> : <EmptyPanel text="Medical details are restricted. You do not have incident medical access." />,
    Witnesses: <RecordCards records={workspace.witnesses} render={(item) => <><div className="flex justify-between"><span className="font-semibold">{item.witness_name}</span><span className="text-sm text-stone-500">{formatDateTime(item.statement_at)}</span></div><p className="mt-2 whitespace-pre-wrap text-sm text-stone-700">{item.statement}</p></>} />,
    Investigation: <RecordCards records={investigations} render={(item) => <><div className="flex justify-between"><span className="font-semibold">Investigation #{item.id}</span><Badge value={item.status} /></div><div className="mt-3 grid gap-2 sm:grid-cols-3"><Field label="Lead" value={item.investigation_lead_user_id ? `User #${item.investigation_lead_user_id}` : 'Unassigned'} /><Field label="Due" value={formatDate(item.target_completion_date)} /><Field label="Overdue" value={item.is_overdue ? 'Yes' : 'No'} /></div><p className="mt-3 text-sm text-stone-600">{item.scope || 'Scope not recorded'}</p></>} />,
    'Event Timeline': <RecordCards records={workspace.events} render={(item) => <><div className="flex justify-between"><Badge value={item.event_type} /><span className="text-sm text-stone-500">{formatDateTime(item.event_at)}</span></div><p className="mt-2 text-sm text-stone-700">{item.description}</p></>} />,
    'Root Causes': <RecordCards records={workspace.causes} render={(item) => <><div className="flex justify-between"><Badge value={item.cause_level} /><span className="text-sm text-stone-500">{humanize(item.category_code)}</span></div><p className="mt-2 text-sm text-stone-700">{item.description}</p>{item.why_steps?.length ? <ol className="mt-3 list-decimal space-y-1 pl-5 text-sm text-stone-600">{item.why_steps.map((step) => <li key={step.sequence}>{step.answer}</li>)}</ol> : null}</>} />,
    Findings: <RecordCards records={workspace.findings} render={(item) => <><div className="flex justify-between"><span className="font-semibold">{item.title}</span><Badge value={item.severity} /></div><p className="mt-2 text-sm text-stone-700">{item.description}</p><p className="mt-2 text-xs text-stone-500">{item.unified_action_id ? `Unified Action #${item.unified_action_id}` : item.action_required ? 'Action required' : 'No action required'}</p></>} />,
    Actions: <RecordCards records={actions} render={(item) => <Link to={`/corrective-actions/${item.id}`} className="block"><div className="flex justify-between"><span className="font-semibold text-emerald-800">{item.action_reference} · {item.title}</span><Badge value={item.lifecycle_status} /></div><p className="mt-2 text-sm text-stone-600">Owner: {item.owner_name || 'Unassigned'} · Due {formatDate(item.current_due_date)}</p></Link>} />,
    Regulatory: <RecordCards records={workspace.regulatory_notifications} render={(item) => <><div className="flex justify-between"><span className="font-semibold">{item.regulator_name}</span><Badge value={item.status} /></div><p className="mt-2 text-sm text-stone-600">Deadline {formatDateTime(item.notification_deadline)} · Ref {item.regulator_reference || '--'}</p></>} />,
    'Return to Work': medical ? <RecordCards records={medical.return_to_work_records} render={(item) => <><div className="flex justify-between"><span className="font-semibold">Person #{item.incident_person_id}</span><Badge value={item.status} /></div><p className="mt-2 text-sm text-stone-600">Planned {formatDate(item.planned_return_date)} · Actual {formatDate(item.actual_return_date)}</p><p className="mt-1 text-sm text-stone-600">{item.restrictions || 'No restrictions recorded'}</p></>} /> : <EmptyPanel text="Return-to-work details require incident medical access." />,
    Evidence: <RecordCards records={workspace.attachments} render={(item) => <><p className="font-semibold">{item.original_filename}</p><p className="mt-1 text-sm text-stone-500">{item.evidence_type || 'General evidence'} · {formatDateTime(item.created_at)}</p></>} />,
    Activity: <RecordCards records={workspace.activities} render={(item) => <><div className="flex justify-between"><Badge value={item.event_type} /><span className="text-sm text-stone-500">{formatDateTime(item.created_at)}</span></div><p className="mt-2 text-sm text-stone-700">{item.summary}</p></>} />,
    Closure: <div className="grid gap-3 md:grid-cols-2"><Field label="Closure Requested" value={workspace.closure_requested ? 'Yes' : 'No'} /><Field label="Requested At" value={formatDateTime(workspace.closure_requested_at)} /><Field label="Verifier" value={workspace.closure_verifier_user_id ? `User #${workspace.closure_verifier_user_id}` : '--'} /><Field label="Verified At" value={formatDateTime(workspace.verified_at)} /><div className="md:col-span-2 rounded-lg bg-stone-50 p-4 text-sm text-stone-700"><p className="font-semibold">Closure summary</p><p className="mt-2">{workspace.closure_summary || 'Not prepared'}</p></div></div>,
  }[activeTab]

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Incident detail" title={`${workspace.incident_reference} · ${workspace.title}`} description="One controlled record from report through investigation, corrective action, recovery, verification and closure." actions={<Link to="/incidents" className="rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700">Back to register</Link>} />
      <div className="flex gap-2 overflow-x-auto border-b border-stone-200 pb-2">{tabs.map((tab) => <button key={tab} type="button" onClick={() => setActiveTab(tab)} className={`shrink-0 rounded-full px-3 py-2 text-sm font-medium ${activeTab === tab ? 'bg-emerald-700 text-white' : 'bg-stone-100 text-stone-700 hover:bg-stone-200'}`}>{tab}</button>)}</div>
      <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">{panel}</section>
    </div>
  )
}

function IncidentRegister() {
  const { token } = useAuth()
  const [incidents, setIncidents] = useState([])
  const [dashboard, setDashboard] = useState(null)
  const [filters, setFilters] = useState({ status: '', severity: '', incident_type: '', open_only: '' })
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      const params = { ...filters, open_only: filters.open_only === '' ? undefined : filters.open_only, limit: 500 }
      const [page, metrics] = await Promise.all([apiClient.getIncidents(token, params), apiClient.getIncidentDashboard(token)])
      setIncidents(page.items); setDashboard(metrics)
    } catch (loadError) { setError(loadError.message) } finally { setLoading(false) }
  }, [filters, token])
  async function exportRegister() {
    try {
      const { blob, filename } = await apiClient.downloadFile(token, '/exports/incident-register.csv', { fallbackFilename: 'incident-register.csv' })
      const url = URL.createObjectURL(blob)
      const anchor = document.createElement('a')
      anchor.href = url; anchor.download = filename; anchor.click()
      URL.revokeObjectURL(url)
    } catch (downloadError) {
      setError(downloadError.message)
    }
  }
  useEffect(() => {
    const timer = window.setTimeout(load, 0)
    return () => window.clearTimeout(timer)
  }, [load])
  const shown = useMemo(() => incidents.filter((item) => !search || `${item.incident_reference} ${item.title} ${item.description}`.toLowerCase().includes(search.toLowerCase())), [incidents, search])

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Enterprise incident management" title="Incident Register" description="Report, classify, investigate and verify every incident through one tenant-controlled lifecycle." actions={<><button type="button" onClick={exportRegister} className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700"><Download className="size-4" />Export</button><Link to="/quick-report" className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><FilePlus2 className="size-4" />Report incident</Link></>} />
      {dashboard ? <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5"><StatCard label="This period" value={dashboard.incidents_this_period} /><StatCard label="Open incidents" value={dashboard.open_incidents} accent="text-amber-700" accentBg="bg-amber-300" /><StatCard label="Open investigations" value={dashboard.open_investigations} /><StatCard label="Overdue investigations" value={dashboard.overdue_investigations} accent="text-rose-700" accentBg="bg-rose-300" /><StatCard label="Awaiting closure" value={dashboard.awaiting_closure} /></div> : null}
      <section className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
        <div className="grid gap-3 md:grid-cols-5"><label className="relative md:col-span-2"><Search className="absolute left-3 top-3 size-4 text-stone-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search reference, title or description" className="w-full rounded-lg border border-stone-300 py-2.5 pl-9 pr-3 text-sm" /></label>{[['status', ['reported', 'triaged', 'under_investigation', 'actions_open', 'pending_closure', 'closed', 'reopened']], ['severity', ['low', 'medium', 'high', 'critical']], ['open_only', ['true', 'false']]].map(([key, options]) => <select key={key} value={filters[key]} onChange={(event) => setFilters((current) => ({ ...current, [key]: event.target.value }))} className="rounded-lg border border-stone-300 px-3 py-2.5 text-sm"><option value="">All {humanize(key)}</option>{options.map((option) => <option key={option} value={option}>{humanize(option)}</option>)}</select>)}</div>
      </section>
      {loading ? <LoadingState title="Loading incident register" /> : error ? <ErrorState message={error} onRetry={load} /> : (
        <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white shadow-sm"><table className="min-w-[1200px] w-full text-left text-sm"><thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500"><tr>{['Reference', 'Date / Time', 'Site', 'Department', 'Type', 'Severity', 'Title', 'Affected', 'Regulator', 'Status', 'Age', 'Indicator'].map((label) => <th key={label} className="px-4 py-3">{label}</th>)}</tr></thead><tbody className="divide-y divide-stone-100">{shown.map((item) => <tr key={item.id} className="hover:bg-emerald-50/40"><td className="px-4 py-3"><Link to={`/incidents/${item.id}`} className="font-semibold text-emerald-800">{item.incident_reference}</Link></td><td className="px-4 py-3 text-stone-600">{formatDateTime(item.occurred_at)}</td><td className="px-4 py-3">#{item.site_id}</td><td className="px-4 py-3">{item.department_id ? `#${item.department_id}` : '--'}</td><td className="px-4 py-3">{humanize(item.incident_type)}</td><td className="px-4 py-3"><Badge value={item.severity} /></td><td className="max-w-xs px-4 py-3 font-medium">{item.title}</td><td className="px-4 py-3">{item.persons_affected}</td><td className="px-4 py-3"><Badge value={item.regulator_notification_status} /></td><td className="px-4 py-3"><Badge value={item.status} /></td><td className="px-4 py-3">{item.age_days}d</td><td className="px-4 py-3">{item.severity === 'critical' && item.status !== 'closed' ? <span className="inline-flex items-center gap-1 text-xs font-semibold text-rose-700"><AlertTriangle className="size-4" />Critical / open</span> : '--'}</td></tr>)}</tbody></table>{shown.length === 0 ? <EmptyPanel text="No incidents match the current filters." /> : null}</div>
      )}
    </div>
  )
}

export function IncidentManagementPage() {
  const { id } = useParams()
  return id ? <IncidentDetail incidentId={id} /> : <IncidentRegister />
}
