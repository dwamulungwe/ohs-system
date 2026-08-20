import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  Award,
  BellRing,
  BookOpenCheck,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Download,
  FileBadge,
  Gauge,
  GraduationCap,
  IdCard,
  LayoutDashboard,
  Search,
  ShieldAlert,
  ShieldCheck,
  TableProperties,
  UserRoundCheck,
  Users,
} from 'lucide-react'
import { apiClient } from '../api/client.js'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, formatNumber } from '../lib/formatters.js'
import { hasPermission } from '../lib/rbac.js'

const MANAGER_TABS = [
  ['dashboard', 'Dashboard', LayoutDashboard],
  ['workers', 'My Training / Workers', Users],
  ['courses', 'Courses', GraduationCap],
  ['competencies', 'Competencies', Award],
  ['requirements', 'Requirements Matrix', TableProperties],
  ['sessions', 'Sessions', CalendarDays],
  ['assessments', 'Assessments', ClipboardCheck],
  ['certificates', 'Certificates', FileBadge],
  ['authorizations', 'Authorizations', IdCard],
  ['matrix', 'Competency Matrix', UserRoundCheck],
  ['requests', 'Training Requests', BookOpenCheck],
  ['compliance', 'Compliance', Gauge],
]

const SELF_TABS = MANAGER_TABS.filter(([key]) => ['workers', 'certificates', 'authorizations', 'requests'].includes(key))
const inputClass = 'w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100'
const primaryButton = 'inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50'
const secondaryButton = 'inline-flex items-center justify-center gap-2 rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm font-semibold text-stone-700 transition hover:bg-stone-50 disabled:opacity-50'

