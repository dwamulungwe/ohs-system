import { CheckCircle2, FileSpreadsheet, Upload } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { apiClient } from '../api/client.js'
import { Badge } from '../components/Badge.jsx'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDateTime, formatNumber } from '../lib/formatters.js'
import { canViewResource, isForbiddenError } from '../lib/rbac.js'

function ReportCard({ label, value, tone = 'stone' }) {
  const colors = {
    stone: 'border-stone-200 bg-stone-50 text-stone-900',
    green: 'border-emerald-200 bg-emerald-50 text-emerald-900',
    amber: 'border-amber-200 bg-amber-50 text-amber-900',
    red: 'border-rose-200 bg-rose-50 text-rose-900',
  }
  return (
    <div className={`rounded-lg border p-4 ${colors[tone]}`}>
      <p className="text-xs font-semibold uppercase tracking-[0.08em] opacity-70">{label}</p>
      <p className="mt-1 text-2xl font-semibold">{formatNumber(value ?? 0)}</p>
    </div>
  )
}

function DiagnosticList({ title, values, tone = 'amber' }) {
  if (!values?.length) return null
  const colors = tone === 'red'
    ? 'border-rose-200 bg-rose-50 text-rose-950'
    : 'border-amber-200 bg-amber-50 text-amber-950'
  const visible = values.slice(0, 20)
  return (
    <div className={`rounded-lg border p-4 ${colors}`}>
      <h3 className="font-semibold">{title} ({formatNumber(values.length)})</h3>
      <p className="mt-2 text-sm leading-6">{visible.join(' · ')}{values.length > visible.length ? ` · +${formatNumber(values.length - visible.length)} more` : ''}</p>
    </div>
  )
}

