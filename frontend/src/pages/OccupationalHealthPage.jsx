import { useCallback, useEffect, useMemo, useState } from 'react'
import { Activity, BellRing, Download, HeartPulse, Plus, RefreshCw, Search, ShieldCheck } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { Badge } from '../components/Badge.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, formatNumber, humanize } from '../lib/formatters.js'
import { hasPermission } from '../lib/rbac.js'

const TAB_LABELS = {
  dashboard: 'Dashboard',
  surveillance: 'Surveillance',
  workers: 'Workers',
  appointments: 'Appointments',
  assessments: 'Assessments',
  restrictions: 'Restrictions',
  exposure: 'Exposure',
  illnesses: 'Occupational Illness',
  providers: 'Providers',
  programmes: 'Programmes',
  compliance: 'Compliance',
}

const TABLES = {
  surveillance: [
    ['employee_user_id', 'Worker'], ['programme_name', 'Programme'], ['compliance_status', 'Compliance', 'badge'],
    ['fitness_outcome', 'Fitness', 'badge'], ['due_date', 'Due', 'date'], ['next_due_date', 'Next due', 'date'],
  ],
  appointments: [
    ['worker_user_id', 'Worker'], ['programme_id', 'Programme'], ['appointment_at', 'Appointment', 'datetime'],
    ['location', 'Location'], ['status', 'Status', 'badge'],
  ],
  assessments: [
    ['worker_user_id', 'Worker'], ['assessment_type', 'Type'], ['assessment_date', 'Assessed', 'date'],
    ['fitness_outcome', 'Fitness', 'badge'], ['next_due_date', 'Next due', 'date'],
    ['operational_restrictions', 'Operational restrictions'],
  ],
  restrictions: [
    ['worker_user_id', 'Worker'], ['restriction_type', 'Type'], ['description', 'Operational restriction'],
    ['effective_from', 'From', 'date'], ['effective_to', 'To', 'date'], ['review_date', 'Review', 'date'],
    ['status', 'Status', 'badge'],
  ],
  exposure: [
    ['worker_user_id', 'Worker'], ['exposure_type_id', 'Exposure'], ['risk_level', 'Risk', 'badge'],
    ['source_type', 'Source'], ['start_date', 'From', 'date'], ['end_date', 'To', 'date'],
  ],
  illnesses: [
    ['worker_user_id', 'Worker'], ['illness_category', 'Category'], ['date_identified', 'Identified', 'date'],
    ['status', 'Status', 'badge'], ['regulator_notification_required', 'Regulator notification'],
  ],
  providers: [
    ['name', 'Provider'], ['facility_name', 'Facility'], ['phone', 'Phone'], ['services', 'Services'], ['active', 'Status', 'boolean'],
  ],
  programmes: [
    ['name', 'Programme'], ['code', 'Code'], ['default_frequency_days', 'Frequency (days)'],
    ['validity_period_days', 'Validity (days)'], ['certificate_required', 'Certificate', 'boolean'], ['active', 'Status', 'boolean'],
  ],
  compliance: [
    ['employee_user_id', 'Worker'], ['programme_name', 'Programme'], ['compliance_status', 'Compliance', 'badge'],
    ['fitness_outcome', 'Fitness', 'badge'], ['expiry_date', 'Certificate / validity expiry', 'date'],
  ],
  certificates: [
    ['worker_user_id', 'Worker'], ['certificate_number', 'Certificate'], ['programme_id', 'Programme'],
    ['issued_date', 'Issued', 'date'], ['expiry_date', 'Expires', 'date'], ['fitness_outcome', 'Fitness', 'badge'],
    ['renewal_status', 'Renewal', 'badge'],
  ],
  requirements: [
    ['name', 'Requirement'], ['programme_id', 'Programme'], ['job_title', 'Job title'],
    ['department_id', 'Department'], ['site_id', 'Site'], ['frequency_days', 'Frequency (days)'],
    ['mandatory', 'Mandatory', 'boolean'],
  ],
}

