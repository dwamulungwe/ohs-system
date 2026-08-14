import { useState } from 'react'
import { Download } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { hasPermission } from '../lib/rbac.js'

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function ActionBulkActionsPanel({ selectedIds, token, user, users, departments, onCompleted, onError }) {
  const [operation, setOperation] = useState('change_priority')
  const [value, setValue] = useState('medium')
  const [note, setNote] = useState('')
  const [isWorking, setIsWorking] = useState(false)
  const canBulk = hasPermission(user, 'corrective_actions.bulk')
  const canExport = hasPermission(user, 'exports.view')

  if (!selectedIds.length) return null

  function defaultValue(nextOperation) {
    if (nextOperation === 'change_priority') return 'medium'
    if (['place_on_hold', 'resume'].includes(nextOperation)) return ''
    return ''
  }

  async function applyBulk() {
    setIsWorking(true)
    try {
      const body = { action_ids: selectedIds, operation, note: note.trim() || null }
      if (operation === 'assign_owner') body.owner_user_id = Number(value)
      if (operation === 'assign_department') body.responsible_department_id = Number(value)
      if (operation === 'change_priority') body.priority = value
      if (operation === 'set_due_date') body.current_due_date = value
      const response = await apiClient.bulkUpdateActions(token, body)
      await onCompleted(`${response.count} action${response.count === 1 ? '' : 's'} updated.`)
    } catch (error) {
      onError(error)
    } finally {
      setIsWorking(false)
    }
  }

  async function exportSelected() {
    setIsWorking(true)
    try {
      const { blob, filename } = await apiClient.bulkExportActions(token, selectedIds)
      downloadBlob(blob, filename)
      await onCompleted(`${selectedIds.length} selected action${selectedIds.length === 1 ? '' : 's'} exported.`)
    } catch (error) {
      onError(error)
    } finally {
      setIsWorking(false)
    }
  }

  return (
    <section className="rounded-xl border border-emerald-200 bg-emerald-50 p-4">
      <div className="flex flex-wrap items-end gap-3">
        <div className="mr-auto">
          <p className="font-semibold text-emerald-950">{selectedIds.length} selected</p>
          <p className="text-xs text-emerald-800">Bulk close is intentionally unavailable; controlled actions retain verification.</p>
        </div>
        {canBulk ? (
          <>
            <label className="text-xs font-semibold uppercase tracking-wide text-emerald-900">
              Operation
              <select value={operation} onChange={(event) => { setOperation(event.target.value); setValue(defaultValue(event.target.value)) }} className="mt-1 block rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm font-normal normal-case text-stone-800">
                <option value="assign_owner">Assign owner</option>
                <option value="assign_department">Assign department</option>
                <option value="change_priority">Change priority</option>
                <option value="set_due_date">Set initial due date</option>
                <option value="place_on_hold">Place on hold</option>
                <option value="resume">Resume</option>
              </select>
            </label>
            {operation === 'assign_owner' ? (
              <select aria-label="Owner" value={value} onChange={(event) => setValue(event.target.value)} className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm">
                <option value="">Select owner</option>
                {users.map((item) => <option key={item.id} value={item.id}>{item.full_name}</option>)}
              </select>
            ) : null}
            {operation === 'assign_department' ? (
              <select aria-label="Responsible department" value={value} onChange={(event) => setValue(event.target.value)} className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm">
                <option value="">Select department</option>
                {departments.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
            ) : null}
            {operation === 'change_priority' ? (
              <select aria-label="Priority" value={value} onChange={(event) => setValue(event.target.value)} className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm">
                {['low', 'medium', 'high', 'critical'].map((item) => <option key={item} value={item}>{item}</option>)}
              </select>
            ) : null}
            {operation === 'set_due_date' ? <input aria-label="Due date" type="date" value={value} onChange={(event) => setValue(event.target.value)} className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm" /> : null}
            <input aria-label="Bulk note" value={note} onChange={(event) => setNote(event.target.value)} placeholder="Optional note" className="rounded-md border border-emerald-300 bg-white px-3 py-2 text-sm" />
            <button type="button" disabled={isWorking || (!value && !['place_on_hold', 'resume'].includes(operation))} onClick={applyBulk} className="rounded-md bg-emerald-700 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Apply</button>
          </>
        ) : null}
        {canExport ? <button type="button" disabled={isWorking} onClick={exportSelected} className="inline-flex items-center gap-2 rounded-md border border-emerald-300 bg-white px-4 py-2 text-sm font-semibold text-emerald-900 disabled:opacity-50"><Download className="size-4" />Export</button> : null}
      </div>
    </section>
  )
}
