import { useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'
import { Badge } from '../components/Badge.jsx'
import { EmptyState } from '../components/EmptyState.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { StatCard } from '../components/StatCard.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, formatNumber, humanize } from '../lib/formatters.js'
import { ROLES, canViewDashboard, isForbiddenError } from '../lib/rbac.js'

function openHtmlReport(html) {
  const blob = new Blob([html], { type: 'text/html;charset=utf-8' })
  const url = URL.createObjectURL(blob)
  window.open(url, '_blank', 'noopener,noreferrer')
  window.setTimeout(() => URL.revokeObjectURL(url), 60000)
}

function SectionCard({ title, description, children, className = '' }) {
  return (
    <section className={`rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60 ${className}`.trim()}>
      <div className="flex flex-col gap-1">
        <h2 className="text-base font-semibold tracking-tight text-stone-950">{title}</h2>
        {description ? (
          <p className="text-sm leading-6 text-stone-600">{description}</p>
        ) : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  )
}

function DistributionPanel({ title, description, values }) {
  const entries = Object.entries(values ?? {})
  const maxValue = Math.max(...entries.map(([, value]) => value), 0)

  return (
    <SectionCard title={title} description={description}>
      {entries.length ? (
        <div className="space-y-3">
          {entries.map(([key, value]) => (
            <div key={key} className="space-y-1.5">
              <div className="flex items-center justify-between gap-3 text-sm">
                <span className="text-stone-600">{humanize(key)}</span>
                <span className="font-medium text-stone-950">{formatNumber(value)}</span>
              </div>
              <div className="h-2.5 rounded-full bg-stone-100">
                <div
                  className="h-2.5 rounded-full bg-emerald-500 transition-all"
                  style={{ width: `${maxValue ? (value / maxValue) * 100 : 0}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title="No distribution data" message="No records matched the current filters." />
      )}
    </SectionCard>
  )
}

function RecordListPanel({ title, description, items, emptyTitle, emptyMessage, renderItem }) {
  return (
    <SectionCard title={title} description={description}>
      {items?.length ? (
        <div className="space-y-3">
          {items.map((item, index) => (
            <div key={`${item.entity_type ?? 'item'}-${item.entity_id ?? item.id ?? index}`} className="rounded-lg border border-stone-200 bg-stone-50 p-4">
              {renderItem(item)}
            </div>
          ))}
        </div>
      ) : (
        <EmptyState title={emptyTitle} message={emptyMessage} />
      )}
    </SectionCard>
  )
}

function FilterControls({
  filters,
  sites,
  disableSiteFilter,
  onChange,
  onApply,
  onClear,
}) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <label className="block min-w-44 text-sm">
        <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Site</span>
        <select
          value={filters.site_id}
          onChange={(event) => onChange('site_id', event.target.value)}
          disabled={disableSiteFilter}
          className="mt-2 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 disabled:bg-stone-100"
        >
          <option value="">All sites</option>
          {sites.map((site) => (
            <option key={site.id} value={String(site.id)}>
              {site.name}
            </option>
          ))}
        </select>
      </label>

      <label className="block text-sm">
        <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">From</span>
        <input
          type="date"
          value={filters.date_from}
          onChange={(event) => onChange('date_from', event.target.value)}
          className="mt-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
        />
      </label>

      <label className="block text-sm">
        <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">To</span>
        <input
          type="date"
          value={filters.date_to}
          onChange={(event) => onChange('date_to', event.target.value)}
          className="mt-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
        />
      </label>

      <button
        type="button"
        onClick={onApply}
        className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700"
      >
        Apply
      </button>
      <button
        type="button"
        onClick={onClear}
        className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
      >
        Clear
      </button>
    </div>
  )
}

export function DashboardPage() {
  const { token, user, primaryRole, assignedSiteId } = useAuth()
  const isSupervisor = primaryRole === ROLES.SUPERVISOR
  const defaultSiteId = isSupervisor && assignedSiteId ? String(assignedSiteId) : ''
  const [filters, setFilters] = useState({ site_id: defaultSiteId, date_from: '', date_to: '' })
  const [appliedFilters, setAppliedFilters] = useState({ site_id: defaultSiteId, date_from: '', date_to: '' })
  const [sites, setSites] = useState([])
  const [summary, setSummary] = useState(null)
  const [risk, setRisk] = useState(null)
  const [actions, setActions] = useState(null)
  const [compliance, setCompliance] = useState(null)
  const [permits, setPermits] = useState(null)
  const [approvals, setApprovals] = useState(null)
  const [siteSummaries, setSiteSummaries] = useState([])
  const [trends, setTrends] = useState(null)
  const [error, setError] = useState(null)
  const [isLoading, setIsLoading] = useState(true)
  const [activeReport, setActiveReport] = useState('')

  useEffect(() => {
    if (isSupervisor && assignedSiteId) {
      const scopedFilters = { site_id: String(assignedSiteId), date_from: '', date_to: '' }
      setFilters(scopedFilters)
      setAppliedFilters(scopedFilters)
    }
  }, [isSupervisor, assignedSiteId])

  useEffect(() => {
    if (!canViewDashboard(user)) {
      setIsLoading(false)
      setError(null)
      return
    }

    let ignore = false

    async function loadDashboard() {
      setIsLoading(true)
      setError(null)

      try {
        const dashboardFilters = {
          site_id: appliedFilters.site_id || undefined,
          date_from: appliedFilters.date_from || undefined,
          date_to: appliedFilters.date_to || undefined,
        }
        const [
          summaryResponse,
          riskResponse,
          actionsResponse,
          complianceResponse,
          permitsResponse,
          approvalsResponse,
          sitesResponse,
          trendsResponse,
          availableSites,
        ] = await Promise.all([
          apiClient.getDashboardManagementSummary(token, dashboardFilters),
          apiClient.getDashboardRisk(token, dashboardFilters),
          apiClient.getDashboardActions(token, dashboardFilters),
          apiClient.getDashboardCompliance(token, dashboardFilters),
          apiClient.getDashboardPermits(token, dashboardFilters),
          apiClient.getDashboardApprovals(token, dashboardFilters),
          apiClient.getDashboardSites(token, dashboardFilters),
          apiClient.getDashboardTrends(token, dashboardFilters),
          apiClient.getCollection(token, '/sites'),
        ])

        if (!ignore) {
          setSummary(summaryResponse)
          setRisk(riskResponse)
          setActions(actionsResponse)
          setCompliance(complianceResponse)
          setPermits(permitsResponse)
          setApprovals(approvalsResponse)
          setSiteSummaries(sitesResponse)
          setTrends(trendsResponse)
          setSites(availableSites)
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

    loadDashboard()

    return () => {
      ignore = true
    }
  }, [token, user, appliedFilters])

  if (!canViewDashboard(user)) {
    return <NotAuthorizedState message="This dashboard is available to Admin, OHS Manager, Safety Officer, and Supervisor roles." />
  }

  if (isLoading) {
    return (
      <LoadingState
        title="Loading dashboard analytics"
        message="Collecting management-level safety intelligence across incidents, risk, actions, compliance, permits, and approvals."
      />
    )
  }

  if (error) {
    return isForbiddenError(error)
      ? <NotAuthorizedState />
      : <ErrorState message={error.message ?? 'Unable to load dashboard analytics'} onRetry={() => setAppliedFilters({ ...appliedFilters })} />
  }

  const executiveCards = [
    {
      key: 'critical_open_incidents_count',
      label: 'Critical Open Incidents',
      value: summary?.incident_snapshot?.critical_open_incidents_count ?? 0,
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Highest-severity unresolved incidents.',
    },
    {
      key: 'open_critical_hazards_count',
      label: 'Open Critical Hazards',
      value: risk?.open_critical_hazards_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Open hazards with critical risk level.',
    },
    {
      key: 'overdue_corrective_actions_count',
      label: 'Overdue Actions',
      value: actions?.overdue_corrective_actions_count ?? 0,
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Corrective actions past due date.',
    },
    {
      key: 'training_compliance_rate',
      label: 'Training Compliance',
      value: compliance?.training_compliance_rate ?? 0,
      accent: 'text-sky-700',
      accentBg: 'bg-sky-200',
      description: 'Completed valid training as a percentage of assigned training.',
    },
    {
      key: 'expiring_soon_permits_count',
      label: 'Permits Expiring Soon',
      value: permits?.expiring_soon_permits_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Permits ending within the configured renewal threshold.',
    },
    {
      key: 'pending_approvals_count',
      label: 'Pending Approvals',
      value: approvals?.pending_approvals_count ?? 0,
      accent: 'text-violet-700',
      accentBg: 'bg-violet-200',
      description: 'Formal workflow decisions still awaiting action.',
    },
    {
      key: 'trifr',
      label: 'TRIFR',
      value: summary?.kpi_snapshot?.trifr ?? 0,
      accent: 'text-cyan-700',
      accentBg: 'bg-cyan-200',
      description: 'Total recordable injury frequency rate from incidents and hours worked.',
    },
    {
      key: 'ltifr',
      label: 'LTIFR',
      value: summary?.kpi_snapshot?.ltifr ?? 0,
      accent: 'text-indigo-700',
      accentBg: 'bg-indigo-200',
      description: 'Lost time injury frequency rate for the selected scope.',
    },
    {
      key: 'published_communications_count',
      label: 'Published Comms',
      value: summary?.communication_snapshot?.published_communications_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Safety communications currently published in the filtered data set.',
    },
    {
      key: 'open_behaviour_issues_count',
      label: 'Open Behaviour Issues',
      value: summary?.behaviour_snapshot?.open_behaviour_issues_count ?? 0,
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Unsafe acts, conduct issues, or event observations still requiring follow-up.',
    },
    {
      key: 'open_investigations_count',
      label: 'Open Investigations',
      value: summary?.investigation_snapshot?.open_investigations_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Investigations that are still draft, in progress, or pending approval.',
    },
    {
      key: 'non_compliant_items_count',
      label: 'Non-Compliant Legal Items',
      value: summary?.legal_compliance_snapshot?.non_compliant_items_count ?? 0,
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Legal register items currently marked non-compliant.',
    },
    {
      key: 'pending_jsa_approvals_count',
      label: 'Pending JSA Approvals',
      value: summary?.jsa_snapshot?.pending_jsa_approvals_count ?? 0,
      accent: 'text-violet-700',
      accentBg: 'bg-violet-200',
      description: 'Job safety analyses waiting for approval before operational use.',
    },
    {
      key: 'contractor_compliance_gaps_count',
      label: 'Contractor Gaps',
      value: summary?.contractor_snapshot?.contractor_compliance_gaps_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Contractors with induction, insurance, or document readiness gaps.',
    },
    {
      key: 'equipment_exposure_count',
      label: 'Defective / Overdue Equipment',
      value:
        (summary?.asset_snapshot?.defective_assets_count ?? 0) +
        (summary?.asset_snapshot?.overdue_asset_inspections_count ?? 0),
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Defective assets plus items with overdue inspection dates.',
    },
    {
      key: 'medical_surveillance_overdue_count',
      label: 'Overdue Medical',
      value: summary?.medical_surveillance_snapshot?.overdue_count ?? 0,
      accent: 'text-rose-700',
      accentBg: 'bg-rose-200',
      description: 'Medical surveillance activities now past due.',
    },
    {
      key: 'overdue_drills_count',
      label: 'Overdue Drills',
      value: summary?.emergency_drill_snapshot?.overdue_drills_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Emergency drills that should already have been completed.',
    },
    {
      key: 'documents_expiring_soon_count',
      label: 'Docs Expiring Soon',
      value: summary?.document_snapshot?.documents_expiring_soon_count ?? 0,
      accent: 'text-amber-700',
      accentBg: 'bg-amber-200',
      description: 'Controlled documents nearing expiry.',
    },
    {
      key: 'open_audits_count',
      label: 'Open Audits',
      value: summary?.audit_snapshot?.open_audits_count ?? 0,
      accent: 'text-sky-700',
      accentBg: 'bg-sky-200',
      description: 'Audit records that still require closure or follow-through.',
    },
  ]

  const reportFilters = {
    site_id: appliedFilters.site_id || undefined,
    date_from: appliedFilters.date_from || undefined,
    date_to: appliedFilters.date_to || undefined,
  }

  async function handleOpenDashboardReport(path, reportKey) {
    setActiveReport(reportKey)
    setError(null)

    try {
      const html = await apiClient.getHtmlReport(token, path, { params: reportFilters })
      openHtmlReport(html)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setActiveReport('')
    }
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Analytics"
        title="Executive safety dashboard"
        description="Management-ready operational intelligence across incidents, risk, actions, compliance, permits, approvals, and urgent exceptions."
        actions={(
          <div className="flex flex-wrap items-end gap-3">
            <FilterControls
              filters={filters}
              sites={sites}
              disableSiteFilter={isSupervisor}
              onChange={(field, value) => setFilters((current) => ({ ...current, [field]: value }))}
              onApply={() => setAppliedFilters({ ...filters })}
              onClear={() => {
                const cleared = { site_id: defaultSiteId, date_from: '', date_to: '' }
                setFilters(cleared)
                setAppliedFilters(cleared)
              }}
            />
            {[
              ['executive', 'Executive Summary', '/exports/reports/executive-summary'],
              ['actions', 'Overdue Actions', '/exports/reports/overdue-corrective-actions'],
              ['hazards', 'Critical Hazards', '/exports/reports/critical-hazards'],
              ['incidents', 'Incident Summary', '/exports/reports/incidents-summary'],
            ].map(([key, label, path]) => (
              <button
                key={key}
                type="button"
                onClick={() => handleOpenDashboardReport(path, key)}
                disabled={activeReport === key}
                className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:bg-stone-100"
              >
                {activeReport === key ? 'Opening report...' : label}
              </button>
            ))}
          </div>
        )}
      />

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        {executiveCards.map((metric) => (
          <StatCard
            key={metric.key}
            label={metric.label}
            value={metric.value}
            accent={metric.accent}
            accentBg={metric.accentBg}
            description={metric.description}
          />
        ))}
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <RecordListPanel
          title="Top Urgent Items"
          description="The five highest-priority issues surfaced for immediate management attention."
          items={summary?.top_urgent_items ?? []}
          emptyTitle="No urgent items"
          emptyMessage="No urgent records matched the current filters."
          renderItem={(item) => (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={item.category} />
                {item.status ? <Badge value={item.status} /> : null}
                {item.priority ? <Badge value={item.priority} /> : null}
              </div>
              <p className="font-semibold text-stone-950">{item.title}</p>
              <p className="text-sm leading-6 text-stone-600">{item.reason}</p>
              <div className="flex flex-wrap gap-4 text-xs font-medium uppercase tracking-[0.08em] text-stone-500">
                <span>{humanize(item.entity_type)} #{item.entity_id}</span>
                {item.site_name ? <span>{item.site_name}</span> : null}
                {item.due_date ? <span>Due {formatDate(item.due_date)}</span> : null}
                {item.end_datetime ? <span>Ends {formatDateTime(item.end_datetime)}</span> : null}
                {item.created_at ? <span>Logged {formatDateTime(item.created_at)}</span> : null}
              </div>
            </div>
          )}
        />

        <SectionCard
          title="Compliance Snapshot"
          description="Training validity and overdue acknowledgement exposure."
        >
          <div className="space-y-4">
            <div className="rounded-lg border border-sky-100 bg-sky-50 px-4 py-4">
              <p className="text-sm font-semibold text-sky-900">Training compliance rate</p>
              <p className="mt-2 text-3xl font-semibold tracking-tight text-sky-800">
                {formatNumber(compliance?.training_compliance_rate ?? 0)}%
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Overdue Training</p>
                <p className="mt-2 text-2xl font-semibold text-stone-950">{formatNumber(compliance?.overdue_training_count ?? 0)}</p>
              </div>
              <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Expired Training</p>
                <p className="mt-2 text-2xl font-semibold text-stone-950">{formatNumber(compliance?.expired_training_count ?? 0)}</p>
              </div>
              <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Overdue Acknowledgements</p>
                <p className="mt-2 text-2xl font-semibold text-stone-950">{formatNumber(compliance?.overdue_compliance_acknowledgements_count ?? 0)}</p>
              </div>
            </div>
          </div>
        </SectionCard>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <SectionCard
          title="Safety KPI Snapshot"
          description="Hours worked and injury frequency rate calculations derived from incident classifications."
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            {[
              ['Hours Worked', summary?.kpi_snapshot?.total_hours_worked ?? 0],
              ['Recordable Incidents', summary?.kpi_snapshot?.recordable_incidents ?? 0],
              ['Lost Time Incidents', summary?.kpi_snapshot?.lost_time_incidents ?? 0],
              ['TRIFR', summary?.kpi_snapshot?.trifr ?? 0],
              ['LTIFR', summary?.kpi_snapshot?.ltifr ?? 0],
            ].map(([label, value]) => (
              <div key={label} className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3">
                <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">{label}</p>
                <p className="mt-2 text-2xl font-semibold text-stone-950">{formatNumber(value)}</p>
              </div>
            ))}
          </div>
        </SectionCard>

        <RecordListPanel
          title="Recent Safety Communications"
          description="Latest toolbox talks, alerts, posters, signage, and campaigns issued in the selected scope."
          items={summary?.communication_snapshot?.recent_communications ?? []}
          emptyTitle="No communications"
          emptyMessage="No safety communications matched the current filters."
          renderItem={(item) => (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={item.communication_type} />
                <Badge value={item.status} />
              </div>
              <p className="font-semibold text-stone-950">{item.title}</p>
              <div className="flex flex-wrap gap-4 text-sm text-stone-600">
                {item.site_name ? <span>{item.site_name}</span> : null}
                <span>{formatDateTime(item.issued_at)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <DistributionPanel
          title="Risk Level Distribution"
          description="Hazard mix across the filtered data set."
          values={risk?.risk_level_distribution}
        />
        <DistributionPanel
          title="Corrective Action Status"
          description="Where actions currently sit in the remediation lifecycle."
          values={actions?.corrective_action_status_distribution}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <SectionCard
          title="Site Risk Ranking"
          description="Sites ranked by critical and high open hazards plus pending reviews."
        >
          {risk?.top_risk_sites?.length ? (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-stone-200">
                <thead className="bg-stone-50">
                  <tr>
                    {['Site', 'Critical Open', 'High Open', 'Pending Review', 'Risk Score'].map((heading) => (
                      <th key={heading} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">
                        {heading}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-stone-100">
                  {risk.top_risk_sites.map((site, index) => (
                    <tr key={site.site_id} className={index % 2 === 0 ? 'bg-white' : 'bg-stone-50/40'}>
                      <td className="px-4 py-3 text-sm font-semibold text-stone-950">{site.site_name}</td>
                      <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.open_critical_hazards_count)}</td>
                      <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.open_high_hazards_count)}</td>
                      <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.hazards_pending_review_count)}</td>
                      <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.aggregate_risk_score)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState title="No ranked sites" message="No hazard data matched the current filters." />
          )}
        </SectionCard>

        <RecordListPanel
          title="Permit Expiry Panel"
          description="Active permit exposure and approval queue pressure."
          items={[
            {
              label: 'Active permits',
              value: permits?.active_permits_count ?? 0,
              badge: 'active',
            },
            {
              label: 'Pending permit approvals',
              value: permits?.pending_approval_permits_count ?? 0,
              badge: 'pending_approval',
            },
            {
              label: 'Permits expiring soon',
              value: permits?.expiring_soon_permits_count ?? 0,
              badge: 'warning',
            },
            {
              label: 'Expired permits',
              value: permits?.expired_permits_count ?? 0,
              badge: 'expired',
            },
          ]}
          emptyTitle="No permit summary"
          emptyMessage="Permit analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <div>
                <p className="font-semibold text-stone-950">{item.label}</p>
              </div>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <DistributionPanel
          title="Communication Type Distribution"
          description="Mix of toolbox talks, alerts, signage, posters, and campaigns."
          values={summary?.communication_snapshot?.communication_type_distribution}
        />
        <DistributionPanel
          title="Behaviour Observation Types"
          description="Balance between positive observations and issue-focused behaviour reports."
          values={summary?.behaviour_snapshot?.behaviour_observation_type_distribution}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <DistributionPanel
          title="Investigation Status Distribution"
          description="Progression of incident investigations across draft, active, approval, and closure stages."
          values={summary?.investigation_snapshot?.investigation_status_distribution}
        />
        <DistributionPanel
          title="Legal Compliance Status"
          description="Current legal register status mix across compliant, partial, and non-compliant items."
          values={summary?.legal_compliance_snapshot?.legal_compliance_status_distribution}
        />
        <DistributionPanel
          title="JSA Status Distribution"
          description="Approval and expiry state of job safety analyses in the selected scope."
          values={summary?.jsa_snapshot?.jsa_status_distribution}
        />
        <DistributionPanel
          title="Asset Condition Distribution"
          description="Condition profile for equipment, PPE, and emergency assets."
          values={summary?.asset_snapshot?.asset_condition_distribution}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <RecordListPanel
          title="Contractor Compliance Snapshot"
          description="At-a-glance summary of contractor approval and document readiness exposure."
          items={[
            {
              label: 'Contractor compliance gaps',
              value: summary?.contractor_snapshot?.contractor_compliance_gaps_count ?? 0,
              badge: 'gap',
            },
            {
              label: 'Contractors pending approval',
              value: summary?.contractor_snapshot?.contractors_pending_approval_count ?? 0,
              badge: 'pending_approval',
            },
            {
              label: 'Insurance expiring soon',
              value: summary?.contractor_snapshot?.insurance_expiring_soon_count ?? 0,
              badge: 'warning',
            },
            {
              label: 'Documents expiring soon',
              value: summary?.contractor_snapshot?.documents_expiring_soon_count ?? 0,
              badge: 'warning',
            },
          ]}
          emptyTitle="No contractor snapshot"
          emptyMessage="Contractor analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
        <RecordListPanel
          title="Asset Inspection Snapshot"
          description="Inspection and condition exposure across registered equipment and emergency assets."
          items={[
            {
              label: 'Defective assets',
              value: summary?.asset_snapshot?.defective_assets_count ?? 0,
              badge: 'defective',
            },
            {
              label: 'Inspections due soon',
              value: summary?.asset_snapshot?.assets_due_inspection_count ?? 0,
              badge: 'due_soon',
            },
            {
              label: 'Overdue inspections',
              value: summary?.asset_snapshot?.overdue_asset_inspections_count ?? 0,
              badge: 'overdue',
            },
          ]}
          emptyTitle="No asset snapshot"
          emptyMessage="Asset analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <RecordListPanel
          title="Medical Surveillance Snapshot"
          description="Due, overdue, and completed occupational health surveillance activity."
          items={[
            {
              label: 'Due surveillance',
              value: summary?.medical_surveillance_snapshot?.due_count ?? 0,
              badge: 'due',
            },
            {
              label: 'Overdue surveillance',
              value: summary?.medical_surveillance_snapshot?.overdue_count ?? 0,
              badge: 'overdue',
            },
            {
              label: 'Completed surveillance',
              value: summary?.medical_surveillance_snapshot?.completed_count ?? 0,
              badge: 'completed',
            },
          ]}
          emptyTitle="No medical snapshot"
          emptyMessage="Medical surveillance analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
        <RecordListPanel
          title="Emergency Drill Snapshot"
          description="Upcoming, overdue, and completed drill workload across the selected scope."
          items={[
            {
              label: 'Upcoming drills',
              value: summary?.emergency_drill_snapshot?.upcoming_drills_count ?? 0,
              badge: 'scheduled',
            },
            {
              label: 'Overdue drills',
              value: summary?.emergency_drill_snapshot?.overdue_drills_count ?? 0,
              badge: 'overdue',
            },
            {
              label: 'Completed drills',
              value: summary?.emergency_drill_snapshot?.completed_drills_count ?? 0,
              badge: 'completed',
            },
          ]}
          emptyTitle="No drill snapshot"
          emptyMessage="Emergency drill analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <RecordListPanel
          title="Document Control Snapshot"
          description="Approval queue and expiry exposure for controlled documents."
          items={[
            {
              label: 'Pending document approvals',
              value: summary?.document_snapshot?.pending_document_approvals_count ?? 0,
              badge: 'pending_approval',
            },
            {
              label: 'Documents expiring soon',
              value: summary?.document_snapshot?.documents_expiring_soon_count ?? 0,
              badge: 'warning',
            },
            {
              label: 'Expired documents',
              value: summary?.document_snapshot?.expired_documents_count ?? 0,
              badge: 'expired',
            },
          ]}
          emptyTitle="No document snapshot"
          emptyMessage="Document control analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
        <RecordListPanel
          title="Audit Snapshot"
          description="Open and closed audit load plus average scoring signal."
          items={[
            {
              label: 'Open audits',
              value: summary?.audit_snapshot?.open_audits_count ?? 0,
              badge: 'open',
            },
            {
              label: 'Closed audits',
              value: summary?.audit_snapshot?.closed_audits_count ?? 0,
              badge: 'closed',
            },
            {
              label: 'Average audit score',
              value: summary?.audit_snapshot?.average_audit_score ?? 0,
              badge: 'score',
            },
          ]}
          emptyTitle="No audit snapshot"
          emptyMessage="Audit analytics were not available."
          renderItem={(item) => (
            <div className="flex items-center justify-between gap-4">
              <p className="font-semibold text-stone-950">{item.label}</p>
              <div className="flex items-center gap-3">
                <Badge value={item.badge} />
                <span className="text-lg font-semibold text-stone-950">{formatNumber(item.value)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <RecordListPanel
          title="Overdue Actions"
          description="Corrective actions that have already missed their due date."
          items={actions?.overdue_corrective_actions ?? []}
          emptyTitle="No overdue actions"
          emptyMessage="No overdue corrective actions matched the current filters."
          renderItem={(item) => (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={item.status} />
                <Badge value={item.priority} />
              </div>
              <p className="font-semibold text-stone-950">{item.title}</p>
              <div className="flex flex-wrap gap-4 text-sm text-stone-600">
                {item.site_name ? <span>{item.site_name}</span> : null}
                {item.due_date ? <span>Due {formatDate(item.due_date)}</span> : null}
                {item.assigned_to_user_id ? <span>Assigned to user #{item.assigned_to_user_id}</span> : null}
              </div>
            </div>
          )}
        />

        <RecordListPanel
          title="Pending Approvals"
          description="Workflow approvals that still require an Admin or OHS Manager decision."
          items={approvals?.pending_approvals ?? []}
          emptyTitle="No pending approvals"
          emptyMessage="No approval requests are currently pending."
          renderItem={(item) => (
            <div className="space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                <Badge value={item.status} />
                <Badge value={item.action_type} />
              </div>
              <p className="font-semibold text-stone-950">{humanize(item.entity_type)} #{item.entity_id}</p>
              <div className="flex flex-wrap gap-4 text-sm text-stone-600">
                {item.site_name ? <span>{item.site_name}</span> : null}
                <span>Requested by user #{item.requested_by_user_id ?? 'Unknown'}</span>
                <span>{formatDateTime(item.created_at)}</span>
              </div>
            </div>
          )}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-3">
        <DistributionPanel
          title="Training Status Distribution"
          description="Training assignment completion and ageing."
          values={compliance?.training_status_distribution}
        />
        <DistributionPanel
          title="Acknowledgement Status Distribution"
          description="Compliance document acknowledgement progress."
          values={compliance?.compliance_acknowledgement_status_distribution}
        />
        <DistributionPanel
          title="Permit Status Distribution"
          description="Permit lifecycle across the filtered set."
          values={permits?.permit_status_distribution}
        />
        <DistributionPanel
          title="Behaviour Observation Status"
          description="Follow-up state across behaviour observation records."
          values={summary?.behaviour_snapshot?.behaviour_observation_status_distribution}
        />
      </section>

      <section className="grid gap-4 xl:grid-cols-[1.05fr_0.95fr]">
        <SectionCard
          title="Recurring Hazard Categories"
          description="Repeated hazard themes inferred from similar hazard titles."
        >
          {risk?.recurring_hazard_categories?.length ? (
            <div className="space-y-3">
              {risk.recurring_hazard_categories.map((category) => (
                <div key={category.label} className="flex items-center justify-between rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-sm">
                  <span className="font-medium text-stone-900">{humanize(category.label)}</span>
                  <span className="text-stone-600">{formatNumber(category.count)}</span>
                </div>
              ))}
            </div>
          ) : (
            <EmptyState title="No recurring categories" message="No repeated hazard themes were identified in the current data set." />
          )}
        </SectionCard>

        <SectionCard
          title="Trend Panels"
          description="Simple month-over-month views for key operational signals."
        >
          <div className="space-y-4">
            {[
              ['Incidents', trends?.incidents_by_month],
              ['Hazards', trends?.hazards_by_month],
              ['Inspections', trends?.inspections_by_month],
              ['Actions Closed', trends?.corrective_actions_closed_by_month],
              ['Communications', trends?.safety_communications_by_month],
              ['Behaviour Observations', trends?.behaviour_observations_by_month],
              ['Emergency Drills', trends?.emergency_drills_by_month],
              ['Audits', trends?.audits_by_month],
              ['TRIFR', trends?.trifr_by_month],
              ['LTIFR', trends?.ltifr_by_month],
            ].map(([label, values]) => (
              <div key={label} className="rounded-lg border border-stone-200 bg-stone-50 p-4">
                <p className="text-sm font-semibold text-stone-900">{label}</p>
                <div className="mt-3 space-y-2">
                  {Object.entries(values ?? {}).length ? (
                    Object.entries(values).map(([month, value]) => (
                      <div key={month} className="flex items-center justify-between rounded-md bg-white px-3 py-2 text-sm">
                        <span className="text-stone-600">{month}</span>
                        <span className="font-medium text-stone-950">{formatNumber(value)}</span>
                      </div>
                    ))
                  ) : (
                    <p className="text-sm text-stone-500">No trend data available.</p>
                  )}
                </div>
              </div>
            ))}
          </div>
        </SectionCard>
      </section>

      <SectionCard
        title="Site Operational Summaries"
        description="Site-level rollup of incidents, hazards, inspections, overdue actions, hours worked, communications, and behaviour observations."
      >
        {siteSummaries.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-stone-200">
              <thead className="bg-stone-50">
                <tr>
                  {['Site', 'Incidents', 'Open Hazards', 'Critical Hazards', 'Inspections', 'Overdue Actions', 'Hours Worked', 'Communications', 'Behaviour Obs.'].map((heading) => (
                    <th key={heading} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-stone-100">
                {siteSummaries.map((site, index) => (
                  <tr key={site.site_id} className={index % 2 === 0 ? 'bg-white' : 'bg-stone-50/40'}>
                    <td className="px-4 py-3 text-sm font-semibold text-stone-950">{site.site_name}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.incidents_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.open_hazards_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.critical_hazards_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.inspections_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.overdue_corrective_actions_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.hours_worked)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.safety_communications_count)}</td>
                    <td className="px-4 py-3 text-sm text-stone-700">{formatNumber(site.behaviour_observations_count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No site summaries" message="No site-level records matched the current filters." />
        )}
      </SectionCard>
    </div>
  )
}