export function DataImportsPage() {
  const { token, user } = useAuth()
  const [file, setFile] = useState(null)
  const [preview, setPreview] = useState(null)
  const [jobs, setJobs] = useState([])
  const [sites, setSites] = useState([])
  const [siteMappings, setSiteMappings] = useState({})
  const [createSites, setCreateSites] = useState([])
  const [isLoading, setIsLoading] = useState(true)
  const [isPreviewing, setIsPreviewing] = useState(false)
  const [isConfirming, setIsConfirming] = useState(false)
  const [error, setError] = useState(null)
  const [message, setMessage] = useState('')

  const loadReferences = useCallback(async () => {
    setIsLoading(true)
    setError(null)
    try {
      const [jobResponse, siteResponse] = await Promise.all([
        apiClient.getList(token, '/data-imports', { skip: 0, limit: 25 }),
        apiClient.getCollection(token, '/sites'),
      ])
      setJobs(jobResponse.items)
      setSites(siteResponse)
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsLoading(false)
    }
  }, [token])

  useEffect(() => {
    if (canViewResource('data-imports', user)) loadReferences()
    else setIsLoading(false)
  }, [loadReferences, user])

  async function handlePreview(event) {
    event.preventDefault()
    if (!file) {
      setError(new Error('Select an .xlsx workbook first.'))
      return
    }
    setIsPreviewing(true)
    setError(null)
    setMessage('')
    try {
      const response = await apiClient.previewDataImport(token, file)
      setPreview(response)
      setSiteMappings(response.report?.site_mappings ?? {})
      setCreateSites([])
      setMessage('Dry-run preview complete. No SIO records have been written.')
      await loadReferences()
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsPreviewing(false)
    }
  }

  function toggleCreateSite(siteName, checked) {
    setCreateSites((current) =>
      checked
        ? [...new Set([...current, siteName])]
        : current.filter((name) => name !== siteName),
    )
    if (checked) {
      setSiteMappings((current) => ({ ...current, [siteName]: '' }))
    }
  }

  async function handleConfirm() {
    if (!preview) return
    const unresolved = preview.report?.unresolved_sites ?? []
    const stillUnresolved = unresolved.filter(
      (name) => !siteMappings[name] && !createSites.includes(name),
    )
    if (stillUnresolved.length) {
      setError(new Error(`Resolve these sites before importing: ${stillUnresolved.join(', ')}`))
      return
    }
    setIsConfirming(true)
    setError(null)
    setMessage('')
    try {
      const mappings = Object.fromEntries(
        Object.entries(siteMappings)
          .filter(([, value]) => value)
          .map(([name, value]) => [name, Number(value)]),
      )
      const response = await apiClient.confirmDataImport(token, preview.id, {
        site_mappings: mappings,
        create_sites: createSites,
      })
      setPreview(response)
      setMessage(`Import finished: ${response.successful_rows} rows imported.`)
      await loadReferences()
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsConfirming(false)
    }
  }

  if (!canViewResource('data-imports', user)) return <NotAuthorizedState />
  if (isLoading && !preview) return <LoadingState title="Loading data imports" message="Fetching import history and site mappings." />

  const report = preview?.report
  const canConfirm = preview?.status === 'previewed'

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Administration"
        title="Data Imports"
        description="Validate first, resolve site mappings, then explicitly confirm. Uploading a workbook never imports records by itself."
      />

      {message ? <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">{message}</div> : null}
      {error ? (isForbiddenError(error) ? <NotAuthorizedState /> : <ErrorState message={error.message ?? 'Import request failed'} />) : null}

      <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
        <div className="flex items-start gap-3">
          <div className="rounded-lg bg-emerald-100 p-2 text-emerald-700"><FileSpreadsheet className="size-5" /></div>
          <div>
            <h2 className="font-semibold text-stone-950">Yalelo historical SIO workbook</h2>
            <p className="mt-1 text-sm leading-6 text-stone-600">Accepts the exact 21-column Yalelo .xlsx format. Maximum file size is 10 MB.</p>
          </div>
        </div>
        <form onSubmit={handlePreview} className="mt-5 flex flex-col gap-3 sm:flex-row sm:items-end">
          <label className="block flex-1 text-sm font-medium text-stone-700">
            Excel workbook
            <input
              type="file"
              accept=".xlsx,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
              className="mt-2 block w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm file:mr-3 file:rounded-md file:border-0 file:bg-stone-100 file:px-3 file:py-2 file:font-medium"
            />
          </label>
          <button
            type="submit"
            disabled={isPreviewing}
            className="inline-flex items-center justify-center gap-2 rounded-md bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
          >
            <Upload className="size-4" />
            {isPreviewing ? 'Validating…' : 'Preview import'}
          </button>
        </form>
      </section>

      {report ? (
        <section className="space-y-4 rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h2 className="font-semibold text-stone-950">Import report · {preview.original_filename}</h2>
              <p className="mt-1 text-sm text-stone-600">Job #{preview.id} · <Badge value={preview.status} /></p>
            </div>
            {preview.is_dry_run ? <span className="rounded-full bg-sky-100 px-3 py-1 text-xs font-semibold uppercase tracking-wide text-sky-800">Dry run — no records written</span> : null}
          </div>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
            <ReportCard label="Detected" value={report.rows_detected} />
            <ReportCard label="Valid" value={report.rows_valid} tone="green" />
            <ReportCard label="Imported" value={report.rows_imported} tone="green" />
            <ReportCard label="Duplicates" value={report.duplicates_skipped} tone="amber" />
            <ReportCard label="Failed" value={report.rows_failed} tone="red" />
          </div>

          {report.unresolved_sites?.length ? (
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <h3 className="font-semibold text-amber-950">Resolve source sites</h3>
              <div className="mt-3 space-y-3">
                {report.unresolved_sites.map((siteName) => (
                  <div key={siteName} className="grid gap-2 rounded-lg bg-white p-3 sm:grid-cols-[1fr_1.5fr_auto] sm:items-center">
                    <span className="text-sm font-medium text-stone-900">{siteName}</span>
                    <select
                      value={siteMappings[siteName] ?? ''}
                      disabled={createSites.includes(siteName)}
                      onChange={(event) => setSiteMappings((current) => ({ ...current, [siteName]: event.target.value }))}
                      className="rounded-md border border-stone-300 bg-white px-3 py-2 text-sm disabled:bg-stone-100"
                    >
                      <option value="">Map to an existing site…</option>
                      {sites.map((site) => <option key={site.id} value={site.id}>{site.name} ({site.code})</option>)}
                    </select>
                    <label className="inline-flex items-center gap-2 text-sm text-stone-700">
                      <input type="checkbox" checked={createSites.includes(siteName)} onChange={(event) => toggleCreateSite(siteName, event.target.checked)} />
                      Create site
                    </label>
                  </div>
                ))}
              </div>
            </div>
          ) : null}

          <div className="grid gap-3 lg:grid-cols-2">
            <DiagnosticList title="Unresolved originating departments" values={report.unresolved_departments} />
            <DiagnosticList title="Unresolved responsible departments" values={report.unresolved_responsible_departments} />
            <DiagnosticList title="Resolved exact user matches" values={report.resolved_users} />
            <DiagnosticList title="Unresolved user/person names" values={report.unresolved_users} />
            <DiagnosticList title="Ambiguous exact user matches" values={report.ambiguous_users} tone="red" />
            <DiagnosticList title="Unexpected statuses" values={report.unexpected_statuses} tone="red" />
            <DiagnosticList title="Unexpected urgency values" values={report.unexpected_urgency_values} tone="red" />
            <DiagnosticList title="Unexpected classifications" values={report.unexpected_classifications} tone="red" />
            <DiagnosticList title="Additional workbook columns" values={report.column_contract?.additional_columns} />
            <DiagnosticList title="Completely empty workbook columns" values={report.column_contract?.completely_empty_columns} />
          </div>

          {report.malformed_dates?.length ? (
            <div className="rounded-lg border border-rose-200 bg-rose-50 p-4 text-sm text-rose-950">
              <h3 className="font-semibold">Malformed dates ({formatNumber(report.malformed_dates.length)})</h3>
              <p className="mt-2">{report.malformed_dates.slice(0, 10).map((item) => `row ${item.row_number} ${item.field}: ${item.value ?? 'blank'}`).join(' · ')}</p>
            </div>
          ) : null}

          {report.failure_reasons?.length ? (
            <div className="max-h-64 overflow-auto rounded-lg border border-rose-200">
              <table className="w-full text-left text-sm">
                <thead className="sticky top-0 bg-rose-50 text-rose-900"><tr><th className="px-3 py-2">Row</th><th className="px-3 py-2">Field</th><th className="px-3 py-2">Reason</th></tr></thead>
                <tbody>{report.failure_reasons.map((reason, index) => <tr key={`${reason.row_number}-${index}`} className="border-t border-rose-100"><td className="px-3 py-2">{reason.row_number ?? '—'}</td><td className="px-3 py-2">{reason.field ?? '—'}</td><td className="px-3 py-2">{reason.message}</td></tr>)}</tbody>
              </table>
            </div>
          ) : null}

          {canConfirm ? (
            <div className="flex justify-end border-t border-stone-200 pt-4">
              <button
                type="button"
                onClick={handleConfirm}
                disabled={isConfirming}
                className="inline-flex items-center gap-2 rounded-md bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
              >
                <CheckCircle2 className="size-4" />
                {isConfirming ? 'Importing…' : 'Confirm import'}
              </button>
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
        <h2 className="font-semibold text-stone-950">Import history</h2>
        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-stone-50 text-xs uppercase tracking-wide text-stone-500"><tr><th className="px-3 py-2">File</th><th className="px-3 py-2">Status</th><th className="px-3 py-2">Rows</th><th className="px-3 py-2">Imported</th><th className="px-3 py-2">Failed</th><th className="px-3 py-2">Created</th></tr></thead>
            <tbody>{jobs.map((job) => <tr key={job.id} className="border-t border-stone-200"><td className="px-3 py-3 font-medium text-stone-900">{job.original_filename}</td><td className="px-3 py-3"><Badge value={job.status} /></td><td className="px-3 py-3">{formatNumber(job.total_rows)}</td><td className="px-3 py-3">{formatNumber(job.successful_rows)}</td><td className="px-3 py-3">{formatNumber(job.failed_rows)}</td><td className="px-3 py-3 text-stone-600">{formatDateTime(job.created_at)}</td></tr>)}</tbody>
          </table>
          {!jobs.length ? <p className="py-8 text-center text-sm text-stone-500">No import jobs yet.</p> : null}
        </div>
      </section>
    </div>
  )
}