function display(value, type) {
  if (type === 'badge') return <Badge value={value || 'pending'} />
  if (type === 'date') return formatDate(value)
  if (type === 'datetime') return formatDateTime(value)
  if (type === 'boolean') return value ? 'Active / Yes' : 'Inactive / No'
  if (Array.isArray(value)) return value.length ? value.join(', ') : '--'
  return value ?? '--'
}

function RecordTable({ records, columns }) {
  if (!records.length) {
    return <div className="rounded-xl border border-dashed border-stone-300 bg-white px-6 py-12 text-center text-sm text-stone-500">No records in this view.</div>
  }
  return (
    <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-stone-200 text-sm">
        <thead className="bg-stone-50"><tr>{columns.map(([key, label]) => <th key={key} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</th>)}</tr></thead>
        <tbody className="divide-y divide-stone-100">
          {records.map((record) => (
            <tr key={record.id} className="align-top hover:bg-stone-50/70">
              {columns.map(([key, , type]) => <td key={key} className="max-w-xs px-4 py-3 text-stone-700">{display(record[key], type)}</td>)}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Field({ field, value, onChange }) {
  const shared = {
    id: field.name,
    name: field.name,
    value: value ?? '',
    required: field.required,
    onChange: (event) => onChange(field.name, event.target.value),
    className: 'mt-1.5 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100',
  }
  return (
    <label htmlFor={field.name} className={field.wide ? 'sm:col-span-2' : ''}>
      <span className="text-xs font-semibold uppercase tracking-wide text-stone-600">{field.label}</span>
      {field.type === 'select' ? (
        <select {...shared}><option value="">Select…</option>{field.options.map((option) => <option key={option.value} value={option.value}>{option.label}</option>)}</select>
      ) : field.type === 'textarea' ? (
        <textarea {...shared} rows={3} />
      ) : (
        <input {...shared} type={field.type || 'text'} />
      )}
    </label>
  )
}

function CreatePanel({ title, fields, onSubmit, isSaving }) {
  const [values, setValues] = useState({})
  async function submit(event) {
    event.preventDefault()
    const saved = await onSubmit(values)
    if (saved) setValues({})
  }
  return (
    <form onSubmit={submit} className="rounded-xl border border-emerald-200 bg-emerald-50/50 p-5">
      <div className="flex items-center gap-2"><Plus className="size-4 text-emerald-700" /><h3 className="font-semibold text-stone-950">{title}</h3></div>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {fields.map((field) => <Field key={field.name} field={field} value={values[field.name]} onChange={(name, value) => setValues((current) => ({ ...current, [name]: value }))} />)}
      </div>
      <button type="submit" disabled={isSaving} className="mt-4 inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:opacity-50">
        {isSaving ? <RefreshCw className="size-4 animate-spin" /> : <Plus className="size-4" />} Save
      </button>
    </form>
  )
}

function metricCards(summary) {
  return [
    ['Workers requiring', summary?.workers_requiring_surveillance],
    ['Compliance rate', summary?.compliance_rate == null ? 'Insufficient data' : `${summary.compliance_rate}%`],
    ['Due in 30 days', summary?.due_30],
    ['Overdue', summary?.overdue_assessments],
    ['Scheduled', summary?.appointments_scheduled],
    ['Missed', summary?.missed_appointments],
    ['Expired certificates', summary?.expired_certificates],
    ['Active restrictions', summary?.active_restrictions],
    ['RTW reviews due', summary?.return_to_work_reviews_due],
    ['Confirmed illness cases', summary?.occupational_illness_confirmed],
  ]
}

export function OccupationalHealthPage() {
  const { token, user } = useAuth()
  const canReport = hasPermission(user, 'occupational_health.reports.view')
  const canViewCompliance = hasPermission(user, 'medical_surveillance.view_compliance')
  const canViewDashboard = canReport || canViewCompliance
  const canManage = hasPermission(user, 'medical_surveillance.manage')
  const canViewMedical = hasPermission(user, 'occupational_health.medical_detail.view')
  const canManageMedical = hasPermission(user, 'occupational_health.medical_detail.manage')
  const canManageFitness = hasPermission(user, 'occupational_health.fitness.manage')
  const [activeTab, setActiveTab] = useState(canViewDashboard ? 'dashboard' : 'workers')
  const [data, setData] = useState({ surveillance: [], appointments: [], assessments: [], certificates: [], restrictions: [], exposure: [], illnesses: [], providers: [], programmes: [], requirements: [], exposureTypes: [] })
  const [dashboardData, setDashboardData] = useState(null)
  const [profile, setProfile] = useState(null)
  const [workerId, setWorkerId] = useState(String(user?.id ?? ''))
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const tabs = useMemo(() => [
    ...(canViewDashboard ? ['dashboard'] : []), 'surveillance', 'workers', 'appointments',
    ...(canViewMedical ? ['assessments'] : []), 'restrictions', 'exposure',
    ...(canManage || canViewMedical ? ['illnesses'] : []),
    ...(canManage ? ['providers', 'programmes'] : []), 'compliance',
  ], [canManage, canViewDashboard, canViewMedical])

  const load = useCallback(async () => {
    await Promise.resolve()
    setIsLoading(true); setError('')
    const requests = {
      surveillance: apiClient.getOccupationalHealth(token),
      appointments: apiClient.getOccupationalHealth(token, 'appointments'),
      certificates: apiClient.getOccupationalHealth(token, 'certificates'),
      restrictions: apiClient.getOccupationalHealth(token, 'restrictions'),
      exposure: apiClient.getOccupationalHealth(token, 'exposures'),
      programmes: apiClient.getOccupationalHealth(token, 'programmes'),
      exposureTypes: apiClient.getOccupationalHealth(token, 'exposure-types'),
      ...(canViewMedical ? { assessments: apiClient.getOccupationalHealth(token, 'assessments') } : {}),
      ...(canManage || canViewMedical ? { illnesses: apiClient.getOccupationalHealth(token, 'occupational-illnesses') } : {}),
      ...(canManage ? { providers: apiClient.getOccupationalHealth(token, 'providers') } : {}),
      ...(canManage ? { requirements: apiClient.getOccupationalHealth(token, 'requirements') } : {}),
      ...(canViewDashboard ? { dashboard: apiClient.getOccupationalHealth(token, 'dashboard') } : {}),
    }
    const keys = Object.keys(requests)
    const results = await Promise.allSettled(Object.values(requests))
    const next = { surveillance: [], appointments: [], assessments: [], certificates: [], restrictions: [], exposure: [], illnesses: [], providers: [], programmes: [], requirements: [], exposureTypes: [] }
    let firstError = null
    results.forEach((result, index) => {
      const key = keys[index]
      if (result.status === 'fulfilled') {
        if (key === 'dashboard') setDashboardData(result.value)
        else next[key] = result.value?.items ?? result.value ?? []
      } else if (!firstError) firstError = result.reason
    })
    setData(next)
    if (firstError) setError(firstError)
    setIsLoading(false)
  }, [canManage, canViewDashboard, canViewMedical, token])

  useEffect(() => {
    const timeoutId = window.setTimeout(load, 0)
    return () => window.clearTimeout(timeoutId)
  }, [load])

  const programmeOptions = data.programmes.map((item) => ({ value: String(item.id), label: item.name }))
  const exposureOptions = data.exposureTypes.map((item) => ({ value: String(item.id), label: item.name }))
  const fieldSets = {
    surveillance: [
      { name: 'employee_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'programme_id', label: 'Programme', type: 'select', options: programmeOptions, required: true },
      { name: 'due_date', label: 'Due date', type: 'date', required: true },
    ],
    appointments: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'programme_id', label: 'Programme', type: 'select', options: programmeOptions, required: true },
      { name: 'appointment_at', label: 'Appointment', type: 'datetime-local', required: true },
      { name: 'location', label: 'Location' },
    ],
    assessments: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'programme_id', label: 'Programme', type: 'select', options: programmeOptions, required: true },
      { name: 'assessment_type', label: 'Assessment type', required: true },
      { name: 'assessment_date', label: 'Assessment date', type: 'date', required: true },
      { name: 'fitness_outcome', label: 'Fitness outcome', type: 'select', required: true, options: ['fit', 'fit_with_restrictions', 'temporarily_unfit', 'permanently_unfit', 'pending_further_assessment', 'not_applicable'].map((value) => ({ value, label: humanize(value) })) },
      { name: 'operational_restrictions', label: 'Operational restrictions', type: 'textarea', wide: true },
      { name: 'confidential_notes', label: 'Confidential clinical notes', type: 'textarea', wide: true },
    ],
    restrictions: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'restriction_type', label: 'Restriction type', required: true },
      { name: 'description', label: 'Operational description', type: 'textarea', required: true, wide: true },
      { name: 'effective_from', label: 'Effective from', type: 'date', required: true },
      { name: 'effective_to', label: 'Effective to', type: 'date' },
      { name: 'review_date', label: 'Review date', type: 'date' },
      { name: 'lifting_limit_kg', label: 'Lifting limit (kg)', type: 'number' },
    ],
    exposure: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'exposure_type_id', label: 'Exposure type', type: 'select', options: exposureOptions, required: true },
      { name: 'start_date', label: 'Start date', type: 'date', required: true },
      { name: 'risk_level', label: 'Risk level', type: 'select', options: ['low', 'medium', 'high', 'critical'].map((value) => ({ value, label: humanize(value) })) },
      { name: 'source_reference', label: 'Source / reference' },
    ],
    illnesses: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'illness_category', label: 'Illness category', required: true },
      { name: 'date_identified', label: 'Date identified', type: 'date', required: true },
      { name: 'status', label: 'Case status', type: 'select', options: ['suspected', 'under_assessment', 'confirmed', 'monitoring', 'resolved', 'closed'].map((value) => ({ value, label: humanize(value) })) },
      { name: 'symptoms_summary', label: 'Symptoms summary', type: 'textarea', wide: true },
      { name: 'diagnosis_detail', label: 'Confidential diagnosis detail', type: 'textarea', wide: true },
    ],
    providers: [
      { name: 'name', label: 'Provider name', required: true }, { name: 'facility_name', label: 'Facility' },
      { name: 'phone', label: 'Phone' }, { name: 'email', label: 'Email', type: 'email' },
      { name: 'address', label: 'Address', type: 'textarea', wide: true },
    ],
    programmes: [
      { name: 'name', label: 'Programme name', required: true }, { name: 'code', label: 'Code', required: true },
      { name: 'default_frequency_days', label: 'Frequency (days)', type: 'number' },
      { name: 'validity_period_days', label: 'Validity (days)', type: 'number' },
      { name: 'description', label: 'Description', type: 'textarea', wide: true },
    ],
    requirements: [
      { name: 'programme_id', label: 'Programme', type: 'select', options: programmeOptions, required: true },
      { name: 'name', label: 'Requirement name', required: true },
      { name: 'job_title', label: 'Applicable job title', required: true },
      { name: 'frequency_days', label: 'Frequency (days)', type: 'number' },
      { name: 'validity_period_days', label: 'Validity (days)', type: 'number' },
      { name: 'rationale', label: 'Operational rationale', type: 'textarea', wide: true },
    ],
    certificates: [
      { name: 'worker_user_id', label: 'Worker user ID', type: 'number', required: true },
      { name: 'programme_id', label: 'Programme', type: 'select', options: programmeOptions, required: true },
      { name: 'certificate_number', label: 'Certificate number', required: true },
      { name: 'issued_date', label: 'Issued date', type: 'date', required: true },
      { name: 'expiry_date', label: 'Expiry date', type: 'date', required: true },
      { name: 'fitness_outcome', label: 'Fitness outcome', type: 'select', required: true, options: ['fit', 'fit_with_restrictions', 'temporarily_unfit', 'permanently_unfit', 'pending_further_assessment', 'not_applicable'].map((value) => ({ value, label: humanize(value) })) },
      { name: 'operational_restrictions', label: 'Operational restrictions', type: 'textarea', wide: true },
    ],
  }

  function buildPayload(tab, values) {
    const numberFields = new Set(['employee_user_id', 'worker_user_id', 'programme_id', 'exposure_type_id', 'lifting_limit_kg', 'default_frequency_days', 'frequency_days', 'validity_period_days'])
    const payload = Object.fromEntries(Object.entries(values).filter(([, value]) => value !== '').map(([key, value]) => [key, numberFields.has(key) ? Number(value) : value]))
    if (tab === 'surveillance') {
      const programme = data.programmes.find((item) => item.id === payload.programme_id)
      payload.surveillance_type = programme?.name || 'Medical surveillance'
    }
    if (tab === 'appointments' && payload.appointment_at) payload.appointment_at = new Date(payload.appointment_at).toISOString()
    return payload
  }

  const endpointFor = { surveillance: '', appointments: 'appointments', assessments: 'assessments', certificates: 'certificates', restrictions: 'restrictions', exposure: 'exposures', illnesses: 'occupational-illnesses', providers: 'providers', programmes: 'programmes', requirements: 'requirements' }
  const canCreate = {
    surveillance: canManage, appointments: canManage, assessments: canManageMedical,
    restrictions: canManageFitness, exposure: canManage, illnesses: canManageMedical,
    providers: canManage, programmes: canManage,
    requirements: canManage, certificates: canManageFitness,
  }

  async function save(tab, values) {
    setIsSaving(true); setError(''); setSuccess('')
    try {
      await apiClient.createOccupationalHealth(token, endpointFor[tab], buildPayload(tab, values))
      setSuccess(`${TAB_LABELS[tab]} record saved.`); await load(); return true
    } catch (requestError) { setError(requestError); return false }
    finally { setIsSaving(false) }
  }

  async function runReminders() {
    setIsSaving(true); setError('')
    try {
      const result = await apiClient.createOccupationalHealth(token, 'reminders/run', {})
      setSuccess(`Reminder run completed (${Object.values(result).reduce((sum, value) => sum + value, 0)} created).`)
      await load()
    } catch (requestError) { setError(requestError) }
    finally { setIsSaving(false) }
  }

  async function findWorker() {
    setError(''); setProfile(null)
    try { setProfile(await apiClient.getOccupationalHealth(token, `workers/${Number(workerId)}/profile`)) }
    catch (requestError) { setError(requestError) }
  }

  async function download(type) {
    try {
      const { blob, filename } = await apiClient.downloadFile(token, `/medical-surveillance/exports/${type}.csv`, { fallbackFilename: `occupational-health-${type}.csv` })
      const url = URL.createObjectURL(blob); const link = document.createElement('a'); link.href = url; link.download = filename; link.click(); URL.revokeObjectURL(url)
    } catch (requestError) { setError(requestError) }
  }

  if (isLoading) return <LoadingState title="Loading Occupational Health" message="Applying tenant, privacy, and workforce scope." />

  const records = activeTab === 'compliance' ? data.surveillance : data[activeTab] ?? []
  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Phase 2C" title="Occupational Health" description="Exposure-to-surveillance workflow with operational fitness visibility and separate confidential medical access." actions={<>
        {canManage ? <button type="button" onClick={runReminders} disabled={isSaving} className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50"><BellRing className="size-4" />Run reminders</button> : null}
        {canReport ? <button type="button" onClick={() => download('compliance')} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-800"><Download className="size-4" />Compliance CSV</button> : null}
      </>} />

      <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900"><div className="flex gap-3"><ShieldCheck className="mt-0.5 size-5 shrink-0" /><p><strong>Privacy boundary:</strong> this workspace exposes operational fitness and restrictions broadly. Diagnoses, clinical results, and confidential notes require a separate medical-detail permission.</p></div></div>
      {success ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800">{success}</div> : null}
      {error ? <ErrorState message={error?.message ?? String(error)} onRetry={load} /> : null}

      <div className="flex gap-2 overflow-x-auto border-b border-stone-200 pb-2">
        {tabs.map((tab) => <button key={tab} type="button" onClick={() => setActiveTab(tab)} className={`shrink-0 rounded-full px-3 py-2 text-sm font-semibold transition ${activeTab === tab ? 'bg-emerald-100 text-emerald-900' : 'text-stone-600 hover:bg-stone-100'}`}>{TAB_LABELS[tab]}</button>)}
      </div>

      {activeTab === 'dashboard' ? (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">{metricCards(dashboardData).map(([label, value]) => <div key={label} className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p><p className="mt-2 text-2xl font-semibold text-stone-950">{typeof value === 'number' ? formatNumber(value) : value ?? '--'}</p></div>)}</div>
          <div className="rounded-xl border border-stone-200 bg-white p-5"><div className="flex items-center gap-2"><Activity className="size-5 text-emerald-700" /><h2 className="font-semibold">Programme compliance</h2></div><div className="mt-4 space-y-3">{(dashboardData?.by_programme ?? []).map((item) => <div key={item.programme} className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 pb-3"><span className="font-medium text-stone-800">{item.programme}</span><div className="flex gap-2 text-xs text-stone-600"><span>{item.compliant ?? 0} compliant</span><span>{item.due_soon ?? 0} due</span><span>{item.overdue ?? 0} overdue</span></div></div>)}</div></div>
        </div>
      ) : activeTab === 'workers' ? (
        <div className="space-y-5">
          <div className="rounded-xl border border-stone-200 bg-white p-5"><h2 className="font-semibold text-stone-950">Worker occupational-health profile</h2><div className="mt-3 flex max-w-md gap-2"><input value={workerId} onChange={(event) => setWorkerId(event.target.value)} type="number" className="min-w-0 flex-1 rounded-lg border border-stone-300 px-3 py-2 text-sm" placeholder="Worker user ID" /><button type="button" onClick={findWorker} className="inline-flex items-center gap-2 rounded-lg bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><Search className="size-4" />Open profile</button></div></div>
          {profile ? <div className="space-y-4"><div className="rounded-xl border border-stone-200 bg-white p-5"><div className="flex items-center gap-3"><HeartPulse className="size-6 text-emerald-700" /><div><h3 className="font-semibold">{profile.worker.full_name}</h3><p className="text-sm text-stone-500">{profile.worker.job_title || 'Job title not recorded'} · Site #{profile.worker.site_id ?? '--'}</p></div></div><div className="mt-4 flex flex-wrap gap-2">{Object.entries(profile.summary).map(([key, value]) => <span key={key} className="rounded-full bg-stone-100 px-3 py-1 text-xs font-medium text-stone-700">{humanize(key)}: {value}</span>)}</div></div><RecordTable records={profile.required_programmes.map((item) => ({ id: item.requirement_id, ...item }))} columns={[["programme_name", "Required programme"], ["requirement_name", "Why required"], ["compliance_status", "Compliance", "badge"], ["due_date", "Due", "date"]]} /><RecordTable records={profile.appointments} columns={TABLES.appointments} /><RecordTable records={profile.certificates} columns={TABLES.certificates} /><RecordTable records={profile.restrictions} columns={TABLES.restrictions} /></div> : null}
        </div>
      ) : (
        <div className="space-y-5">
          {canCreate[activeTab] && fieldSets[activeTab] ? <CreatePanel title={`Add ${TAB_LABELS[activeTab]} record`} fields={fieldSets[activeTab]} onSubmit={(values) => save(activeTab, values)} isSaving={isSaving} /> : null}
          {activeTab === 'programmes' && canManage ? <><CreatePanel title="Add surveillance requirement" fields={fieldSets.requirements} onSubmit={(values) => save('requirements', values)} isSaving={isSaving} /><RecordTable records={data.requirements} columns={TABLES.requirements} /></> : null}
          {activeTab === 'compliance' && canManageFitness ? <CreatePanel title="Add fitness certificate" fields={fieldSets.certificates} onSubmit={(values) => save('certificates', values)} isSaving={isSaving} /> : null}
          {activeTab === 'compliance' && canReport ? <div className="flex flex-wrap gap-2"><button type="button" onClick={() => download('due-overdue')} className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold"><Download className="size-4" />Due / overdue</button><button type="button" onClick={() => download('certificates')} className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold"><Download className="size-4" />Certificate expiry</button><button type="button" onClick={() => download('restrictions')} className="inline-flex items-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold"><Download className="size-4" />Restrictions register</button></div> : null}
          <RecordTable records={records} columns={TABLES[activeTab]} />
          {activeTab === 'compliance' ? <RecordTable records={data.certificates} columns={TABLES.certificates} /> : null}
        </div>
      )}
    </div>
  )
}
