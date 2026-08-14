import { useCallback, useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { ActionBulkActionsPanel } from '../components/ActionBulkActionsPanel.jsx'
import { DataTable } from '../components/DataTable.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { PaginationControls } from '../components/PaginationControls.jsx'
import { ResourceFormModal } from '../components/ResourceFormModal.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { workflowFormConfigs } from '../config/workflowForms.js'
import { useAuth } from '../context/AuthContext.jsx'
import { canCreateResource, canViewResource, hasPermission, isForbiddenError } from '../lib/rbac.js'

const LIMIT = 25
const QUEUES = [
  ['my_actions', 'My Actions'],
  ['awaiting_acceptance', 'Awaiting My Acceptance'],
  ['due_this_week', 'Due This Week'],
  ['overdue', 'Overdue'],
  ['awaiting_verification', 'Awaiting My Verification'],
  ['my_team', 'My Team'],
  ['my_department', 'My Department'],
  ['recently_closed', 'Recently Closed'],
  ['reopened', 'Reopened'],
]

function optionRows(filter, refs) {
  if (filter.type === 'site') return refs.sites.map((item) => ({ value: item.id, label: item.name }))
  if (filter.type === 'department') return refs.departments.map((item) => ({ value: item.id, label: item.name }))
  if (filter.type === 'user') return refs.users.map((item) => ({ value: item.id, label: item.full_name }))
  return (filter.options ?? []).map((value) => ({ value, label: value.replaceAll('_', ' ') }))
}

function Breakdown({ title, values }) {
  const rows = Object.entries(values ?? {}).slice(0, 8)
  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
      <h3 className="font-semibold text-stone-900">{title}</h3>
      <div className="mt-3 space-y-2">
        {rows.length ? rows.map(([label, value]) => (
          <div key={label} className="flex items-center justify-between gap-3 text-sm"><span className="truncate text-stone-600">{label.replaceAll('_', ' ')}</span><span className="font-semibold text-stone-900">{value}</span></div>
        )) : <p className="text-sm text-stone-500">No data for this view.</p>}
      </div>
    </section>
  )
}

function InsightList({ title, rows, detailKey }) {
  return (
    <section className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
      <h3 className="font-semibold text-stone-900">{title}</h3>
      <div className="mt-3 space-y-3">
        {(rows ?? []).slice(0, 5).map((item) => (
          <a key={item.id ?? `${item.action_reference}-${item[detailKey]}`} href={item.id ? `/corrective-actions/${item.id}` : undefined} className="block rounded-lg bg-stone-50 p-3 text-sm hover:bg-emerald-50">
            <span className="block font-semibold text-stone-900">{item.action_reference ?? item.title ?? item.owner ?? item.department ?? item.source}</span>
            <span className="mt-1 block text-stone-500">{item[detailKey] ?? item.title ?? ''}</span>
          </a>
        ))}
        {!rows?.length ? <p className="text-sm text-stone-500">No exceptions identified.</p> : null}
      </div>
    </section>
  )
}

