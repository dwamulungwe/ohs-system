import { ArrowLeft, BellRing, FileText, Pencil } from 'lucide-react'
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { apiClient } from '../api/client.js'
import { ApprovalDecisionPanel } from '../components/ApprovalDecisionPanel.jsx'
import { ApprovalWorkflowPanel } from '../components/ApprovalWorkflowPanel.jsx'
import { AttachmentsPanel } from '../components/AttachmentsPanel.jsx'
import { ConfirmDialog } from '../components/ConfirmDialog.jsx'
import { DetailSection } from '../components/DetailSection.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { ResourceFormModal } from '../components/ResourceFormModal.jsx'
import { workflowFormConfigs } from '../config/workflowForms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { mapResourceSubtitle } from '../config/resources.jsx'
import { canEditRecord, canViewResource, isForbiddenError } from '../lib/rbac.js'

function openHtmlReport(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(url), 60000)
}

export function ResourceDetailPage({ resource }) {
  const { id } = useParams()
  const navigate = useNavigate()
  const { token, user } = useAuth()
  const [item, setItem] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [isEditOpen, setIsEditOpen] = useState(false)
  const [isReadConfirmOpen, setIsReadConfirmOpen] = useState(false)
  const [isOpeningReport, setIsOpeningReport] = useState(false)

  const formConfig = workflowFormConfigs[resource.key]
  const supportsForm = Boolean(formConfig)

  useEffect(() => {
    let ignore = false

    async function loadDetail() {
      setIsLoading(true)
      setError('')

      try {
        const response = await apiClient.getDetail(token, resource.detailEndpoint(id))
        if (!ignore) {
          setItem(response)
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError)
        }
      } finally {
        if (!ignore) {
          setIsLoading(false)
        }
      }
    }

    loadDetail()

    return () => {
      ignore = true
    }
  }, [id, resource, token])

  async function handleMarkAsRead() {
    try {
      const response = await apiClient.markNotificationAsRead(token, id)
      setItem(response)
      setSuccessMessage('Notification marked as read.')
    } catch (requestError) {
      setError(requestError)
    }
  }

  function handleSaved(updatedRecord) {
    setItem(updatedRecord)
    setIsEditOpen(false)
    setSuccessMessage(`${resource.singular} updated successfully.`)
  }

  async function handleOpenReport() {
    if (!resource.reportEndpoint || !item?.id) {
      return
    }

    setIsOpeningReport(true)

    try {
      const html = await apiClient.getHtmlReport(token, resource.reportEndpoint(item.id))
      openHtmlReport(html)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsOpeningReport(false)
    }
  }

  if (!canViewResource(resource.key, user)) {
    return <NotAuthorizedState />
  }

  if (isLoading) {
    return (
      <LoadingState
        title={`Loading ${resource.singular.toLowerCase()}`}
        message="Fetching the latest detail view from the backend."
      />
    )
  }

  if (error) {
    return isForbiddenError(error)
      ? <NotAuthorizedState />
      : <ErrorState message={error.message ?? 'Unable to load record details'} onRetry={() => navigate(0)} />
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link
          to={resource.route}
          className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
        >
          <ArrowLeft className="size-4" />
          Back to {resource.label}
        </Link>
      </div>

      <PageHeader
        eyebrow={resource.singular}
        title={
          item.title ??
          item.surveillance_type ??
          item.emergency_type ??
          item.job_name ??
          item.contractor_name ??
          item.asset_name ??
          item.action_type ??
          item.full_name ??
          item.name ??
          item.document_title ??
          item.permit_number ??
          `${resource.singular} #${item.id}`
        }
        description={mapResourceSubtitle(resource, item)}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {resource.reportEndpoint ? (
              <button
                type="button"
                onClick={handleOpenReport}
                disabled={isOpeningReport}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:bg-stone-100"
              >
                <FileText className="size-4" />
                {isOpeningReport ? 'Opening report...' : 'Open report'}
              </button>
            ) : null}
            {supportsForm && canEditRecord(resource.key, user, item) ? (
              <button
                type="button"
                onClick={() => setIsEditOpen(true)}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              >
                <Pencil className="size-4" />
                Edit {resource.singular}
              </button>
            ) : null}
            {resource.key === 'notifications' && !item.is_read ? (
              <button
                type="button"
                onClick={() => setIsReadConfirmOpen(true)}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              >
                <BellRing className="size-4" />
                Mark as read
              </button>
            ) : null}
          </div>
        }
      />

      {successMessage ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      ) : null}

      <div className="space-y-4">
        {resource.detailSections.map((section) => (
          <DetailSection key={section.title} title={section.title} fields={section.fields} item={item} />
        ))}
      </div>

      {resource.approvalConfig ? (
        <ApprovalWorkflowPanel
          resource={resource}
          item={item}
          token={token}
          user={user}
          onEntityUpdated={setItem}
        />
      ) : null}

      {resource.key === 'approvals' ? (
        <ApprovalDecisionPanel
          approval={item}
          token={token}
          user={user}
          onUpdated={setItem}
        />
      ) : null}

      {resource.attachmentEntityType ? (
        <AttachmentsPanel
          resource={resource}
          item={item}
          token={token}
          user={user}
        />
      ) : null}

      {supportsForm ? (
        <ResourceFormModal
          resource={resource}
          config={formConfig}
          mode="edit"
          item={item}
          isOpen={isEditOpen}
          onClose={() => setIsEditOpen(false)}
          onSaved={handleSaved}
        />
      ) : null}
      <ConfirmDialog
        isOpen={isReadConfirmOpen}
        title="Mark notification as read?"
        description="This notification will move out of the unread list for the current user."
        confirmLabel="Mark as read"
        onClose={() => setIsReadConfirmOpen(false)}
        onConfirm={async () => {
          setIsReadConfirmOpen(false)
          await handleMarkAsRead()
        }}
      />
    </div>
  )
}
