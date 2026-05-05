import { Camera, Send } from 'lucide-react'
import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client.js'
import { ErrorState } from '../components/ErrorState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { PageHeader } from '../components/PageHeader.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { canAccessQuickReport, isForbiddenError } from '../lib/rbac.js'

const REPORT_TYPES = [
  { value: 'incident', label: 'Incident' },
  { value: 'hazard', label: 'Hazard' },
  { value: 'observation', label: 'Observation' },
]

function buildPayload(reportType, values) {
  if (reportType === 'incident') {
    return {
      site_id: Number(values.site_id),
      title: values.title.trim(),
      description: values.description.trim(),
      severity: 'medium',
      status: 'open',
      occurred_at: new Date().toISOString(),
      is_recordable: false,
      is_lost_time: false,
      attachments_metadata: [],
    }
  }

  if (reportType === 'hazard') {
    return {
      site_id: Number(values.site_id),
      title: values.title.trim(),
      description: values.description.trim(),
      likelihood: 3,
      impact: 3,
      status: 'open',
      existing_controls: [],
      additional_controls: [],
      attachments_metadata: [],
      owner_user_id: null,
    }
  }

  return {
    site_id: Number(values.site_id),
    title: values.title.trim(),
    description: values.description.trim(),
    observation_type: 'event_safety_observation',
    status: 'open',
    severity: 'medium',
    action_required: false,
    observed_at: new Date().toISOString(),
    attachments_metadata: [],
  }
}

function entityConfig(reportType) {
  if (reportType === 'incident') {
    return { endpoint: '/incidents', entityType: 'incident' }
  }
  if (reportType === 'hazard') {
    return { endpoint: '/hazards', entityType: 'hazard' }
  }
  return { endpoint: '/behaviour-observations', entityType: 'behaviour_observation' }
}

export function QuickReportPage() {
  const { token, user, assignedSiteId } = useAuth()
  const [sites, setSites] = useState([])
  const [reportType, setReportType] = useState('incident')
  const [values, setValues] = useState({
    site_id: assignedSiteId ? String(assignedSiteId) : '',
    title: '',
    description: '',
    photo: null,
  })
  const [successMessage, setSuccessMessage] = useState('')
  const [error, setError] = useState(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  useEffect(() => {
    let ignore = false

    async function loadSites() {
      try {
        const response = await apiClient.getCollection(token, '/sites')
        if (!ignore) {
          setSites(response)
          if (!values.site_id && response.length === 1) {
            setValues((current) => ({ ...current, site_id: String(response[0].id) }))
          }
        }
      } catch (requestError) {
        if (!ignore) {
          setError(requestError)
        }
      }
    }

    loadSites()

    return () => {
      ignore = true
    }
  }, [token])

  const selectedSiteId = useMemo(
    () => values.site_id || (assignedSiteId ? String(assignedSiteId) : ''),
    [assignedSiteId, values.site_id],
  )

  async function handleSubmit(event) {
    event.preventDefault()
    setIsSubmitting(true)
    setError(null)
    setSuccessMessage('')

    try {
      const payload = buildPayload(reportType, { ...values, site_id: selectedSiteId })
      const config = entityConfig(reportType)
      const created = await apiClient.createRecord(token, config.endpoint, payload)
      if (values.photo) {
        await apiClient.uploadAttachment(token, config.entityType, created.id, {
          file: values.photo,
          description: 'Quick report photo',
        })
      }
      setSuccessMessage(`${REPORT_TYPES.find((item) => item.value === reportType)?.label} submitted successfully.`)
      setValues((current) => ({
        ...current,
        title: '',
        description: '',
        photo: null,
      }))
    } catch (requestError) {
      setError(requestError)
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!canAccessQuickReport(user)) {
    return <NotAuthorizedState />
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        eyebrow="Mobile"
        title="Quick Report"
        description="Capture an incident, hazard, or observation with the fewest possible steps. Designed to work cleanly on smaller screens."
      />

      {successMessage ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          {successMessage}
        </div>
      ) : null}

      {error ? (
        isForbiddenError(error)
          ? <NotAuthorizedState />
          : <ErrorState message={error.message ?? 'Unable to submit quick report'} />
      ) : null}

      <form onSubmit={handleSubmit} className="space-y-5 rounded-2xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
        <div className="grid gap-3 sm:grid-cols-3">
          {REPORT_TYPES.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => setReportType(option.value)}
              className={[
                'rounded-xl border px-4 py-4 text-left text-sm transition',
                reportType === option.value
                  ? 'border-emerald-500 bg-emerald-50 text-emerald-900 shadow-sm'
                  : 'border-stone-200 bg-stone-50 text-stone-700 hover:bg-stone-100',
              ].join(' ')}
            >
              <span className="block font-semibold">{option.label}</span>
              <span className="mt-1 block text-xs text-stone-500">Fast capture</span>
            </button>
          ))}
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Site</span>
            <select
              value={selectedSiteId}
              onChange={(event) => setValues((current) => ({ ...current, site_id: event.target.value }))}
              disabled={Boolean(assignedSiteId)}
              className="mt-2 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200 disabled:bg-stone-100"
            >
              <option value="">Select a site</option>
              {sites.map((site) => (
                <option key={site.id} value={String(site.id)}>
                  {site.name}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-sm">
            <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Title</span>
            <input
              value={values.title}
              onChange={(event) => setValues((current) => ({ ...current, title: event.target.value }))}
              placeholder={`Short ${reportType} title`}
              className="mt-2 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
            />
          </label>
        </div>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Description</span>
          <textarea
            rows={6}
            value={values.description}
            onChange={(event) => setValues((current) => ({ ...current, description: event.target.value }))}
            placeholder="What happened, where, and what needs attention?"
            className="mt-2 w-full rounded-md border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 shadow-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-200"
          />
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">Photo</span>
          <div className="mt-2 flex items-center gap-3 rounded-xl border border-dashed border-stone-300 bg-stone-50 px-4 py-4">
            <Camera className="size-5 text-stone-500" />
            <input
              type="file"
              accept="image/*"
              onChange={(event) => setValues((current) => ({ ...current, photo: event.target.files?.[0] ?? null }))}
              className="min-w-0 flex-1 text-sm text-stone-700 file:mr-3 file:rounded-md file:border-0 file:bg-emerald-600 file:px-3 file:py-2 file:text-sm file:font-semibold file:text-white hover:file:bg-emerald-700"
            />
          </div>
        </label>

        <button
          type="submit"
          disabled={isSubmitting || !selectedSiteId || !values.title.trim() || !values.description.trim()}
          className="inline-flex w-full items-center justify-center gap-2 rounded-xl bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:bg-emerald-300"
        >
          <Send className="size-4" />
          {isSubmitting ? 'Submitting...' : 'Submit Quick Report'}
        </button>
      </form>
    </div>
  )
}
