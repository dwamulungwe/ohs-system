import { Download, Layers3 } from 'lucide-react'
import { useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  URL.revokeObjectURL(url)
}

export function SIOBulkActionsPanel({ selectedIds, token, onCompleted, onError }) {
  const [operation, setOperation] = useState('set_due_date')
  const [dueDate, setDueDate] = useState('')
  const [status, setStatus] = useState('in_progress')
  const [responsibleUserId, setResponsibleUserId] = useState('')
  const [responsibleDepartmentId, setResponsibleDepartmentId] = useState('')
  const [users, setUsers] = useState([])
  const [departments, setDepartments] = useState([])
  const [busy, setBusy] = useState(false)

  useEffect(() => {
    if (!selectedIds.length) return
    Promise.all([
      apiClient.getCollection(token, '/users?limit=500'),
      apiClient.getCollection(token, '/departments?limit=500'),
    ]).then(([nextUsers, nextDepartments]) => {
      setUsers(nextUsers)
      setDepartments(nextDepartments)
    }).catch(() => {})
  }, [selectedIds.length, token])

  if (!selectedIds.length) return null

  async function applyOperation() {
    setBusy(true)
    try {
      const payload = { sio_ids: selectedIds, operation }
      if (operation === 'assign') {
        payload.responsible_user_id = responsibleUserId ? Number(responsibleUserId) : null
        payload.responsible_department_id = responsibleDepartmentId ? Number(responsibleDepartmentId) : null
      } else if (operation === 'set_due_date') {
        payload.due_date = dueDate || null
      } else {
        payload.status = status
      }
      await apiClient.bulkUpdateSios(token, payload)
      onCompleted(`${selectedIds.length} SIO record(s) updated safely.`)
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  async function exportSelection() {
    setBusy(true)
    try {
      const { blob, filename } = await apiClient.bulkExportSios(token, selectedIds)
      downloadBlob(blob, filename)
      onCompleted(`${selectedIds.length} selected SIO record(s) exported.`)
    } catch (error) {
      onError(error)
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <span className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-950">
          <Layers3 className="size-4" /> {selectedIds.length} selected
        </span>
        <select value={operation} onChange={(event) => setOperation(event.target.value)} className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-sm">
          <option value="set_due_date">Set due date</option>
          <option value="assign">Assign responsibility</option>
          <option value="transition">Change status</option>
        </select>
        {operation === 'set_due_date' ? (
          <input type="date" value={dueDate} onChange={(event) => setDueDate(event.target.value)} className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-sm" />
        ) : null}
        {operation === 'assign' ? (
          <>
            <select value={responsibleUserId} onChange={(event) => setResponsibleUserId(event.target.value)} className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-sm">
              <option value="">Responsible user</option>
              {users.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
            </select>
            <select value={responsibleDepartmentId} onChange={(event) => setResponsibleDepartmentId(event.target.value)} className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-sm">
              <option value="">Responsible department</option>
              {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
            </select>
          </>
        ) : null}
        {operation === 'transition' ? (
          <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-md border border-emerald-200 bg-white px-3 py-2 text-sm">
            {['open', 'unassigned', 'assigned', 'in_progress', 'pending_verification', 'complete'].map((value) => <option key={value} value={value}>{value.replaceAll('_', ' ')}</option>)}
          </select>
        ) : null}
        <button type="button" disabled={busy} onClick={applyOperation} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Apply</button>
        <button type="button" disabled={busy} onClick={exportSelection} className="inline-flex items-center gap-2 rounded-md border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-800 disabled:opacity-50"><Download className="size-4" />Export selected</button>
      </div>
    </section>
  )
}
