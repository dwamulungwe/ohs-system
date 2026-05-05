import { CheckCircle2, XCircle } from 'lucide-react'
import { useState } from 'react'
import { apiClient } from '../api/client.js'
import { Badge } from './Badge.jsx'
import { Modal } from './Modal.jsx'
import { NotAuthorizedState } from './NotAuthorizedState.jsx'
import { formatDateTime, humanize } from '../lib/formatters.js'
import { canDecideApproval, isForbiddenError } from '../lib/rbac.js'

function DecisionModal({
  isOpen,
  status,
  notes,
  onNotesChange,
  onClose,
  onConfirm,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <Modal
      title={status === 'approved' ? 'Approve request' : 'Reject request'}
      description="Add optional decision notes for the audit trail and requester notification."
      onClose={onClose}
      maxWidthClassName="max-w-xl"
    >
      <div className="space-y-4">
        <textarea
          value={notes}
          onChange={(event) => onNotesChange(event.target.value)}
          rows={5}
          className="w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          placeholder="Add decision notes"
        />
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={[
              'rounded-md px-4 py-2 text-sm font-semibold text-white transition',
              status === 'approved' ? 'bg-emerald-600 hover:bg-emerald-700' : 'bg-rose-600 hover:bg-rose-700',
            ].join(' ')}
          >
            {status === 'approved' ? 'Approve' : 'Reject'}
          </button>
        </div>
      </div>
    </Modal>
  )
}

export function ApprovalDecisionPanel({ approval, token, user, onUpdated }) {
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [decisionStatus, setDecisionStatus] = useState('approved')
  const [decisionNotes, setDecisionNotes] = useState('')
  const [isOpen, setIsOpen] = useState(false)

  if (!canDecideApproval(user)) {
    return null
  }

  if (error && isForbiddenError(error)) {
    return <NotAuthorizedState />
  }

  async function handleDecision() {
    try {
      const updated = await apiClient.decideApproval(token, approval.id, {
        status: decisionStatus,
        decision_notes: decisionNotes.trim() || null,
      })
      setIsOpen(false)
      setDecisionNotes('')
      setSuccessMessage(`Approval ${decisionStatus}.`)
      onUpdated(updated)
    } catch (requestError) {
      setError(requestError)
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-stone-950">Decision Controls</h2>
          <p className="mt-1 text-sm leading-6 text-stone-600">
            {approval.status === 'pending'
              ? 'This request is waiting for a final decision.'
              : `This request was ${humanize(approval.status).toLowerCase()} on ${formatDateTime(approval.decided_at)}.`}
          </p>
        </div>
        <Badge value={approval.status} />
      </div>

      {successMessage ? (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      ) : null}

      {error && !isForbiddenError(error) ? (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error.message ?? 'Unable to update the approval.'}
        </div>
      ) : null}

      {approval.status === 'pending' ? (
        <div className="mt-5 flex flex-wrap items-center gap-3">
          <button
            type="button"
            onClick={() => {
              setDecisionStatus('approved')
              setDecisionNotes('')
              setIsOpen(true)
            }}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
          >
            <CheckCircle2 className="size-4" />
            Approve
          </button>
          <button
            type="button"
            onClick={() => {
              setDecisionStatus('rejected')
              setDecisionNotes('')
              setIsOpen(true)
            }}
            className="inline-flex items-center gap-2 rounded-md bg-rose-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-700"
          >
            <XCircle className="size-4" />
            Reject
          </button>
        </div>
      ) : null}

      <DecisionModal
        isOpen={isOpen}
        status={decisionStatus}
        notes={decisionNotes}
        onNotesChange={setDecisionNotes}
        onClose={() => setIsOpen(false)}
        onConfirm={handleDecision}
      />
    </section>
  )
}
