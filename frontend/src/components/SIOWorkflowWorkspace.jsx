import { CheckCircle2, ClipboardList, MessageSquarePlus, RotateCcw, ShieldCheck, UserRoundCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'
import { hasPermission } from '../lib/rbac.js'
import { formatDateTime } from '../lib/formatters.js'

const inputClass = 'w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm outline-none focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100'

function Section({ title, description, children }) {
  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <h2 className="text-lg font-semibold text-stone-950">{title}</h2>
      {description ? <p className="mt-1 text-sm text-stone-600">{description}</p> : null}
      <div className="mt-4">{children}</div>
    </section>
  )
}

export function SIOWorkflowWorkspace({ item, token, user, onUpdated }) {
  const [comments, setComments] = useState([])
  const [activity, setActivity] = useState([])
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [comment, setComment] = useState('')
  const [reason, setReason] = useState('')
  const [closureNotes, setClosureNotes] = useState('')
  const [verificationNotes, setVerificationNotes] = useState('')
  const [assignment, setAssignment] = useState({ responsible_user_id: '', responsible_department_id: '', due_date: '' })
  const [investigation, setInvestigation] = useState({})
  const [busy, setBusy] = useState('')
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  const canManage = hasPermission(user, 'sios.edit')
  const canVerify = hasPermission(user, 'sios.verify')
  const isResponsible = Number(item.responsible_user_id) === Number(user?.id)
  const canWork = canManage || isResponsible

  useEffect(() => {
    setInvestigation({
      investigation_required: Boolean(item.investigation_required),
      investigator_user_id: item.investigator_user_id ? String(item.investigator_user_id) : '',
      immediate_cause: item.immediate_cause ?? '',
      underlying_cause: item.underlying_cause ?? '',
      root_cause: item.root_cause ?? '',
      contributing_factors: (item.contributing_factors ?? []).join('\n'),
      investigation_summary: item.investigation_summary ?? '',
      lessons_learned: item.lessons_learned ?? '',
    })
  }, [item])

  async function refreshTimeline() {
    const [nextComments, nextActivity] = await Promise.all([
      apiClient.getSioComments(token, item.id),
      apiClient.getSioActivity(token, item.id),
    ])
    setComments(nextComments)
    setActivity(nextActivity)
  }

  useEffect(() => {
    let ignore = false
    Promise.all([
      apiClient.getSioComments(token, item.id),
      apiClient.getSioActivity(token, item.id),
    ]).then(([nextComments, nextActivity]) => {
      if (!ignore) {
        setComments(nextComments)
        setActivity(nextActivity)
      }
    }).catch((loadError) => { if (!ignore) setError(loadError.message) })
    if (canManage) {
      Promise.all([
        apiClient.getCollection(token, '/users?limit=500'),
        apiClient.getCollection(token, '/departments?limit=500'),
      ]).then(([nextUsers, nextDepartments]) => {
        if (!ignore) {
          setUsers(nextUsers)
          setDepartments(nextDepartments)
        }
      }).catch(() => {})
    }
    return () => { ignore = true }
  }, [canManage, item.id, token])

  async function perform(label, action) {
    setBusy(label)
    setError('')
    setNotice('')
    try {
      const updated = await action()
      if (updated?.id) onUpdated(updated)
      await refreshTimeline()
      setNotice(`${label} completed.`)
      setReason('')
    } catch (requestError) {
      setError(requestError.message ?? `Unable to complete ${label.toLowerCase()}.`)
    } finally {
      setBusy('')
    }
  }

  async function addComment(event) {
    event.preventDefault()
    if (!comment.trim()) return
    await perform('Comment', async () => {
      await apiClient.addSioComment(token, item.id, comment.trim())
      setComment('')
      return null
    })
  }

  return (
    <div className="space-y-4">
      {error ? <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div> : null}
      {notice ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div> : null}

      <Section title="Responsibility" description="Assignment decisions and ownership are recorded in the immutable activity history.">
        <div className="grid gap-4 lg:grid-cols-3">
          <div className="rounded-lg bg-stone-50 p-4 text-sm">
            <p><strong>Status:</strong> {item.assignment_status?.replaceAll('_', ' ')}</p>
            <p className="mt-2"><strong>Responsible user:</strong> {item.responsible_person_name || (item.responsible_user_id ? `User #${item.responsible_user_id}` : 'Unassigned')}</p>
            <p className="mt-2"><strong>Due:</strong> {item.due_date || 'Not set'}</p>
          </div>
          {canManage ? (
            <div className="grid gap-3 lg:col-span-2 sm:grid-cols-3">
              <select value={assignment.responsible_user_id} onChange={(event) => setAssignment((current) => ({ ...current, responsible_user_id: event.target.value }))} className={inputClass}>
                <option value="">Responsible user</option>
                {users.map((entry) => <option key={entry.id} value={entry.id}>{entry.full_name}</option>)}
              </select>
              <select value={assignment.responsible_department_id} onChange={(event) => setAssignment((current) => ({ ...current, responsible_department_id: event.target.value }))} className={inputClass}>
                <option value="">Responsible department</option>
                {departments.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}
              </select>
              <input type="date" value={assignment.due_date} onChange={(event) => setAssignment((current) => ({ ...current, due_date: event.target.value }))} className={inputClass} />
              <button type="button" disabled={Boolean(busy)} onClick={() => perform('Assignment', () => apiClient.sioAction(token, item.id, 'assign', {
                responsible_user_id: assignment.responsible_user_id ? Number(assignment.responsible_user_id) : null,
                responsible_department_id: assignment.responsible_department_id ? Number(assignment.responsible_department_id) : null,
                due_date: assignment.due_date || null,
              }))} className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><UserRoundCheck className="size-4" />Assign</button>
            </div>
          ) : null}
        </div>
        {isResponsible && ['assigned', 'reassigned'].includes(item.assignment_status) ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <button type="button" onClick={() => perform('Assignment acceptance', () => apiClient.sioAction(token, item.id, 'assignment/accept'))} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white">Accept</button>
            <input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required decline reason" className={`${inputClass} max-w-md`} />
            <button type="button" onClick={() => perform('Assignment decline', () => apiClient.sioAction(token, item.id, 'assignment/decline', { reason }))} className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700">Decline</button>
          </div>
        ) : null}
      </Section>

      {canWork ? (
        <Section title="Workflow" description="Progression follows explicit validated transitions.">
          <div className="flex flex-wrap gap-2">
            {['in_progress', 'pending_verification', 'complete'].map((nextStatus) => (
              <button key={nextStatus} type="button" disabled={Boolean(busy)} onClick={() => perform(`Status: ${nextStatus.replaceAll('_', ' ')}`, () => apiClient.sioAction(token, item.id, 'transition', { status: nextStatus }))} className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold text-stone-700 hover:bg-stone-50">{nextStatus.replaceAll('_', ' ')}</button>
            ))}
          </div>
        </Section>
      ) : null}

      <Section title="Investigation" description="Structured analysis for this observation; it does not replace an incident investigation.">
        <div className="grid gap-3 lg:grid-cols-2">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={Boolean(investigation.investigation_required)} onChange={(event) => setInvestigation((current) => ({ ...current, investigation_required: event.target.checked }))} />Investigation required</label>
          {canManage ? <select value={investigation.investigator_user_id ?? ''} onChange={(event) => setInvestigation((current) => ({ ...current, investigator_user_id: event.target.value }))} className={inputClass}><option value="">Investigator</option>{users.map((entry) => <option key={entry.id} value={entry.id}>{entry.full_name}</option>)}</select> : null}
          {['immediate_cause', 'underlying_cause', 'root_cause', 'contributing_factors', 'investigation_summary', 'lessons_learned'].map((field) => (
            <label key={field} className="text-sm font-medium capitalize">{field.replaceAll('_', ' ')}<textarea rows={3} value={investigation[field] ?? ''} onChange={(event) => setInvestigation((current) => ({ ...current, [field]: event.target.value }))} className={`mt-1 ${inputClass}`} /></label>
          ))}
        </div>
        {(canManage || Number(item.investigator_user_id) === Number(user?.id)) ? (
          <button type="button" disabled={Boolean(busy)} onClick={() => perform('Investigation update', () => apiClient.updateSioInvestigation(token, item.id, {
            ...investigation,
            investigator_user_id: investigation.investigator_user_id ? Number(investigation.investigator_user_id) : null,
            contributing_factors: (investigation.contributing_factors ?? '').split('\n').map((value) => value.trim()).filter(Boolean),
          }))} className="mt-4 inline-flex items-center gap-2 rounded-md bg-stone-900 px-4 py-2 text-sm font-semibold text-white"><ClipboardList className="size-4" />Save investigation</button>
        ) : null}
      </Section>

      <Section title="Comments" description="Comments are immutable and become activity timeline entries.">
        <form onSubmit={addComment} className="flex gap-2"><textarea rows={2} value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add an operational comment" className={inputClass} /><button disabled={Boolean(busy) || !comment.trim()} className="inline-flex items-center gap-2 self-end rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"><MessageSquarePlus className="size-4" />Add</button></form>
        <div className="mt-4 space-y-2">{comments.map((entry) => <div key={entry.id} className="rounded-lg bg-stone-50 p-3 text-sm"><p>{entry.body}</p><p className="mt-1 text-xs text-stone-500">{entry.author_name || `User #${entry.author_user_id}`} · {formatDateTime(entry.created_at)}</p></div>)}</div>
      </Section>

      <Section title="Closure / Verification" description="High and urgent SIOs cannot be closed directly; evidence can be uploaded in the attachment section.">
        {canWork && !['closed', 'no_action_required'].includes(item.status) ? (
          <div className="flex flex-wrap gap-2"><input value={closureNotes} onChange={(event) => setClosureNotes(event.target.value)} placeholder="Closure request notes" className={`${inputClass} max-w-xl`} /><button type="button" disabled={!closureNotes.trim()} onClick={() => perform('Closure request', () => apiClient.sioAction(token, item.id, 'request-closure', { notes: closureNotes }))} className="rounded-md bg-amber-600 px-4 py-2 text-sm font-semibold text-white">Request closure</button></div>
        ) : null}
        {canVerify && item.status === 'pending_verification' ? (
          <div className="mt-4 flex flex-wrap gap-2"><input value={verificationNotes} onChange={(event) => setVerificationNotes(event.target.value)} placeholder="Verification notes" className={`${inputClass} max-w-xl`} /><button type="button" disabled={!verificationNotes.trim()} onClick={() => perform('Verification approval', () => apiClient.sioAction(token, item.id, 'verify', { approved: true, notes: verificationNotes }))} className="inline-flex items-center gap-2 rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white"><ShieldCheck className="size-4" />Verify & close</button><button type="button" disabled={!verificationNotes.trim()} onClick={() => perform('Verification rejection', () => apiClient.sioAction(token, item.id, 'verify', { approved: false, notes: verificationNotes }))} className="rounded-md border border-rose-300 bg-white px-4 py-2 text-sm font-semibold text-rose-700">Reject</button></div>
        ) : null}
        {canVerify ? (
          <div className="mt-4 flex flex-wrap gap-2"><input value={reason} onChange={(event) => setReason(event.target.value)} placeholder="Required reason" className={`${inputClass} max-w-xl`} />{['closed', 'complete', 'no_action_required'].includes(item.status) ? <button type="button" disabled={!reason.trim()} onClick={() => perform('Reopen', () => apiClient.sioAction(token, item.id, 'reopen', { reason }))} className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold"><RotateCcw className="size-4" />Reopen</button> : <button type="button" disabled={!reason.trim()} onClick={() => perform('No action required', () => apiClient.sioAction(token, item.id, 'no-action-required', { reason }))} className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-semibold"><CheckCircle2 className="size-4" />No action required</button>}</div>
        ) : null}
      </Section>

      <Section title="Activity Timeline" description="Tenant-safe audit-style history of operational events.">
        <ol className="space-y-3 border-l border-stone-200 pl-5">{[...activity].reverse().map((entry) => <li key={entry.id} className="relative"><span className="absolute -left-[25px] top-1.5 size-2.5 rounded-full bg-emerald-500" /><p className="text-sm font-semibold capitalize text-stone-900">{entry.event_type.replaceAll('_', ' ')}</p><p className="mt-1 text-sm text-stone-700">{entry.message}</p><p className="mt-1 text-xs text-stone-500">{entry.actor_name || (entry.actor_user_id ? `User #${entry.actor_user_id}` : 'System')} · {formatDateTime(entry.created_at)}</p></li>)}</ol>
      </Section>
    </div>
  )
}