function humanize(value) {
  return String(value ?? '—').replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function Status({ value }) {
  const normalized = String(value ?? '')
  const positive = ['active', 'approved', 'assigned', 'attended', 'compliant', 'competent', 'completed', 'eligible', 'passed', 'valid', 'verified'].includes(normalized)
  const negative = ['absent', 'expired', 'failed', 'missing', 'not_eligible', 'overdue', 'rejected', 'revoked', 'restricted', 'suspended'].includes(normalized)
  const tone = positive ? 'bg-emerald-100 text-emerald-800' : negative ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
  return <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{humanize(value)}</span>
}

function Panel({ title, description, children }) {
  return <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm"><h2 className="font-semibold text-stone-950">{title}</h2>{description ? <p className="mt-1 text-sm text-stone-500">{description}</p> : null}<div className="mt-4">{children}</div></section>
}

function Field({ label, children }) {
  return <label className="space-y-1 text-sm font-medium text-stone-700"><span>{label}</span>{children}</label>
}

function Empty({ message = 'No records match this view.' }) {
  return <div className="rounded-xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">{message}</div>
}

function Records({ columns, rows }) {
  if (!rows?.length) return <Empty />
  return (
    <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white shadow-sm">
      <table className="min-w-full divide-y divide-stone-200 text-sm">
        <thead className="bg-stone-50"><tr>{columns.map(([, label]) => <th key={label} className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</th>)}</tr></thead>
        <tbody className="divide-y divide-stone-100">{rows.map((row, index) => <tr key={row.id ?? index} className="hover:bg-emerald-50/40">{columns.map(([key, , type]) => {
          const value = row[key]
          return <td key={key} className="max-w-xs px-4 py-3 text-stone-700">{type === 'status' ? <Status value={value} /> : type === 'date' ? formatDate(value) : type === 'datetime' ? formatDateTime(value) : Array.isArray(value) ? value.join(', ') || '—' : String(value ?? '—')}</td>
        })}</tr>)}</tbody>
      </table>
    </div>
  )
}

function Metric({ label, value, warning = false }) {
  return <article className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"><p className="text-xs font-semibold uppercase tracking-wide text-stone-500">{label}</p><p className={`mt-2 text-2xl font-semibold ${warning ? 'text-amber-700' : 'text-stone-950'}`}>{value === null || value === undefined ? 'Unavailable' : formatNumber(value)}</p></article>
}

function asNumber(value) {
  return value === '' || value === null || value === undefined ? null : Number(value)
}

export function TrainingCompetencyPage() {
  const { token, user } = useAuth()
  const canViewAll = hasPermission(user, 'training.view_all')
  const canManage = hasPermission(user, 'training.manage')
  const canAssign = canManage || hasPermission(user, 'training.assign')
  const canAssess = canManage || hasPermission(user, 'training.assess')
  const canAuthorize = canManage || hasPermission(user, 'training.authorize')
  const canRequest = hasPermission(user, 'training.request')
  const canExport = hasPermission(user, 'training.export')
  const tabs = canViewAll ? MANAGER_TABS : SELF_TABS
  const [tab, setTab] = useState(canViewAll ? 'dashboard' : 'workers')
  const [data, setData] = useState(null)
  const [courses, setCourses] = useState([])
  const [competencies, setCompetencies] = useState([])
  const [workerId, setWorkerId] = useState(String(user?.id ?? ''))
  const [filters, setFilters] = useState({ site_id: user?.assigned_site_id ?? '', department_id: '' })
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [eligibility, setEligibility] = useState(null)
  const [eligibilityForm, setEligibilityForm] = useState({ worker_user_id: user?.id ?? '', task_activity: '', authorization_type: '', site_id: user?.assigned_site_id ?? '' })
  const [courseForm, setCourseForm] = useState({ name: '', code: '', category: 'safety training', training_type: 'safety_training', assessment_required: false, passing_score: '', certificate_required: false, default_validity_period_days: '', refresher_required: false, default_refresher_interval_days: '', practical_component_required: false })
  const [competencyForm, setCompetencyForm] = useState({ name: '', code: '', category: 'technical', validity_period_days: '', assessment_required: true, certificate_required: false, medical_prerequisite: false, ppe_prerequisite: false })
  const [requirementForm, setRequirementForm] = useState({ name: '', course_id: '', competency_id: '', authorization_type: '', level: 'mandatory', site_id: user?.assigned_site_id ?? '', department_id: '', role_name: '', job_title: '', task_activity: '', permit_type: '', equipment_category: '', medical_programme_codes: '', ppe_item_id: '', assessment_required: false, mandatory_certificate: false, is_critical: false })
  const [assignmentForm, setAssignmentForm] = useState({ course_id: '', assigned_user_id: user?.id ?? '', due_date: '', priority: 'normal', mandatory: true, reason: '', site_id: user?.assigned_site_id ?? '' })
  const [sessionForm, setSessionForm] = useState({ course_id: '', starts_at: '', ends_at: '', trainer_user_id: user?.id ?? '', provider: '', location: '', capacity: '', site_id: user?.assigned_site_id ?? '', delivery_mode: 'classroom', status: 'scheduled' })
  const [assessmentForm, setAssessmentForm] = useState({ course_id: '', competency_id: '', worker_user_id: '', assessment_type: 'theory', assessment_date: '', score: '', passed: true, competency_demonstrated: false, reassessment_required: false, reassessment_due_date: '' })
  const [certificateForm, setCertificateForm] = useState({ worker_user_id: '', course_id: '', competency_id: '', certificate_number: '', issue_date: '', expiry_date: '', provider: '', certificate_file_reference: '' })
  const [authorizationForm, setAuthorizationForm] = useState({ authorization_type: '', worker_user_id: '', competency_id: '', site_id: user?.assigned_site_id ?? '', task_activity: '', valid_from: '', valid_until: '', status: 'pending' })
  const [requestForm, setRequestForm] = useState({ course_id: '', requested_for_user_id: user?.id ?? '', reason: '', urgency: 'normal' })

  const queryFilters = useMemo(() => ({ site_id: filters.site_id || undefined, department_id: filters.department_id || undefined }), [filters])

  const loadLookups = useCallback(async () => {
    const [courseRows, competencyRows] = await Promise.all([
      apiClient.getTrainingCompetency(token, 'courses', { active: true }),
      apiClient.getTrainingCompetency(token, 'competencies', { active: true }),
    ])
    setCourses(courseRows); setCompetencies(competencyRows)
  }, [token])

  const load = useCallback(async () => {
    setLoading(true); setError('')
    try {
      let result
      if (tab === 'dashboard') result = await apiClient.getTrainingCompetency(token, 'dashboard', queryFilters)
      if (tab === 'workers') result = await apiClient.getTrainingCompetency(token, `workers/${Number(workerId || user.id)}/profile`)
      if (tab === 'courses') result = await apiClient.getTrainingCompetency(token, 'courses')
      if (tab === 'competencies') result = await apiClient.getTrainingCompetency(token, 'competencies')
      if (tab === 'requirements') result = await apiClient.getTrainingCompetency(token, 'requirements', queryFilters)
      if (tab === 'sessions') result = await apiClient.getTrainingCompetency(token, 'sessions', queryFilters)
      if (tab === 'assessments') result = await apiClient.getTrainingCompetency(token, 'assessments')
      if (tab === 'certificates') result = await apiClient.getTrainingCompetency(token, 'certificates', canViewAll ? {} : { worker_user_id: user.id })
      if (tab === 'authorizations') result = await apiClient.getTrainingCompetency(token, 'authorizations', canViewAll ? queryFilters : { worker_user_id: user.id })
      if (tab === 'matrix') result = await apiClient.getTrainingCompetency(token, 'competency-matrix', queryFilters)
      if (tab === 'requests') result = await apiClient.getTrainingCompetency(token, 'requests')
      if (tab === 'compliance') {
        const [summary, exceptions, forward] = await Promise.all([
          apiClient.getTrainingCompetency(token, 'dashboard', queryFilters),
          apiClient.getTrainingCompetency(token, 'management-exceptions', queryFilters),
          apiClient.getTrainingCompetency(token, 'forward-view', { ...queryFilters, days: 90 }),
        ])
        result = { summary, exceptions, forward }
      }
      setData(result)
    } catch (requestError) {
      setError(requestError?.message ?? String(requestError)); setData(null)
    } finally { setLoading(false) }
  }, [canViewAll, queryFilters, tab, token, user.id, workerId])

  useEffect(() => {
    // Each request owns its resulting lookup state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadLookups().catch((requestError) => setError(requestError?.message ?? String(requestError)))
  }, [loadLookups])
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    load()
  }, [load])

  async function command(path, body, reset) {
    setSaving(true); setError(''); setNotice('')
    try {
      await apiClient.trainingCompetencyCommand(token, path, body)
      setNotice('Training and competency record saved.')
      if (reset) reset()
      await Promise.all([load(), loadLookups()])
    } catch (requestError) { setError(requestError?.message ?? String(requestError)) }
    finally { setSaving(false) }
  }

  async function runEligibility(event) {
    event.preventDefault(); setSaving(true); setError('')
    try {
      setEligibility(await apiClient.trainingCompetencyCommand(token, 'eligibility', {
        worker_user_id: asNumber(eligibilityForm.worker_user_id),
        task_activity: eligibilityForm.task_activity || null,
        authorization_type: eligibilityForm.authorization_type || null,
        site_id: asNumber(eligibilityForm.site_id),
      }))
    } catch (requestError) { setError(requestError?.message ?? String(requestError)) }
    finally { setSaving(false) }
  }

  async function runReminders() {
    setSaving(true); setError('')
    try {
      const result = await apiClient.trainingCompetencyCommand(token, 'reminders/run', {})
      setNotice(`Reminder run completed: ${Object.values(result).reduce((sum, value) => sum + Number(value), 0)} created.`)
      await load()
    } catch (requestError) { setError(requestError?.message ?? String(requestError)) }
    finally { setSaving(false) }
  }

  async function download(type) {
    try {
      const result = await apiClient.downloadFile(token, `/training/exports/${type}`, { params: queryFilters, fallbackFilename: `${type}.csv` })
      const url = URL.createObjectURL(result.blob); const link = document.createElement('a'); link.href = url; link.download = result.filename; link.click(); URL.revokeObjectURL(url)
    } catch (requestError) { setError(requestError?.message ?? String(requestError)) }
  }

  function dashboardView(summary = data) {
    return <div className="space-y-5">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <Metric label="Assigned training" value={summary?.assigned_training} />
        <Metric label="Overdue training" value={summary?.overdue_training} warning />
        <Metric label="Competency gaps" value={summary?.competency_gaps} warning />
        <Metric label="Expiring competencies" value={summary?.expiring_competencies} />
        <Metric label="Eligibility failures" value={summary?.work_eligibility_failures} warning />
        <Metric label="Expired certificates" value={summary?.expired_certificates} warning />
        <Metric label="Authorization gaps" value={summary?.authorization_gaps} warning />
        <Metric label="Failed assessments" value={summary?.failed_assessments} warning />
        <Metric label="Refresher backlog" value={summary?.refresher_backlog} warning />
        <Metric label="Competency compliance" value={summary?.competency_compliance_rate} />
      </div>
      <Panel title="Work eligibility check" description="Transparent checks return a decision and the exact training, competency, certificate, medical, PPE, or authorization reasons.">
        <form onSubmit={runEligibility} className="grid gap-3 md:grid-cols-4">
          <Field label="Worker user ID"><input required type="number" className={inputClass} value={eligibilityForm.worker_user_id} onChange={(event) => setEligibilityForm({ ...eligibilityForm, worker_user_id: event.target.value })} /></Field>
          <Field label="Task / activity"><input className={inputClass} value={eligibilityForm.task_activity} onChange={(event) => setEligibilityForm({ ...eligibilityForm, task_activity: event.target.value })} placeholder="e.g. Confined Space Entry" /></Field>
          <Field label="Authorization type"><input className={inputClass} value={eligibilityForm.authorization_type} onChange={(event) => setEligibilityForm({ ...eligibilityForm, authorization_type: event.target.value })} /></Field>
          <button className={`${primaryButton} self-end`} disabled={saving}><ShieldCheck className="size-4" />Evaluate</button>
        </form>
        {eligibility ? <div className={`mt-4 rounded-lg border p-4 ${eligibility.eligible ? 'border-emerald-200 bg-emerald-50' : 'border-red-200 bg-red-50'}`}><div className="flex items-center gap-2"><Status value={eligibility.status} /><span className="text-xs text-stone-600">as at {formatDate(eligibility.as_of)}</span></div>{eligibility.reasons?.length ? <ul className="mt-3 list-disc space-y-1 pl-5 text-sm text-stone-700">{eligibility.reasons.map((reason, index) => <li key={`${reason.code}-${index}`}>{reason.message}</li>)}</ul> : <p className="mt-3 text-sm text-emerald-800">All configured prerequisites are current.</p>}</div> : null}
      </Panel>
    </div>
  }

  function workersView() {
    const profile = data
    return <div className="space-y-5">
      {canViewAll ? <Panel title="Worker training profile"><form className="flex max-w-lg gap-2" onSubmit={(event) => { event.preventDefault(); load() }}><input type="number" className={inputClass} value={workerId} onChange={(event) => setWorkerId(event.target.value)} /><button className={secondaryButton}><Search className="size-4" />Open profile</button></form></Panel> : null}
      {canAssign ? <Panel title="Assign training" description="Creates an explicit assignment and a linked historical TrainingRecord for internal workers."><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('assignments', { ...assignmentForm, course_id: Number(assignmentForm.course_id), assigned_user_id: Number(assignmentForm.assigned_user_id), site_id: asNumber(assignmentForm.site_id) }, () => setAssignmentForm({ ...assignmentForm, reason: '' })) }}>
        <Field label="Course"><select required className={inputClass} value={assignmentForm.course_id} onChange={(event) => setAssignmentForm({ ...assignmentForm, course_id: event.target.value })}><option value="">Select course</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
        <Field label="Worker user ID"><input required type="number" className={inputClass} value={assignmentForm.assigned_user_id} onChange={(event) => setAssignmentForm({ ...assignmentForm, assigned_user_id: event.target.value })} /></Field>
        <Field label="Due date"><input type="date" className={inputClass} value={assignmentForm.due_date} onChange={(event) => setAssignmentForm({ ...assignmentForm, due_date: event.target.value })} /></Field>
        <Field label="Reason"><input className={inputClass} value={assignmentForm.reason} onChange={(event) => setAssignmentForm({ ...assignmentForm, reason: event.target.value })} /></Field>
        <button className={`${primaryButton} md:col-span-4`} disabled={saving}>Assign training</button>
      </form></Panel> : null}
      {profile?.worker ? <Panel title={profile.worker.full_name} description={`${profile.worker.job_title || 'Job title not recorded'} · Site #${profile.worker.site_id ?? '—'}`}><div className="grid gap-3 sm:grid-cols-3"><Metric label="Competency gaps" value={profile.competency_gaps?.length} warning /><Metric label="Overdue training" value={profile.overdue_training?.length} warning /><Metric label="Authorizations" value={profile.authorizations?.length} /></div></Panel> : null}
      <Records columns={[["course_name", "Required course"], ["level", "Level"], ["status", "Status", "status"], ["reason", "Reason"]]} rows={profile?.required_courses ?? []} />
      <Records columns={[["course_id", "Course ID"], ["due_date", "Due", "date"], ["priority", "Priority"], ["status", "Status", "status"], ["source", "Source"]]} rows={profile?.assignments ?? []} />
    </div>
  }

  function coursesView() {
    return <div className="space-y-5">{canManage ? <Panel title="Add training course" description="Categories remain tenant-configurable; validity and prerequisites drive downstream compliance."><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('courses', { ...courseForm, passing_score: asNumber(courseForm.passing_score), default_validity_period_days: asNumber(courseForm.default_validity_period_days), default_refresher_interval_days: asNumber(courseForm.default_refresher_interval_days), medical_programme_codes: [], ppe_item_ids: [], reminder_windows: [90, 60, 30, 7], provider_required: false, medical_clearance_required: false, ppe_prerequisite_required: false }, () => setCourseForm({ ...courseForm, name: '', code: '' })) }}>
      <Field label="Course name"><input required className={inputClass} value={courseForm.name} onChange={(event) => setCourseForm({ ...courseForm, name: event.target.value })} /></Field><Field label="Code"><input required className={inputClass} value={courseForm.code} onChange={(event) => setCourseForm({ ...courseForm, code: event.target.value.toUpperCase() })} /></Field><Field label="Category"><input required className={inputClass} value={courseForm.category} onChange={(event) => setCourseForm({ ...courseForm, category: event.target.value })} /></Field><Field label="Training type"><select className={inputClass} value={courseForm.training_type} onChange={(event) => setCourseForm({ ...courseForm, training_type: event.target.value })}>{['induction', 'toolbox_talk', 'safety_training', 'equipment_training', 'emergency_response', 'compliance_training', 'other'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></Field>
      <Field label="Passing score"><input type="number" min="0" max="100" className={inputClass} value={courseForm.passing_score} onChange={(event) => setCourseForm({ ...courseForm, passing_score: event.target.value })} /></Field><Field label="Validity days"><input type="number" min="1" className={inputClass} value={courseForm.default_validity_period_days} onChange={(event) => setCourseForm({ ...courseForm, default_validity_period_days: event.target.value })} /></Field><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={courseForm.assessment_required} onChange={(event) => setCourseForm({ ...courseForm, assessment_required: event.target.checked })} />Assessment required</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={courseForm.certificate_required} onChange={(event) => setCourseForm({ ...courseForm, certificate_required: event.target.checked })} />Certificate required</label><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Create course</button>
    </form></Panel> : null}<Records columns={[["name", "Course"], ["code", "Code"], ["category", "Category"], ["training_type", "Type"], ["assessment_required", "Assessment"], ["certificate_required", "Certificate"], ["active", "Active"]]} rows={data ?? []} /></div>
  }

  function competenciesView() {
    return <div className="space-y-5">{canManage ? <Panel title="Add competency"><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('competencies', { name: competencyForm.name, code: competencyForm.code, category: competencyForm.category, evidence_requirements: [], assessment_rules: { required: competencyForm.assessment_required, certificate_required: competencyForm.certificate_required }, validity_period_days: asNumber(competencyForm.validity_period_days), renewal_rules: {}, medical_prerequisite: competencyForm.medical_prerequisite, medical_programme_codes: [], ppe_prerequisite: competencyForm.ppe_prerequisite, ppe_item_ids: [], supervisor_approval_required: true }, () => setCompetencyForm({ ...competencyForm, name: '', code: '' })) }}><Field label="Competency name"><input required className={inputClass} value={competencyForm.name} onChange={(event) => setCompetencyForm({ ...competencyForm, name: event.target.value })} /></Field><Field label="Code"><input required className={inputClass} value={competencyForm.code} onChange={(event) => setCompetencyForm({ ...competencyForm, code: event.target.value.toUpperCase() })} /></Field><Field label="Category"><input required className={inputClass} value={competencyForm.category} onChange={(event) => setCompetencyForm({ ...competencyForm, category: event.target.value })} /></Field><Field label="Validity days"><input type="number" min="1" className={inputClass} value={competencyForm.validity_period_days} onChange={(event) => setCompetencyForm({ ...competencyForm, validity_period_days: event.target.value })} /></Field><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={competencyForm.medical_prerequisite} onChange={(event) => setCompetencyForm({ ...competencyForm, medical_prerequisite: event.target.checked })} />Medical prerequisite</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={competencyForm.ppe_prerequisite} onChange={(event) => setCompetencyForm({ ...competencyForm, ppe_prerequisite: event.target.checked })} />PPE prerequisite</label><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Create competency</button></form></Panel> : null}<Records columns={[["name", "Competency"], ["code", "Code"], ["category", "Category"], ["validity_period_days", "Validity days"], ["medical_prerequisite", "Medical"], ["ppe_prerequisite", "PPE"], ["active", "Active"]]} rows={data ?? []} /></div>
  }

  function requirementsView() {
    return <div className="space-y-5">{canManage ? <Panel title="Add role / task requirement" description="Scope a mandatory or recommended course, competency, or authorization to a role, job, department, site, task, permit, or equipment category."><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('requirements', { ...requirementForm, course_id: asNumber(requirementForm.course_id), competency_id: asNumber(requirementForm.competency_id), site_id: asNumber(requirementForm.site_id), department_id: asNumber(requirementForm.department_id), ppe_item_id: asNumber(requirementForm.ppe_item_id), role_name: requirementForm.role_name || null, job_title: requirementForm.job_title || null, task_activity: requirementForm.task_activity || null, permit_type: requirementForm.permit_type || null, equipment_category: requirementForm.equipment_category || null, authorization_type: requirementForm.authorization_type || null, medical_programme_codes: requirementForm.medical_programme_codes.split(',').map((item) => item.trim()).filter(Boolean) }, () => setRequirementForm({ ...requirementForm, name: '' })) }}><Field label="Requirement name"><input required className={inputClass} value={requirementForm.name} onChange={(event) => setRequirementForm({ ...requirementForm, name: event.target.value })} /></Field><Field label="Course"><select className={inputClass} value={requirementForm.course_id} onChange={(event) => setRequirementForm({ ...requirementForm, course_id: event.target.value })}><option value="">None</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Competency"><select className={inputClass} value={requirementForm.competency_id} onChange={(event) => setRequirementForm({ ...requirementForm, competency_id: event.target.value })}><option value="">None</option>{competencies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Authorization type"><input className={inputClass} value={requirementForm.authorization_type} onChange={(event) => setRequirementForm({ ...requirementForm, authorization_type: event.target.value })} /></Field><Field label="Job title"><input className={inputClass} value={requirementForm.job_title} onChange={(event) => setRequirementForm({ ...requirementForm, job_title: event.target.value })} /></Field><Field label="Role"><input className={inputClass} value={requirementForm.role_name} onChange={(event) => setRequirementForm({ ...requirementForm, role_name: event.target.value })} /></Field><Field label="Task / activity"><input className={inputClass} value={requirementForm.task_activity} onChange={(event) => setRequirementForm({ ...requirementForm, task_activity: event.target.value })} /></Field><Field label="Medical programme codes"><input className={inputClass} value={requirementForm.medical_programme_codes} onChange={(event) => setRequirementForm({ ...requirementForm, medical_programme_codes: event.target.value })} placeholder="WORK_AT_HEIGHT, RESPIRATORY" /></Field><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Create requirement</button></form></Panel> : null}<Records columns={[["name", "Requirement"], ["course_id", "Course ID"], ["competency_id", "Competency ID"], ["authorization_type", "Authorization"], ["job_title", "Job title"], ["task_activity", "Task"], ["level", "Level", "status"]]} rows={data ?? []} /></div>
  }

  function sessionsView() {
    return <div className="space-y-5">{canManage ? <Panel title="Schedule training session"><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('sessions', { ...sessionForm, course_id: Number(sessionForm.course_id), starts_at: new Date(sessionForm.starts_at).toISOString(), ends_at: sessionForm.ends_at ? new Date(sessionForm.ends_at).toISOString() : null, trainer_user_id: asNumber(sessionForm.trainer_user_id), capacity: asNumber(sessionForm.capacity), site_id: asNumber(sessionForm.site_id) }, null) }}><Field label="Course"><select required className={inputClass} value={sessionForm.course_id} onChange={(event) => setSessionForm({ ...sessionForm, course_id: event.target.value })}><option value="">Select course</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Starts"><input required type="datetime-local" className={inputClass} value={sessionForm.starts_at} onChange={(event) => setSessionForm({ ...sessionForm, starts_at: event.target.value })} /></Field><Field label="Ends"><input type="datetime-local" className={inputClass} value={sessionForm.ends_at} onChange={(event) => setSessionForm({ ...sessionForm, ends_at: event.target.value })} /></Field><Field label="Location"><input className={inputClass} value={sessionForm.location} onChange={(event) => setSessionForm({ ...sessionForm, location: event.target.value })} /></Field><Field label="Provider"><input className={inputClass} value={sessionForm.provider} onChange={(event) => setSessionForm({ ...sessionForm, provider: event.target.value })} /></Field><Field label="Capacity"><input type="number" min="1" className={inputClass} value={sessionForm.capacity} onChange={(event) => setSessionForm({ ...sessionForm, capacity: event.target.value })} /></Field><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Schedule session</button></form></Panel> : null}<Records columns={[["course_id", "Course ID"], ["starts_at", "Starts", "datetime"], ["provider", "Provider"], ["location", "Location"], ["delivery_mode", "Delivery"], ["status", "Status", "status"]]} rows={data ?? []} /></div>
  }

  function assessmentsView() {
    return <div className="space-y-5">{canAssess ? <Panel title="Record assessment"><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('assessments', { ...assessmentForm, course_id: asNumber(assessmentForm.course_id), competency_id: asNumber(assessmentForm.competency_id), worker_user_id: Number(assessmentForm.worker_user_id), score: asNumber(assessmentForm.score), reassessment_due_date: assessmentForm.reassessment_due_date || null }, () => setAssessmentForm({ ...assessmentForm, score: '' })) }}><Field label="Worker user ID"><input required type="number" className={inputClass} value={assessmentForm.worker_user_id} onChange={(event) => setAssessmentForm({ ...assessmentForm, worker_user_id: event.target.value })} /></Field><Field label="Course"><select className={inputClass} value={assessmentForm.course_id} onChange={(event) => setAssessmentForm({ ...assessmentForm, course_id: event.target.value })}><option value="">None</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Competency"><select className={inputClass} value={assessmentForm.competency_id} onChange={(event) => setAssessmentForm({ ...assessmentForm, competency_id: event.target.value })}><option value="">None</option>{competencies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Assessment type"><select className={inputClass} value={assessmentForm.assessment_type} onChange={(event) => setAssessmentForm({ ...assessmentForm, assessment_type: event.target.value })}>{['theory', 'practical', 'observation', 'oral', 'competency_check'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></Field><Field label="Assessment date"><input required type="date" className={inputClass} value={assessmentForm.assessment_date} onChange={(event) => setAssessmentForm({ ...assessmentForm, assessment_date: event.target.value })} /></Field><Field label="Score"><input type="number" min="0" max="100" className={inputClass} value={assessmentForm.score} onChange={(event) => setAssessmentForm({ ...assessmentForm, score: event.target.value })} /></Field><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={assessmentForm.passed} onChange={(event) => setAssessmentForm({ ...assessmentForm, passed: event.target.checked })} />Passed</label><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={assessmentForm.competency_demonstrated} onChange={(event) => setAssessmentForm({ ...assessmentForm, competency_demonstrated: event.target.checked })} />Competency demonstrated</label><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Record assessment</button></form></Panel> : null}<Records columns={[["worker_user_id", "Worker"], ["course_id", "Course ID"], ["competency_id", "Competency ID"], ["assessment_type", "Type"], ["assessment_date", "Date", "date"], ["score", "Score"], ["passed", "Passed", "status"]]} rows={data ?? []} /></div>
  }

  function certificatesView() {
    return <div className="space-y-5">{canAssess ? <Panel title="Record certificate" description="Issued certificate facts are captured as a history snapshot; verification is a separate audited action."><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('certificates', { ...certificateForm, worker_user_id: Number(certificateForm.worker_user_id), course_id: asNumber(certificateForm.course_id), competency_id: asNumber(certificateForm.competency_id), expiry_date: certificateForm.expiry_date || null }, () => setCertificateForm({ ...certificateForm, certificate_number: '' })) }}><Field label="Worker user ID"><input required type="number" className={inputClass} value={certificateForm.worker_user_id} onChange={(event) => setCertificateForm({ ...certificateForm, worker_user_id: event.target.value })} /></Field><Field label="Course"><select className={inputClass} value={certificateForm.course_id} onChange={(event) => setCertificateForm({ ...certificateForm, course_id: event.target.value })}><option value="">None</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Competency"><select className={inputClass} value={certificateForm.competency_id} onChange={(event) => setCertificateForm({ ...certificateForm, competency_id: event.target.value })}><option value="">None</option>{competencies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Certificate number"><input required className={inputClass} value={certificateForm.certificate_number} onChange={(event) => setCertificateForm({ ...certificateForm, certificate_number: event.target.value })} /></Field><Field label="Issue date"><input required type="date" className={inputClass} value={certificateForm.issue_date} onChange={(event) => setCertificateForm({ ...certificateForm, issue_date: event.target.value })} /></Field><Field label="Expiry date"><input type="date" className={inputClass} value={certificateForm.expiry_date} onChange={(event) => setCertificateForm({ ...certificateForm, expiry_date: event.target.value })} /></Field><Field label="Provider"><input className={inputClass} value={certificateForm.provider} onChange={(event) => setCertificateForm({ ...certificateForm, provider: event.target.value })} /></Field><button className={`${primaryButton} self-end`} disabled={saving}>Record certificate</button></form></Panel> : null}<Records columns={[["certificate_number", "Certificate"], ["worker_user_id", "Worker"], ["provider", "Provider"], ["issue_date", "Issued", "date"], ["expiry_date", "Expires", "date"], ["verification_status", "Verification", "status"]]} rows={data ?? []} /></div>
  }

  function authorizationsView() {
    return <div className="space-y-5">{canAuthorize ? <Panel title="Create work authorization" description="Activation validates all configured prerequisites and stores the explainable decision snapshot."><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('authorizations', { ...authorizationForm, worker_user_id: Number(authorizationForm.worker_user_id), competency_id: asNumber(authorizationForm.competency_id), site_id: asNumber(authorizationForm.site_id), valid_until: authorizationForm.valid_until || null }, () => setAuthorizationForm({ ...authorizationForm, authorization_type: '' })) }}><Field label="Authorization type"><input required className={inputClass} value={authorizationForm.authorization_type} onChange={(event) => setAuthorizationForm({ ...authorizationForm, authorization_type: event.target.value })} /></Field><Field label="Worker user ID"><input required type="number" className={inputClass} value={authorizationForm.worker_user_id} onChange={(event) => setAuthorizationForm({ ...authorizationForm, worker_user_id: event.target.value })} /></Field><Field label="Competency"><select className={inputClass} value={authorizationForm.competency_id} onChange={(event) => setAuthorizationForm({ ...authorizationForm, competency_id: event.target.value })}><option value="">None</option>{competencies.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Task / activity"><input className={inputClass} value={authorizationForm.task_activity} onChange={(event) => setAuthorizationForm({ ...authorizationForm, task_activity: event.target.value })} /></Field><Field label="Valid from"><input required type="date" className={inputClass} value={authorizationForm.valid_from} onChange={(event) => setAuthorizationForm({ ...authorizationForm, valid_from: event.target.value })} /></Field><Field label="Valid until"><input type="date" className={inputClass} value={authorizationForm.valid_until} onChange={(event) => setAuthorizationForm({ ...authorizationForm, valid_until: event.target.value })} /></Field><Field label="Initial state"><select className={inputClass} value={authorizationForm.status} onChange={(event) => setAuthorizationForm({ ...authorizationForm, status: event.target.value })}><option value="pending">Pending</option><option value="active">Active</option></select></Field><button className={`${primaryButton} self-end`} disabled={saving}>Create authorization</button></form></Panel> : null}<Records columns={[["authorization_type", "Authorization"], ["worker_user_id", "Worker"], ["site_id", "Site"], ["valid_from", "Valid from", "date"], ["valid_until", "Valid until", "date"], ["status", "Status", "status"]]} rows={data ?? []} /></div>
  }

  function matrixView() {
    if (!data?.rows?.length) return <Empty message="No workers or applicable competencies match this scope." />
    return <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white shadow-sm"><table className="min-w-full divide-y divide-stone-200 text-sm"><thead className="bg-stone-50"><tr><th className="sticky left-0 bg-stone-50 px-4 py-3 text-left">Worker</th>{data.competencies.map((item) => <th key={item.id} className="min-w-40 px-4 py-3 text-left text-xs font-semibold text-stone-600">{item.name}</th>)}</tr></thead><tbody className="divide-y divide-stone-100">{data.rows.map((row) => <tr key={`${row.worker.subject_type || 'worker'}-${row.worker.id}`}><td className="sticky left-0 bg-white px-4 py-3"><p className="font-semibold text-stone-900">{row.worker.full_name}</p><p className="text-xs text-stone-500">{row.worker.job_title || 'Unassigned'}{row.worker.subject_type === 'contractor' ? ' · Contractor' : ''}</p></td>{row.cells.map((cell) => <td key={cell.competency_id} className="px-4 py-3"><Status value={cell.state} />{cell.reason ? <p className="mt-1 max-w-48 text-xs text-stone-500">{cell.reason}</p> : null}</td>)}</tr>)}</tbody></table></div>
  }

  function requestsView() {
    return <div className="space-y-5">{canRequest ? <Panel title="Request training"><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); command('requests', { ...requestForm, course_id: Number(requestForm.course_id), requested_for_user_id: Number(requestForm.requested_for_user_id) }, () => setRequestForm({ ...requestForm, reason: '' })) }}><Field label="Course"><select required className={inputClass} value={requestForm.course_id} onChange={(event) => setRequestForm({ ...requestForm, course_id: event.target.value })}><option value="">Select course</option>{courses.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field><Field label="Requested for user ID"><input required type="number" className={inputClass} value={requestForm.requested_for_user_id} onChange={(event) => setRequestForm({ ...requestForm, requested_for_user_id: event.target.value })} /></Field><Field label="Reason"><input required className={inputClass} value={requestForm.reason} onChange={(event) => setRequestForm({ ...requestForm, reason: event.target.value })} /></Field><Field label="Urgency"><select className={inputClass} value={requestForm.urgency} onChange={(event) => setRequestForm({ ...requestForm, urgency: event.target.value })}>{['low', 'normal', 'high', 'critical'].map((value) => <option key={value} value={value}>{humanize(value)}</option>)}</select></Field><button className={`${primaryButton} md:col-span-4`} disabled={saving}>Submit request</button></form></Panel> : null}<Records columns={[["course_id", "Course ID"], ["requester_user_id", "Requester"], ["requested_for_user_id", "Requested for"], ["urgency", "Urgency"], ["status", "Status", "status"], ["decision_notes", "Decision"]]} rows={data ?? []} /></div>
  }

  function complianceView() {
    return <div className="space-y-5">{dashboardView(data?.summary)}<div className="flex flex-wrap gap-2">{canExport ? ['training-register', 'competency-matrix', 'certificate-register', 'authorization-register', 'expiry-schedule', 'work-eligibility'].map((type) => <button key={type} className={secondaryButton} onClick={() => download(type)}><Download className="size-4" />{humanize(type)}</button>) : null}</div><Panel title="90-day forward view"><Records columns={[["type", "Type"], ["label", "Item"], ["worker_user_id", "Worker"], ["date", "Due / expiry", "date"]]} rows={data?.forward ?? []} /></Panel><Panel title="Management exceptions" description="Deterministic attention items—no AI score."><Records columns={[["type", "Exception"], ["severity", "Severity", "status"], ["worker_user_id", "Worker"], ["reason", "Reason"]]} rows={data?.exceptions ?? []} /></Panel></div>
  }

  if (loading) return <LoadingState title="Loading Training & Competency" message="Applying tenant, site, department, and permission scope." />

  let content
  if (tab === 'dashboard') content = dashboardView()
  if (tab === 'workers') content = workersView()
  if (tab === 'courses') content = coursesView()
  if (tab === 'competencies') content = competenciesView()
  if (tab === 'requirements') content = requirementsView()
  if (tab === 'sessions') content = sessionsView()
  if (tab === 'assessments') content = assessmentsView()
  if (tab === 'certificates') content = certificatesView()
  if (tab === 'authorizations') content = authorizationsView()
  if (tab === 'matrix') content = matrixView()
  if (tab === 'requests') content = requestsView()
  if (tab === 'compliance') content = complianceView()

  return <div className="space-y-6">
    <PageHeader eyebrow="Phase 2D" title="Training & Competency" description="Role and task requirements through assignment, assessment, competency, certification, authorization, expiry, and explainable work eligibility." actions={<>{canManage ? <button className={secondaryButton} onClick={runReminders} disabled={saving}><BellRing className="size-4" />Run reminders</button> : null}{canExport ? <button className={primaryButton} onClick={() => download('training-register')}><Download className="size-4" />Training register</button> : null}</>} />
    <div className="rounded-xl border border-sky-200 bg-sky-50 p-4 text-sm text-sky-900"><div className="flex gap-3"><ShieldAlert className="mt-0.5 size-5 shrink-0" /><p><strong>Eligibility is explainable:</strong> supervisors see operational clearance outcomes and prerequisite failures. Medical diagnoses and clinical detail are never exposed here.</p></div></div>
    {notice ? <div className="flex items-center gap-2 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm font-medium text-emerald-800"><CheckCircle2 className="size-4" />{notice}</div> : null}
    {error ? <ErrorState message={error} onRetry={load} /> : null}
    {canViewAll ? <div className="grid gap-3 rounded-xl border border-stone-200 bg-white p-4 sm:grid-cols-3"><Field label="Site ID"><input type="number" className={inputClass} value={filters.site_id} onChange={(event) => setFilters({ ...filters, site_id: event.target.value })} /></Field><Field label="Department ID"><input type="number" className={inputClass} value={filters.department_id} onChange={(event) => setFilters({ ...filters, department_id: event.target.value })} /></Field><button className={`${secondaryButton} self-end`} onClick={load}><Search className="size-4" />Apply scope</button></div> : null}
    <div className="flex gap-2 overflow-x-auto border-b border-stone-200 pb-2">{tabs.map(([key, label, Icon]) => <button key={key} onClick={() => setTab(key)} className={`inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold transition ${tab === key ? 'bg-emerald-100 text-emerald-900' : 'text-stone-600 hover:bg-stone-100'}`}><Icon className="size-4" />{label}</button>)}</div>
    {content}
  </div>
}
