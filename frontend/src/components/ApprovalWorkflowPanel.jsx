import { CheckCircle2, Clock3, FileCheck2, XCircle } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client.js'
import { Badge } from './Badge.jsx'
import { Modal } from './Modal.jsx'
import { NotAuthorizedState } from './NotAuthorizedState.jsx'
import { formatDateTime, humanize } from '../lib/formatters.js'
import { canDecideApproval, canRequestApproval, isForbiddenError } from '../lib/rbac.js'

function ApprovalModal({
  title,
  description,
  confirmLabel,
  isOpen,
  tone = 'default',
  notes,
  onNotesChange,
  onClose,
  onConfirm,
}) {
  if (!isOpen) {
    return null
  }

  return (
    <Modal title={title} description={description} onClose={onClose} maxWidthClassName="max-w-xl">
      <div className="space-y-4">
        <label className="block text-sm">
          <span className="font-medium text-stone-900">Notes</span>
          <textarea
            value={notes}
            onChange={(event) => onNotesChange(event.target.value)}
            rows={5}
            className="mt-2 w-full rounded-md border border-stone-300 px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            placeholder="Add context for the workflow record."
          />
        </label>
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
              tone === 'danger' ? 'bg-rose-600 hover:bg-rose-700' : 'bg-emerald-600 hover:bg-emerald-700',
            ].join(' ')}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}

