import { useCallback, useEffect, useState } from 'react'
import { BellRing, Download, Play, Plus } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { ConfirmDialog } from '../components/ConfirmDialog.jsx'
import { DataTable } from '../components/DataTable.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { PaginationControls } from '../components/PaginationControls.jsx'
import { ResourceFormModal } from '../components/ResourceFormModal.jsx'
import { workflowFormConfigs } from '../config/workflowForms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { canCreateResource, canViewResource, isForbiddenError } from '../lib/rbac.js'

const DEFAULT_LIMIT = 25

function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  link.remove()
  window.setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function ResourceListPage({ resource }) {
  const { token, user } = useAuth()
  const [data, setData] = useState({
    items: [],
    total: 0,
    skip: 0,
    limit: DEFAULT_LIMIT,
  })
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [successMessage, setSuccessMessage] = useState('')
  const [unreadCount, setUnreadCount] = useState(null)
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isMarkAllConfirmOpen, setIsMarkAllConfirmOpen] = useState(false)
  const [isExporting, setIsExporting] = useState(false)

  const formConfig = workflowFormConfigs[resource.key]
  const supportsForm = Boolean(formConfig)

  const loadItems = useCallback(
    async (skip = 0) => {
      setIsLoading(true)
      setError('')

      try {
        const response = await apiClient.getList(token, resource.listEndpoint, {
          skip,
          limit: DEFAULT_LIMIT,
        })
        setData(response)

        if (resource.key === 'notifications') {
          const unread = await apiClient.getUnreadNotificationCount(token)
          setUnreadCount(unread.unread_count)
        }
      } catch (requestError) {
        setError(requestError)
      } finally {
        setIsLoading(false)
      }
    },
    [resource, token],
  )

  useEffect(() => {
    loadItems(0)
  }, [loadItems])

  async function handleMarkAllAsRead() {
    try {
      await apiClient.markAllNotificationsAsRead(token)
      await loadItems(data.skip)
      setSuccessMessage('Notifications marked as read.')
    } catch (requestError) {
      setError(requestError)
    }
  }

  async function handleCreated(record) {
    setIsCreateOpen(false)
    setSuccessMessage(`${resource.singular} created successfully.`)
    await loadItems(0)
    if (resource.key === 'notifications') {
      setUnreadCount((current) => current ?? 0)
    }
  }

  async function handleRunScheduledJobs() {
    try {
      await apiClient.runScheduledJobs(token)
      setSuccessMessage('Scheduled jobs executed successfully.')
      await loadItems(0)
    } catch (requestError) {
      setError(requestError)
    }
  }

  async function handleExportCsv() {
    if (!resource.csvExportEndpoint) {
      return
    }

    setIsExporting(true)
    try {
      const { blob, filename } = await apiClient.downloadFile(token, resource.csvExportEndpoint, {
        fallbackFilename: `${resource.key}.csv`,
      })
      triggerDownload(blob, filename)
      setSuccessMessage(`${resource.label} export downloaded.`)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsExporting(false)
    }
  }

  if (!canViewResource(resource.key, user)) {
    return <NotAuthorizedState />
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Records"
        title={resource.label}
        description={resource.description}
        actions={
          <div className="flex flex-wrap items-center gap-3">
            {supportsForm && canCreateResource(resource.key, user) ? (
              <button
                type="button"
                onClick={() => setIsCreateOpen(true)}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
              >
                <Plus className="size-4" />
                New {resource.singular}
              </button>
            ) : null}
            {resource.csvExportEndpoint ? (
              <button
                type="button"
                onClick={handleExportCsv}
                disabled={isExporting}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:bg-stone-100"
              >
                <Download className="size-4" />
                {isExporting ? 'Exporting...' : 'Export CSV'}
              </button>
            ) : null}
            {resource.key === 'notifications' ? (
              <button
                type="button"
                onClick={() => setIsMarkAllConfirmOpen(true)}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              >
                <BellRing className="size-4" />
                Mark all as read
                {unreadCount !== null ? (
                  <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
                    {unreadCount}
                  </span>
                ) : null}
              </button>
            ) : null}
            {resource.key === 'job-runs' ? (
              <button
                type="button"
                onClick={handleRunScheduledJobs}
                className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
              >
                <Play className="size-4" />
                Run scheduled jobs
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
      {error ? (
        isForbiddenError(error) ? (
          <NotAuthorizedState />
        ) : (
          <ErrorState message={error.message ?? `Unable to load ${resource.label.toLowerCase()}`} onRetry={() => loadItems(data.skip)} />
        )
      ) : null}

      {isLoading ? (
        <LoadingState
          title={`Loading ${resource.label.toLowerCase()}`}
          message="Pulling the latest records from the API."
        />
      ) : (
        <>
          <DataTable
            items={data.items}
            columns={resource.columns}
            getRowHref={
              resource.detailEndpoint
                ? (item) => `${resource.route}/${item.id}`
                : undefined
            }
            emptyTitle={`No ${resource.label.toLowerCase()} yet`}
            emptyMessage={`The backend returned no ${resource.label.toLowerCase()} for this view.`}
          />

          <div className="rounded-lg border border-stone-200 bg-white shadow-sm">
            <PaginationControls
              skip={data.skip}
              limit={data.limit}
              total={data.total}
              itemsCount={data.items.length}
              onPrevious={() => loadItems(Math.max(0, data.skip - data.limit))}
              onNext={() => loadItems(data.skip + data.limit)}
            />
          </div>
        </>
      )}

      {supportsForm ? (
        <ResourceFormModal
          resource={resource}
          config={formConfig}
          mode="create"
          isOpen={isCreateOpen}
          onClose={() => setIsCreateOpen(false)}
          onSaved={handleCreated}
        />
      ) : null}
      <ConfirmDialog
        isOpen={isMarkAllConfirmOpen}
        title="Mark all notifications as read?"
        description="This updates every unread notification for the current user."
        confirmLabel="Mark all as read"
        onClose={() => setIsMarkAllConfirmOpen(false)}
        onConfirm={async () => {
          setIsMarkAllConfirmOpen(false)
          await handleMarkAllAsRead()
        }}
      />
    </div>
  )
}
