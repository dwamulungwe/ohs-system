import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client.js'
import { ErrorState } from '../components/ErrorState.jsx'
import { LoadingState } from '../components/LoadingState.jsx'
import { NotAuthorizedState } from '../components/NotAuthorizedState.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { hasRole, ROLES } from '../lib/rbac.js'

function prettyLabel(value) {
  return value.replaceAll('_', ' ').replace(/\b\w/g, (letter) => letter.toUpperCase())
}

function stringify(value) {
  return JSON.stringify(value ?? {}, null, 2)
}

export function OrganisationAdministrationPage({ platform = false }) {
  const { token, user } = useAuth()
  const [organisations, setOrganisations] = useState([])
  const [selectedId, setSelectedId] = useState(user?.organisation_id ?? null)
  const [features, setFeatures] = useState([])
  const [settings, setSettings] = useState(null)
  const [settingsDraft, setSettingsDraft] = useState({})
  const [isLoading, setIsLoading] = useState(true)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [createDraft, setCreateDraft] = useState({ name: '', code: '', slug: '' })

  const authorized = platform
    ? Boolean(user?.is_platform_admin)
    : Boolean(user?.is_platform_admin || hasRole(user, [ROLES.ADMIN]))
  const selectedOrganisation = useMemo(
    () => organisations.find((item) => item.id === Number(selectedId)) ?? user?.organisation,
    [organisations, selectedId, user],
  )

  useEffect(() => {
    if (!authorized) {
      setIsLoading(false)
      return
    }
    let ignore = false
    async function load() {
      setIsLoading(true)
      setError('')
      try {
        if (platform) {
          const rows = await apiClient.getOrganisations(token)
          if (ignore) return
          setOrganisations(rows)
          setSelectedId((current) => current ?? rows[0]?.id ?? null)
        } else {
          setOrganisations(user?.organisation ? [user.organisation] : [])
          setSelectedId(user?.organisation_id ?? null)
        }
      } catch (loadError) {
        if (!ignore) setError(loadError.message)
      } finally {
        if (!ignore) setIsLoading(false)
      }
    }
    load()
    return () => { ignore = true }
  }, [authorized, platform, token, user])

  useEffect(() => {
    if (!authorized || !selectedId) return
    let ignore = false
    async function loadDetail() {
      setError('')
      try {
        const [nextSettings, nextFeatures] = await Promise.all([
          apiClient.getOrganisationSettings(token, selectedId),
          platform
            ? apiClient.getOrganisationFeatures(token, selectedId)
            : Promise.resolve((user?.enabled_modules ?? []).map((key) => ({ key, is_enabled: true, configuration: {} }))),
        ])
        if (ignore) return
        setSettings(nextSettings)
        setSettingsDraft({
          permit_expiry_warning_days: String(nextSettings.permit_expiry_warning_days),
          branding: stringify(nextSettings.branding),
          terminology: stringify(nextSettings.terminology),
          dashboard_preferences: stringify(nextSettings.dashboard_preferences),
          notification_preferences: stringify(nextSettings.notification_preferences),
          numbering_prefixes: stringify(nextSettings.numbering_prefixes),
          sio_workflow_configuration: stringify(nextSettings.sio_workflow_configuration),
        })
        setFeatures(nextFeatures)
      } catch (loadError) {
        if (!ignore) setError(loadError.message)
      }
    }
    loadDetail()
    return () => { ignore = true }
  }, [authorized, platform, selectedId, token, user])

  if (!authorized) return <NotAuthorizedState />
  if (isLoading) return <LoadingState label="Loading organisation administration..." />
  if (error && !settings) return <ErrorState message={error} />

  async function createOrganisation(event) {
    event.preventDefault()
    setIsSaving(true)
    setError('')
    try {
      const created = await apiClient.createOrganisation(token, {
        ...createDraft,
        timezone: 'Africa/Lusaka',
        is_active: true,
      })
      setOrganisations((current) => [...current, created].sort((a, b) => a.name.localeCompare(b.name)))
      setSelectedId(created.id)
      setCreateDraft({ name: '', code: '', slug: '' })
      setNotice('Organisation created with isolated roles, settings, and module entitlements.')
    } catch (saveError) {
      setError(saveError.message)
    } finally {
      setIsSaving(false)
    }
  }

  async function saveFeatures() {
    setIsSaving(true)
    setError('')
    try {
      const updated = await apiClient.updateOrganisationFeatures(token, selectedId, features)
      setFeatures(updated)
      setNotice('Module entitlements updated.')
    } catch (saveError) {
      setError(saveError.message)
    } finally {
      setIsSaving(false)
    }
  }

  async function saveSettings(event) {
    event.preventDefault()
    setIsSaving(true)
    setError('')
    try {
      const payload = {
        permit_expiry_warning_days: Number(settingsDraft.permit_expiry_warning_days),
        branding: JSON.parse(settingsDraft.branding || '{}'),
        terminology: JSON.parse(settingsDraft.terminology || '{}'),
        dashboard_preferences: JSON.parse(settingsDraft.dashboard_preferences || '{}'),
        notification_preferences: JSON.parse(settingsDraft.notification_preferences || '{}'),
        numbering_prefixes: JSON.parse(settingsDraft.numbering_prefixes || '{}'),
        sio_workflow_configuration: JSON.parse(settingsDraft.sio_workflow_configuration || '{}'),
      }
      const updated = await apiClient.updateOrganisationSettings(token, selectedId, payload)
      setSettings(updated)
      setNotice('Organisation settings updated.')
    } catch (saveError) {
      setError(saveError instanceof SyntaxError ? 'Settings JSON is not valid.' : saveError.message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <p className="text-sm font-medium text-emerald-700">{platform ? 'Platform Administration' : 'Tenant Administration'}</p>
        <h2 className="mt-1 text-2xl font-semibold text-stone-950">{platform ? 'Organisations' : 'Organisation Settings'}</h2>
        <p className="mt-2 text-sm text-stone-600">Manage tenant identity, module access, and configurable operating preferences.</p>
      </div>

      {error ? <ErrorState message={error} /> : null}
      {notice ? <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800">{notice}</div> : null}

      {platform ? (
        <form onSubmit={createOrganisation} className="grid gap-3 rounded-xl border border-stone-200 bg-white p-4 shadow-sm md:grid-cols-4">
          <input required minLength={2} placeholder="Organisation name" value={createDraft.name} onChange={(event) => setCreateDraft((current) => ({ ...current, name: event.target.value }))} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" />
          <input required minLength={2} placeholder="Code" value={createDraft.code} onChange={(event) => setCreateDraft((current) => ({ ...current, code: event.target.value.toUpperCase() }))} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" />
          <input required minLength={2} placeholder="slug" value={createDraft.slug} onChange={(event) => setCreateDraft((current) => ({ ...current, slug: event.target.value.toLowerCase().replace(/[^a-z0-9-]+/g, '-') }))} className="rounded-lg border border-stone-300 px-3 py-2 text-sm" />
          <button disabled={isSaving} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Create organisation</button>
        </form>
      ) : null}

      <div className="grid gap-6 xl:grid-cols-[280px_minmax(0,1fr)]">
        {platform ? (
          <div className="space-y-2 rounded-xl border border-stone-200 bg-white p-3 shadow-sm">
            {organisations.map((organisation) => (
              <button key={organisation.id} type="button" onClick={() => setSelectedId(organisation.id)} className={`w-full rounded-lg px-3 py-3 text-left text-sm ${Number(selectedId) === organisation.id ? 'bg-emerald-100 text-emerald-950' : 'hover:bg-stone-100'}`}>
                <span className="block font-semibold">{organisation.name}</span>
                <span className="mt-1 block text-xs opacity-70">{organisation.code} · {organisation.slug}</span>
              </button>
            ))}
          </div>
        ) : null}

        <div className="space-y-6">
          <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
            <p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Organisation Detail</p>
            <h3 className="mt-2 text-xl font-semibold text-stone-950">{selectedOrganisation?.name}</h3>
            <p className="mt-1 text-sm text-stone-600">{selectedOrganisation?.code} · {selectedOrganisation?.timezone}</p>
          </section>

          {platform ? (
            <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Modules / Features</p><h3 className="mt-1 text-lg font-semibold">Entitlements</h3></div>
                <button type="button" disabled={isSaving} onClick={saveFeatures} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Save modules</button>
              </div>
              <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {features.map((feature, index) => (
                  <label key={feature.key} className="flex items-center gap-3 rounded-lg border border-stone-200 p-3 text-sm">
                    <input type="checkbox" checked={feature.is_enabled} onChange={(event) => setFeatures((current) => current.map((item, itemIndex) => itemIndex === index ? { ...item, is_enabled: event.target.checked } : item))} />
                    {prettyLabel(feature.key)}
                  </label>
                ))}
              </div>
            </section>
          ) : null}

          {settings ? (
            <form onSubmit={saveSettings} className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm">
              <div className="flex items-center justify-between gap-4">
                <div><p className="text-xs font-semibold uppercase tracking-wide text-stone-500">Settings</p><h3 className="mt-1 text-lg font-semibold">Organisation preferences</h3></div>
                <button disabled={isSaving} className="rounded-lg bg-emerald-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50">Save settings</button>
              </div>
              <label className="mt-4 block text-sm font-medium">Permit expiry warning days<input type="number" min="1" max="365" value={settingsDraft.permit_expiry_warning_days ?? ''} onChange={(event) => setSettingsDraft((current) => ({ ...current, permit_expiry_warning_days: event.target.value }))} className="mt-1 block w-full rounded-lg border border-stone-300 px-3 py-2" /></label>
              <div className="mt-4 grid gap-4 lg:grid-cols-2">
                {['branding', 'terminology', 'dashboard_preferences', 'notification_preferences', 'numbering_prefixes', 'sio_workflow_configuration'].map((key) => (
                  <label key={key} className="block text-sm font-medium">{prettyLabel(key)} (JSON)<textarea rows={6} value={settingsDraft[key] ?? '{}'} onChange={(event) => setSettingsDraft((current) => ({ ...current, [key]: event.target.value }))} className="mt-1 block w-full rounded-lg border border-stone-300 px-3 py-2 font-mono text-xs" /></label>
                ))}
              </div>
            </form>
          ) : null}
        </div>
      </div>
    </div>
  )
}