function ApprovalCard({ approval, canDecide, onApprove, onReject }) {
  return (
    <div className="rounded-xl border border-stone-200 bg-stone-50 p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Badge value={approval.status} />
            <span className="text-sm font-medium text-stone-900">{humanize(approval.action_type)}</span>
          </div>
          <p className="text-sm text-stone-600">
            Requested by user #{approval.requested_by_user_id ?? 'Unknown'} on {formatDateTime(approval.created_at)}
          </p>
          {approval.request_notes ? (
            <p className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm leading-6 text-stone-700">
              {approval.request_notes}
            </p>
          ) : null}
          {approval.decision_notes ? (
            <p className="rounded-lg border border-stone-200 bg-white px-3 py-2 text-sm leading-6 text-stone-700">
              {approval.decision_notes}
            </p>
          ) : null}
          {approval.decided_at ? (
            <p className="text-xs font-medium uppercase tracking-[0.08em] text-stone-500">
              Decided {formatDateTime(approval.decided_at)}
            </p>
          ) : null}
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/approvals/${approval.id}`}
            className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-100"
          >
            <FileCheck2 className="size-4" />
            View
          </Link>
          {approval.status === 'pending' && canDecide ? (
            <>
              <button
                type="button"
                onClick={() => onApprove(approval)}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
              >
                <CheckCircle2 className="size-4" />
                Approve
              </button>
              <button
                type="button"
                onClick={() => onReject(approval)}
                className="inline-flex items-center gap-2 rounded-md bg-rose-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-rose-700"
              >
                <XCircle className="size-4" />
                Reject
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

export function ApprovalWorkflowPanel({ resource, item, token, user, onEntityUpdated }) {
  const [approvals, setApprovals] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [requestNotes, setRequestNotes] = useState('')
  const [isRequestOpen, setIsRequestOpen] = useState(false)
  const [decisionTarget, setDecisionTarget] = useState(null)
  const [decisionStatus, setDecisionStatus] = useState('approved')
  const [decisionNotes, setDecisionNotes] = useState('')

  const approvalConfig = resource.approvalConfig
  const canRequest = canRequestApproval(resource.key, user, item)
  const canDecide = canDecideApproval(user)

  async function refreshEntity() {
    if (!onEntityUpdated) {
      return
    }

    const updated = await apiClient.getDetail(token, resource.detailEndpoint(item.id))
    onEntityUpdated(updated)
  }

  async function loadApprovals() {
    setIsLoading(true)
    setError('')

    try {
      const response = await apiClient.getList(
        token,
        `/approvals?entity_type=${approvalConfig.entityType}&entity_id=${item.id}`,
        { skip: 0, limit: 20 },
      )
      setApprovals(response.items)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsLoading(false)
    }
  }

  useEffect(() => {
    loadApprovals()
  }, [approvalConfig.entityType, item.id, token])

  async function handleRequestApproval() {
    try {
      await apiClient.requestApproval(token, approvalConfig.entityType, item.id, {
        action_type: approvalConfig.actionType,
        request_notes: requestNotes.trim() || null,
      })
      setIsRequestOpen(false)
      setRequestNotes('')
      setSuccessMessage('Approval request submitted.')
      await Promise.all([loadApprovals(), refreshEntity()])
    } catch (requestError) {
      setError(requestError)
    }
  }

  async function handleDecision() {
    if (!decisionTarget) {
      return
    }

    try {
      await apiClient.decideApproval(token, decisionTarget.id, {
        status: decisionStatus,
        decision_notes: decisionNotes.trim() || null,
      })
      setDecisionTarget(null)
      setDecisionNotes('')
      setSuccessMessage(`Approval ${decisionStatus}.`)
      await Promise.all([loadApprovals(), refreshEntity()])
    } catch (requestError) {
      setError(requestError)
    }
  }

  if (error && isForbiddenError(error)) {
    return <NotAuthorizedState />
  }

  const pendingApproval = approvals.find(
    (approval) => approval.status === 'pending' && approval.action_type === approvalConfig.actionType,
  )

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
        <div>
          <h2 className="text-lg font-semibold tracking-tight text-stone-950">Approval Workflow</h2>
          <p className="mt-1 text-sm leading-6 text-stone-600">
            Track review requests and formal decisions for this record.
          </p>
        </div>
        {canRequest && !pendingApproval ? (
          <button
            type="button"
            onClick={() => setIsRequestOpen(true)}
            className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
          >
            <Clock3 className="size-4" />
            {approvalConfig.requestLabel}
          </button>
        ) : null}
      </div>

      {successMessage ? (
        <div className="mt-4 rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      ) : null}

      {error && !isForbiddenError(error) ? (
        <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
          {error.message ?? 'Unable to load approval workflow details.'}
        </div>
      ) : null}

      <div className="mt-5 space-y-4">
        {isLoading ? (
          <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-600">
            Loading approvals for this record.
          </div>
        ) : approvals.length ? (
          approvals.map((approval) => (
            <ApprovalCard
              key={approval.id}
              approval={approval}
              canDecide={canDecide}
              onApprove={(selected) => {
                setDecisionTarget(selected)
                setDecisionStatus('approved')
                setDecisionNotes('')
              }}
              onReject={(selected) => {
                setDecisionTarget(selected)
                setDecisionStatus('rejected')
                setDecisionNotes('')
              }}
            />
          ))
        ) : (
          <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-4 py-6 text-sm text-stone-600">
            No approval requests have been recorded for this item yet.
          </div>
        )}
      </div>

      <ApprovalModal
        title={approvalConfig.requestTitle}
        description="Add any context the approver should see before making a decision."
        confirmLabel="Submit request"
        isOpen={isRequestOpen}
        notes={requestNotes}
        onNotesChange={setRequestNotes}
        onClose={() => setIsRequestOpen(false)}
        onConfirm={handleRequestApproval}
      />

      <ApprovalModal
        title={decisionStatus === 'approved' ? 'Approve request' : 'Reject request'}
        description="Decision notes are saved on the workflow record and shown in approval history."
        confirmLabel={decisionStatus === 'approved' ? 'Approve' : 'Reject'}
        tone={decisionStatus === 'approved' ? 'default' : 'danger'}
        isOpen={Boolean(decisionTarget)}
        notes={decisionNotes}
        onNotesChange={setDecisionNotes}
        onClose={() => setDecisionTarget(null)}
        onConfirm={handleDecision}
      />
    </section>
  )
}
