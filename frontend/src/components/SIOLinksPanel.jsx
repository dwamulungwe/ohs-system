import { ArrowUpRight, Plus } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiClient } from '../api/client.js'
import { canCreateResource, canEditRecord } from '../lib/rbac.js'

const LINK_TYPES = [
  {
    key: 'hazard',
    label: 'Hazard',
    resourceKey: 'hazards',
    idField: 'linked_hazard_id',
    route: '/hazards',
    endpoint: 'create-hazard',
    description: 'Create a risk-ranked hazard using the SIO description and urgency.',
  },
  {
    key: 'incident',
    label: 'Incident',
    resourceKey: 'incidents',
    idField: 'linked_incident_id',
    route: '/incidents',
    endpoint: 'create-incident',
    description: 'Create an incident when the observation represents an event requiring investigation.',
  },
  {
    key: 'corrective-action',
    label: 'Corrective Action',
    resourceKey: 'corrective-actions',
    idField: 'linked_corrective_action_id',
    route: '/corrective-actions',
    endpoint: 'create-corrective-action',
    description: 'Create a tracked action assigned to the mapped responsible person.',
  },
]

export function SIOLinksPanel({ item, token, user, onUpdated }) {
  const [busyKey, setBusyKey] = useState('')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const canEscalate = canEditRecord('sios', user, item)

  async function createLink(linkType) {
    setBusyKey(linkType.key)
    setMessage('')
    setError('')
    try {
      const updated = await apiClient.createRecord(
        token,
        `/sios/${item.id}/${linkType.endpoint}`,
        {},
      )
      onUpdated(updated)
      setMessage(`${linkType.label} created and linked.`)
    } catch (requestError) {
      setError(requestError.message ?? `Unable to create ${linkType.label.toLowerCase()}.`)
    } finally {
      setBusyKey('')
    }
  }

  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <h2 className="text-base font-semibold tracking-tight text-stone-950">Operational Links</h2>
      <p className="mt-1 text-sm leading-6 text-stone-600">
        Historical observations remain SIOs. Create an operational record only when follow-up is required.
      </p>
      {message ? <p className="mt-3 rounded-lg bg-emerald-50 px-3 py-2 text-sm text-emerald-800">{message}</p> : null}
      {error ? <p className="mt-3 rounded-lg bg-rose-50 px-3 py-2 text-sm text-rose-800">{error}</p> : null}
      <div className="mt-4 grid gap-3 md:grid-cols-3">
        {LINK_TYPES.map((linkType) => {
          const linkedId = item[linkType.idField]
          const permitted = canEscalate && canCreateResource(linkType.resourceKey, user)
          return (
            <div key={linkType.key} className="rounded-lg border border-stone-200 bg-stone-50 p-4">
              <p className="font-semibold text-stone-950">{linkType.label}</p>
              <p className="mt-1 text-sm leading-5 text-stone-600">{linkType.description}</p>
              {linkedId ? (
                <Link
                  to={`${linkType.route}/${linkedId}`}
                  className="mt-4 inline-flex items-center gap-2 text-sm font-semibold text-emerald-700 hover:text-emerald-800"
                >
                  Open linked record #{linkedId}
                  <ArrowUpRight className="size-4" />
                </Link>
              ) : permitted ? (
                <button
                  type="button"
                  onClick={() => createLink(linkType)}
                  disabled={Boolean(busyKey)}
                  className="mt-4 inline-flex items-center gap-2 rounded-md bg-emerald-600 px-3 py-2 text-sm font-semibold text-white hover:bg-emerald-700 disabled:opacity-60"
                >
                  <Plus className="size-4" />
                  {busyKey === linkType.key ? 'Creating…' : `Create ${linkType.label}`}
                </button>
              ) : (
                <p className="mt-4 text-xs text-stone-500">No linked record.</p>
              )}
            </div>
          )
        })}
      </div>
    </section>
  )
}
