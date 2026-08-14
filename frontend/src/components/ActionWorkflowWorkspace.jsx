import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'
import { Badge } from './Badge.jsx'
import { hasPermission } from '../lib/rbac.js'

const TERMINAL = ['closed', 'cancelled']

function Section({ title, description, children }) {
  return <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm"><div><h3 className="text-lg font-semibold text-stone-950">{title}</h3>{description ? <p className="mt-1 text-sm text-stone-500">{description}</p> : null}</div><div className="mt-4">{children}</div></section>
}

function Message({ value, tone = 'error' }) {
  if (!value) return null
  return <div className={`rounded-lg border px-4 py-3 text-sm ${tone === 'error' ? 'border-rose-200 bg-rose-50 text-rose-800' : 'border-emerald-200 bg-emerald-50 text-emerald-800'}`}>{value}</div>
}

function label(value) {
  return String(value ?? '').replaceAll('_', ' ')
}

export function ActionWorkflowWorkspace({ item, token, user, onUpdated }) {
  const [comments, setComments] = useState([])
  const [activity, setActivity] = useState([])
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [isWorking, setIsWorking] = useState(false)
  const [reason, setReason] = useState('')
  const [comment, setComment] = useState('')
  const [progress, setProgress] = useState({ percent: String(item.progress_percent ?? 0), notes: item.progress_notes ?? '' })
  const [assignment, setAssignment] = useState({ owner: String(item.owner_user_id ?? ''), department: String(item.responsible_department_id ?? ''), verifier: String(item.verifier_user_id ?? ''), dueDate: '', note: '' })
  const [task, setTask] = useState({ title: '', description: '', owner: '', dueDate: '', required: true })
  const [completionNotes, setCompletionNotes] = useState(item.completion_notes ?? '')
  const [verification, setVerification] = useState({ approved: true, notes: '' })
  const [extension, setExtension] = useState({ requestedDueDate: '', reason: '' })

  const isOwner = item.owner_user_id === user?.id || item.assigned_to_user_id === user?.id
  const canManage = hasPermission(user, 'corrective_actions.edit') || (
    isOwner && hasPermission(user, 'corrective_actions.self_update')
  )
  const canAssign = hasPermission(user, 'corrective_actions.edit')
  const canVerify = hasPermission(user, 'corrective_actions.verify')
  const canManageExtensions = hasPermission(user, 'corrective_actions.manage_extensions')

  const loadRelated = useCallback(async () => {
    const [commentsResult, activityResult] = await Promise.all([
      apiClient.getActionComments(token, item.id),
      apiClient.getActionActivity(token, item.id),
    ])
    setComments(commentsResult)
    setActivity(activityResult)
  }, [item.id, token])

  useEffect(() => {
    let ignore = false
    loadRelated().catch((requestError) => { if (!ignore) setError(requestError.message) })
    Promise.allSettled([
      apiClient.getCollection(token, '/users?limit=500'),
      apiClient.getCollection(token, '/departments?limit=500'),
    ]).then(([usersResult, departmentsResult]) => {
      if (ignore) return
      if (usersResult.status === 'fulfilled') setUsers(usersResult.value)
      if (departmentsResult.status === 'fulfilled') setDepartments(departmentsResult.value)
    })
    return () => { ignore = true }
  }, [loadRelated, token])

  useEffect(() => {
    setProgress({ percent: String(item.progress_percent ?? 0), notes: item.progress_notes ?? '' })
    setCompletionNotes(item.completion_notes ?? '')
    setAssignment({ owner: String(item.owner_user_id ?? ''), department: String(item.responsible_department_id ?? ''), verifier: String(item.verifier_user_id ?? ''), dueDate: '', note: '' })
  }, [item])

  async function refresh() {
    const updated = await apiClient.getDetail(token, `/corrective-actions/${item.id}`)
    onUpdated(updated)
    await loadRelated()
  }

  async function run(work, success) {
    setIsWorking(true)
    setError('')
    setNotice('')
    try {
      const updated = await work()
      if (updated?.action_reference) onUpdated(updated)
      else await refresh()
      await loadRelated()
      setNotice(success)
    } catch (requestError) {
      setError(requestError.message ?? 'The action operation failed.')
    } finally {
      setIsWorking(false)
    }
  }

  async function transition(target, transitionReason = null) {
    await run(() => apiClient.actionCommand(token, item.id, 'transition', { lifecycle_status: target, reason: transitionReason }), `Action moved to ${label(target)}.`)
  }

  return (
    <div className="space-y-5">
      <Message value={error} /><Message value={notice} tone="success" />

      <Section title="Operational controls" description="Lifecycle state is explicit; overdue is derived from the approved current due date.">
        <div className="flex flex-wrap items-center gap-2">
          <Badge value={item.lifecycle_status} />
          {item.is_overdue ? <span className="rounded-full bg-rose-100 px-3 py-1 text-xs font-semibold text-rose-800">{item.days_overdue} days overdue</span> : null}
          {item.lifecycle_status === 'draft' && canManage ? <button disabled={isWorking} onClick={() => transition('open')} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Open</button> : null}
          {item.lifecycle_status === 'assigned' && isOwner ? <><button disabled={isWorking} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'assignment/accept'), 'Assignment accepted.')} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Accept</button><button disabled={isWorking || !reason.trim()} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'assignment/decline', { reason }), 'Assignment declined.')} className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700">Decline</button></> : null}
          {['open', 'assigned', 'accepted', 'reopened'].includes(item.lifecycle_status) && canManage ? <button disabled={isWorking} onClick={() => transition('in_progress')} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Start</button> : null}
          {['open', 'assigned', 'accepted', 'in_progress', 'reopened', 'pending_verification'].includes(item.lifecycle_status) && canManage ? <button disabled={isWorking} onClick={() => transition('on_hold', reason.trim() || null)} className="rounded-md border border-stone-300 px-3 py-2 text-sm font-semibold">Hold</button> : null}
          {item.lifecycle_status === 'on_hold' && canManage ? <button disabled={isWorking} onClick={() => transition('in_progress', reason.trim() || null)} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white">Resume</button> : null}
          {!TERMINAL.includes(item.lifecycle_status) && canManage ? <button disabled={isWorking || !reason.trim()} onClick={() => transition('cancelled', reason)} className="rounded-md border border-rose-300 px-3 py-2 text-sm font-semibold text-rose-700">Cancel</button> : null}
          {item.lifecycle_status === 'closed' && canVerify ? <button disabled={isWorking || !reason.trim()} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'reopen', { reason }), 'Action reopened.')} className="rounded-md border border-amber-300 bg-amber-50 px-3 py-2 text-sm font-semibold text-amber-900">Reopen</button> : null}
        </div>
        <label className="mt-3 block text-sm font-medium text-stone-700">Reason for decline, hold, cancel, or reopen<input value={reason} onChange={(event) => setReason(event.target.value)} className="mt-1 block w-full rounded-md border border-stone-300 px-3 py-2" /></label>
      </Section>

      {canAssign ? <Section title="Ownership and assignment" description="One primary owner remains accountable; reassignment is retained in history.">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <select aria-label="Accountable owner" value={assignment.owner} onChange={(event) => setAssignment((current) => ({ ...current, owner: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm"><option value="">Select owner</option>{users.map((entry) => <option key={entry.id} value={entry.id}>{entry.full_name}</option>)}</select>
          <select aria-label="Responsible department" value={assignment.department} onChange={(event) => setAssignment((current) => ({ ...current, department: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm"><option value="">Responsible department</option>{departments.map((entry) => <option key={entry.id} value={entry.id}>{entry.name}</option>)}</select>
          <select aria-label="Verifier" value={assignment.verifier} onChange={(event) => setAssignment((current) => ({ ...current, verifier: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm"><option value="">Verifier (optional)</option>{users.map((entry) => <option key={entry.id} value={entry.id}>{entry.full_name}</option>)}</select>
          <input aria-label="Assignment due date" type="date" value={assignment.dueDate} onChange={(event) => setAssignment((current) => ({ ...current, dueDate: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm" />
          <button disabled={isWorking || !assignment.owner} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'assign', { owner_user_id: Number(assignment.owner), responsible_department_id: assignment.department ? Number(assignment.department) : null, verifier_user_id: assignment.verifier ? Number(assignment.verifier) : null, current_due_date: assignment.dueDate || null, note: assignment.note || null }), item.owner_user_id ? 'Action reassigned.' : 'Action assigned.')} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">{item.owner_user_id ? 'Reassign' : 'Assign'}</button>
        </div>
        <input value={assignment.note} onChange={(event) => setAssignment((current) => ({ ...current, note: event.target.value }))} placeholder="Assignment note" className="mt-3 block w-full rounded-md border border-stone-300 px-3 py-2 text-sm" />
        {item.assignment_history?.length ? <div className="mt-4 overflow-x-auto"><table className="min-w-full text-left text-sm"><thead><tr className="text-stone-500"><th className="py-2">Type</th><th>Owner ID</th><th>Assigned by</th><th>When</th><th>Reason</th></tr></thead><tbody>{item.assignment_history.map((entry) => <tr key={entry.id} className="border-t border-stone-100"><td className="py-2">{label(entry.assignment_type)}</td><td>{entry.owner_user_id ?? '—'}</td><td>{entry.assigned_by_user_id ?? '—'}</td><td>{new Date(entry.created_at).toLocaleString()}</td><td>{entry.reason ?? '—'}</td></tr>)}</tbody></table></div> : null}
      </Section> : null}

      <Section title="Tasks and progress" description="Required incomplete tasks block completion; task status automatically contributes to parent progress.">
        <div className="space-y-3">
          {(item.tasks ?? []).map((entry) => {
            const canUpdate = canManage || entry.owner_user_id === user?.id
            return <div key={entry.id} className="flex flex-col gap-2 rounded-lg border border-stone-200 p-3 md:flex-row md:items-center"><div className="min-w-0 flex-1"><p className="font-semibold text-stone-900">{entry.title}{entry.is_required ? <span className="ml-2 text-xs text-rose-700">Required</span> : null}</p><p className="text-sm text-stone-500">{entry.owner_name ?? 'Unassigned'} · due {entry.due_date ?? 'not set'}</p></div><select disabled={!canUpdate || isWorking} value={entry.status} onChange={(event) => run(() => apiClient.updateActionTask(token, item.id, entry.id, { status: event.target.value }), `Task moved to ${label(event.target.value)}.`)} className="rounded-md border border-stone-300 px-3 py-2 text-sm">{['open', 'in_progress', 'completed', 'cancelled'].map((value) => <option key={value} value={value}>{label(value)}</option>)}</select></div>
          })}
          {!item.tasks?.length ? <p className="text-sm text-stone-500">No child tasks have been added.</p> : null}
        </div>
        {canManage && !TERMINAL.includes(item.lifecycle_status) ? <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5"><input value={task.title} onChange={(event) => setTask((current) => ({ ...current, title: event.target.value }))} placeholder="Task title" className="rounded-md border border-stone-300 px-3 py-2 text-sm" /><input value={task.description} onChange={(event) => setTask((current) => ({ ...current, description: event.target.value }))} placeholder="Description" className="rounded-md border border-stone-300 px-3 py-2 text-sm" /><select value={task.owner} onChange={(event) => setTask((current) => ({ ...current, owner: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm"><option value="">Task owner</option>{users.map((entry) => <option key={entry.id} value={entry.id}>{entry.full_name}</option>)}</select><input type="date" value={task.dueDate} onChange={(event) => setTask((current) => ({ ...current, dueDate: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm" /><button disabled={isWorking || !task.title.trim()} onClick={() => run(async () => { await apiClient.createActionTask(token, item.id, { title: task.title, description: task.description || null, owner_user_id: task.owner ? Number(task.owner) : null, due_date: task.dueDate || null, is_required: task.required, status: 'open', notes: null }); setTask({ title: '', description: '', owner: '', dueDate: '', required: true }) }, 'Task added.')} className="rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Add task</button><label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={task.required} onChange={(event) => setTask((current) => ({ ...current, required: event.target.checked }))} />Required for completion</label></div> : null}
        {canManage && !item.tasks?.length && !TERMINAL.includes(item.lifecycle_status) ? <div className="mt-5 grid gap-3 md:grid-cols-[140px_minmax(0,1fr)_auto]"><input type="number" min="0" max="100" value={progress.percent} onChange={(event) => setProgress((current) => ({ ...current, percent: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2" /><input value={progress.notes} onChange={(event) => setProgress((current) => ({ ...current, notes: event.target.value }))} placeholder="Progress notes" className="rounded-md border border-stone-300 px-3 py-2" /><button disabled={isWorking} onClick={() => run(() => apiClient.updateActionProgress(token, item.id, { progress_percent: Number(progress.percent), progress_notes: progress.notes || null }), 'Progress updated; closure remains controlled.')} className="rounded-md border border-emerald-300 px-4 py-2 text-sm font-semibold text-emerald-800">Update progress</button></div> : <p className="mt-4 text-sm font-medium text-stone-700">Parent progress: {item.progress_percent}%</p>}
      </Section>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Completion and verification" description="Completion does not close an action until organization verification rules are satisfied.">
          {['in_progress', 'reopened'].includes(item.lifecycle_status) && canManage ? <div className="space-y-3"><textarea value={completionNotes} onChange={(event) => setCompletionNotes(event.target.value)} rows={3} placeholder="Completion notes and how acceptance criteria were met" className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm" /><button disabled={isWorking || !completionNotes.trim()} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'request-completion', { completion_notes: completionNotes }), 'Completion requested.')} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Request completion</button></div> : null}
          {['completion_requested', 'pending_verification'].includes(item.lifecycle_status) && canVerify ? <div className="space-y-3"><textarea value={verification.notes} onChange={(event) => setVerification((current) => ({ ...current, notes: event.target.value }))} rows={3} placeholder="Verification findings (required)" className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm" /><div className="flex gap-2"><button disabled={isWorking || !verification.notes.trim()} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'verify', { approved: true, notes: verification.notes }), 'Action verified and closed.')} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Approve</button><button disabled={isWorking || !verification.notes.trim()} onClick={() => run(() => apiClient.actionCommand(token, item.id, 'verify', { approved: false, notes: verification.notes }), 'Completion rejected and action returned to progress.')} className="rounded-md border border-rose-300 px-4 py-2 text-sm font-semibold text-rose-700 disabled:opacity-50">Reject</button></div></div> : null}
          {!['in_progress', 'reopened', 'completion_requested', 'pending_verification'].includes(item.lifecycle_status) ? <p className="text-sm text-stone-500">Completion controls become available once work is in progress.</p> : null}
        </Section>

        <Section title="Due-date extensions" description={`Original due date: ${item.original_due_date ?? 'not set'} · approved current due date: ${item.current_due_date ?? 'not set'} · ${item.number_of_extensions} approved extension(s)`}>
          {canManage && !TERMINAL.includes(item.lifecycle_status) ? <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)_auto]"><input type="date" value={extension.requestedDueDate} onChange={(event) => setExtension((current) => ({ ...current, requestedDueDate: event.target.value }))} className="rounded-md border border-stone-300 px-3 py-2 text-sm" /><input value={extension.reason} onChange={(event) => setExtension((current) => ({ ...current, reason: event.target.value }))} placeholder="Business reason for extension" className="rounded-md border border-stone-300 px-3 py-2 text-sm" /><button disabled={isWorking || !extension.requestedDueDate || !extension.reason.trim()} onClick={() => run(async () => { await apiClient.requestActionExtension(token, item.id, { requested_due_date: extension.requestedDueDate, extension_reason: extension.reason }); setExtension({ requestedDueDate: '', reason: '' }) }, 'Extension requested.')} className="rounded-md border border-amber-300 bg-amber-50 px-4 py-2 text-sm font-semibold text-amber-900 disabled:opacity-50">Request</button></div> : null}
          <div className="mt-4 space-y-3">{(item.extensions ?? []).map((entry) => <div key={entry.id} className="rounded-lg border border-stone-200 p-3 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><p className="font-semibold">{entry.previous_due_date ?? 'No prior date'} → {entry.requested_due_date}</p><Badge value={entry.decision_status} /></div><p className="mt-1 text-stone-600">{entry.extension_reason}</p>{entry.decision_notes ? <p className="mt-1 text-stone-500">Decision: {entry.decision_notes}</p> : null}{entry.decision_status === 'pending' && canManageExtensions ? <div className="mt-3 flex gap-2"><button disabled={isWorking} onClick={() => run(() => apiClient.decideActionExtension(token, item.id, entry.id, { approved: true, decision_notes: reason || null }), 'Extension approved.')} className="rounded-md bg-emerald-600 px-3 py-1.5 font-semibold text-white">Approve</button><button disabled={isWorking} onClick={() => run(() => apiClient.decideActionExtension(token, item.id, entry.id, { approved: false, decision_notes: reason || null }), 'Extension rejected.')} className="rounded-md border border-rose-300 px-3 py-1.5 font-semibold text-rose-700">Reject</button></div> : null}</div>)}</div>
        </Section>
      </div>

      <div className="grid gap-5 xl:grid-cols-2">
        <Section title="Comments" description="Comments are included in the immutable action timeline.">
          <div className="space-y-3">{comments.map((entry) => <div key={entry.id} className="rounded-lg bg-stone-50 p-3"><p className="text-sm text-stone-800">{entry.body}</p><p className="mt-2 text-xs text-stone-500">{entry.author_name ?? 'System'} · {new Date(entry.created_at).toLocaleString()}</p></div>)}</div>
          <div className="mt-4 flex gap-2"><input value={comment} onChange={(event) => setComment(event.target.value)} placeholder="Add operational context" className="min-w-0 flex-1 rounded-md border border-stone-300 px-3 py-2 text-sm" /><button disabled={isWorking || !comment.trim()} onClick={() => run(async () => { await apiClient.addActionComment(token, item.id, comment); setComment('') }, 'Comment added.')} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Add</button></div>
        </Section>
        <Section title="Timeline" description="Tenant-scoped activity records preserve lifecycle and KPI history.">
          <ol className="space-y-3">{activity.map((entry) => <li key={entry.id} className="border-l-2 border-emerald-200 pl-3"><p className="text-sm font-semibold text-stone-900">{label(entry.event_type)}</p><p className="text-sm text-stone-600">{entry.summary}</p><p className="mt-1 text-xs text-stone-500">{entry.actor_name ?? 'System'} · {new Date(entry.created_at).toLocaleString()}</p></li>)}</ol>
        </Section>
      </div>

      <Section title="Source and recurrence">
        <div className="grid gap-4 text-sm md:grid-cols-2"><div><p className="font-semibold text-stone-700">Source record</p>{item.source_backlink ? <a href={item.source_backlink} className="mt-1 inline-block text-emerald-700 underline">Open {label(item.source_type)} source #{item.source_id}</a> : <p className="mt-1 text-stone-500">{label(item.source_type)}{item.source_id ? ` #${item.source_id}` : ''}</p>}</div><div><p className="font-semibold text-stone-700">Recurrence</p><p className="mt-1 text-stone-500">{item.recurrence_enabled ? `Every ${item.recurrence_interval} ${label(item.recurrence_frequency)}; next due ${item.next_due_date ?? 'calculated on closure'}${item.recurrence_end_date ? `; ends ${item.recurrence_end_date}` : ''}` : 'Not recurring'}</p>{item.recurrence_parent_action_id ? <a href={`/corrective-actions/${item.recurrence_parent_action_id}`} className="mt-1 inline-block text-emerald-700 underline">Open previous occurrence</a> : null}</div></div>
      </Section>
    </div>
  )
}