export function ActionCentrePage({ resource }) {
  const { token, user } = useAuth()
  const [data, setData] = useState({ items: [], total: 0, skip: 0, limit: LIMIT })
  const [dashboard, setDashboard] = useState(null)
  const [refs, setRefs] = useState({ sites: [], departments: [], users: [] })
  const [filters, setFilters] = useState(Object.fromEntries(resource.filters.map((item) => [item.name, ''])))
  const [appliedFilters, setAppliedFilters] = useState({})
  const [queue, setQueue] = useState('my_actions')
  const [selectedIds, setSelectedIds] = useState([])
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const canAnalytics = hasPermission(user, 'corrective_actions.view_analytics')
  const canSelect = hasPermission(user, 'corrective_actions.bulk') || hasPermission(user, 'exports.view')

  const loadItems = useCallback(async (skip = 0) => {
    setIsLoading(true)
    setError('')
    try {
      const endpoint = apiClient.buildPath(resource.listEndpoint, { ...appliedFilters, queue })
      const response = await apiClient.getList(token, endpoint, { skip, limit: LIMIT })
      setData(response)
      setSelectedIds([])
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsLoading(false)
    }
  }, [appliedFilters, queue, resource.listEndpoint, token])

  useEffect(() => { loadItems(0) }, [loadItems])

  useEffect(() => {
    let ignore = false
    Promise.allSettled([
      apiClient.getCollection(token, '/sites?limit=500'),
      apiClient.getCollection(token, '/departments?limit=500'),
      apiClient.getCollection(token, '/users?limit=500'),
    ]).then(([sites, departments, users]) => {
      if (!ignore) setRefs({
        sites: sites.status === 'fulfilled' ? sites.value : [],
        departments: departments.status === 'fulfilled' ? departments.value : [],
        users: users.status === 'fulfilled' ? users.value : [],
      })
    })
    if (canAnalytics) {
      apiClient.getActionDashboard(token).then((response) => { if (!ignore) setDashboard(response) }).catch((requestError) => { if (!ignore) setError(requestError) })
    }
    return () => { ignore = true }
  }, [canAnalytics, token])

  if (!canViewResource(resource.key, user)) return <NotAuthorizedState />

  async function completed(message) {
    setNotice(message)
    await loadItems(data.skip)
    if (canAnalytics) setDashboard(await apiClient.getActionDashboard(token))
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow="Unified register" title="Action Centre" description={resource.description} actions={canCreateResource(resource.key, user) ? <button type="button" onClick={() => setIsCreateOpen(true)} className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700"><Plus className="size-4" />New Action</button> : null} />

      {notice ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{notice}</div> : null}
      {error ? (isForbiddenError(error) ? <NotAuthorizedState /> : <ErrorState message={error.message ?? 'Unable to load actions'} onRetry={() => loadItems(data.skip)} />) : null}

      {dashboard ? (
        <>
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Open actions" value={dashboard.open_actions} />
            <StatCard label="Overdue" value={dashboard.overdue_actions} accent="text-rose-700" accentBg="bg-rose-200" description={`${dashboard.overdue_rate}% of open actions`} />
            <StatCard label="Due this week" value={dashboard.due_this_week} accent="text-amber-700" accentBg="bg-amber-200" />
            <StatCard label="Awaiting verification" value={dashboard.awaiting_verification} accent="text-sky-700" accentBg="bg-sky-200" />
            <StatCard label="Due in 30 days" value={dashboard.due_in_30_days} />
            <StatCard label="Critical/high overdue" value={dashboard.critical_high_overdue} accent="text-rose-700" accentBg="bg-rose-200" />
            <StatCard label="Pending extensions" value={dashboard.pending_extension_requests} accent="text-amber-700" accentBg="bg-amber-200" />
            <StatCard label="Closed this period" value={dashboard.closed_this_period} description={`${dashboard.current_due_date_on_time_closure_rate}% on time to approved due date`} />
          </div>
          <details className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
            <summary className="cursor-pointer font-semibold text-stone-900">Management breakdowns and insights</summary>
            <div className="mt-4 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Breakdown title="By site" values={dashboard.by_site} /><Breakdown title="By responsible department" values={dashboard.by_responsible_department} /><Breakdown title="By owner" values={dashboard.by_owner} /><Breakdown title="By source" values={dashboard.by_source} />
              <Breakdown title="By priority" values={dashboard.by_priority} /><Breakdown title="By status" values={dashboard.by_status} /><Breakdown title="By age" values={dashboard.by_age_bucket} /><Breakdown title="By manager" values={dashboard.by_manager} />
              <InsightList title="Oldest open" rows={dashboard.oldest_open_actions} detailKey="title" /><InsightList title="Most overdue" rows={dashboard.most_overdue_actions} detailKey="days_overdue" /><InsightList title="Repeated extensions" rows={dashboard.repeated_extension_actions} detailKey="number_of_extensions" /><Breakdown title="Owners with overdue items" values={dashboard.owners_with_overdue_actions} />
              <Breakdown title="Largest department backlogs" values={dashboard.departments_with_highest_backlog} /><Breakdown title="Sources generating overdue actions" values={dashboard.sources_generating_most_overdue_actions} />
            </div>
            <div className="mt-4 grid gap-4 sm:grid-cols-2 lg:grid-cols-4 text-sm">
              <p><span className="font-semibold">Original due-date on-time closure:</span> {dashboard.original_due_date_on_time_closure_rate}%</p><p><span className="font-semibold">Average closure:</span> {dashboard.average_closure_days} days</p><p><span className="font-semibold">Median closure:</span> {dashboard.median_closure_days} days</p><p><span className="font-semibold">Verification rejection:</span> {dashboard.verification_rejection_rate}%</p>
            </div>
          </details>
        </>
      ) : null}

      <section className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
        <div className="flex gap-2 overflow-x-auto pb-2">
          {QUEUES.map(([value, label]) => <button key={value} type="button" onClick={() => setQueue(value)} className={`shrink-0 rounded-full px-3 py-2 text-sm font-medium ${queue === value ? 'bg-emerald-700 text-white' : 'bg-stone-100 text-stone-700 hover:bg-stone-200'}`}>{label}</button>)}
        </div>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {resource.filters.map((filter) => (
            <label key={filter.name} className="block text-sm"><span className="text-xs font-semibold uppercase tracking-wide text-stone-500">{filter.label}</span>
              {['select', 'site', 'department', 'user'].includes(filter.type) ? <select value={filters[filter.name]} onChange={(event) => setFilters((current) => ({ ...current, [filter.name]: event.target.value }))} className="mt-1 block w-full rounded-md border border-stone-300 bg-white px-3 py-2"><option value="">All</option>{optionRows(filter, refs).map((option) => <option key={`${filter.name}-${option.value}`} value={option.value}>{option.label}</option>)}</select> : <input type={filter.type === 'search' ? 'search' : filter.type} value={filters[filter.name]} onChange={(event) => setFilters((current) => ({ ...current, [filter.name]: event.target.value }))} className="mt-1 block w-full rounded-md border border-stone-300 px-3 py-2" />}
            </label>
          ))}
        </div>
        <div className="mt-4 flex gap-2"><button type="button" onClick={() => setAppliedFilters(Object.fromEntries(Object.entries(filters).filter(([, value]) => value !== '')))} className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white">Apply filters</button><button type="button" onClick={() => { const empty = Object.fromEntries(resource.filters.map((item) => [item.name, ''])); setFilters(empty); setAppliedFilters({}) }} className="rounded-md border border-stone-300 px-4 py-2 text-sm font-medium">Clear</button></div>
      </section>

      <ActionBulkActionsPanel selectedIds={selectedIds} token={token} user={user} users={refs.users} departments={refs.departments} onCompleted={completed} onError={setError} />
      {isLoading ? <LoadingState title="Loading actions" message="Applying queue and register filters." /> : <><DataTable items={data.items} columns={resource.columns} getRowHref={(item) => `${resource.route}/${item.id}`} emptyTitle="No actions found" emptyMessage="No actions match this queue and filter combination." selectedIds={canSelect ? selectedIds : undefined} onSelectionChange={canSelect ? (itemId, checked) => setSelectedIds((current) => checked ? [...new Set([...current, itemId])] : current.filter((id) => id !== itemId)) : undefined} /><div className="rounded-lg border border-stone-200 bg-white shadow-sm"><PaginationControls skip={data.skip} limit={data.limit} total={data.total} itemsCount={data.items.length} onPrevious={() => loadItems(Math.max(0, data.skip - data.limit))} onNext={() => loadItems(data.skip + data.limit)} /></div></>}

      <ResourceFormModal resource={resource} config={workflowFormConfigs[resource.key]} mode="create" isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} onSaved={async () => { setIsCreateOpen(false); await completed('Action created successfully.') }} />
    </div>
  )
}
