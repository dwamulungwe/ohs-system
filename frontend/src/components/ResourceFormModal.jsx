import { useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { canUseUserReferences } from '../lib/rbac.js'
import { Modal } from './Modal.jsx'

function extractErrorMessage(error) {
  if (typeof error?.payload?.detail === 'string') {
    return error.payload.detail
  }

  if (Array.isArray(error?.payload?.detail)) {
    return error.payload.detail.map((entry) => entry.msg).join(', ')
  }

  return error?.message ?? 'Unable to save record.'
}

function buildOptions(field, references) {
  if (field.optionsSource === 'sites') {
    return (references.sites ?? []).map((site) => ({
      value: String(site.id),
      label: `${site.name} (${site.code})`,
    }))
  }

  if (field.optionsSource === 'users') {
    return (references.users ?? []).map((user) => ({
      value: String(user.id),
      label: `${user.full_name} (${user.email})`,
    }))
  }

  if (field.optionsSource === 'roles') {
    return (references.roles ?? []).map((role) => ({
      value: String(role.id),
      label: role.name.replaceAll('_', ' '),
    }))
  }

  return field.options ?? []
}

function normalizeFieldValue(field, value) {
  if (field.type === 'checkbox') {
    return Boolean(value)
  }

  return value ?? ''
}

function FieldControl({ field, value, onChange, options, error }) {
  const commonClassName = [
    'mt-2 w-full rounded-lg border bg-white px-3 py-2.5 text-sm text-stone-900 outline-none transition',
    error
      ? 'border-rose-300 focus:border-rose-500 focus:ring-4 focus:ring-rose-500/10'
      : 'border-stone-300 focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10',
  ].join(' ')

  if (field.type === 'textarea') {
    return (
      <textarea
        value={value}
        onChange={(event) => onChange(field.name, event.target.value)}
        rows={field.rows ?? 4}
        className={commonClassName}
      />
    )
  }

  if (field.type === 'select') {
    return (
      <select
        value={value}
        onChange={(event) => onChange(field.name, event.target.value)}
        className={commonClassName}
      >
        <option value="">Select an option</option>
        {options.map((option) => (
          <option key={`${field.name}-${option.value}`} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    )
  }

  if (field.type === 'checkbox') {
    return (
      <label className="mt-3 inline-flex items-center gap-3">
        <input
          type="checkbox"
          checked={Boolean(value)}
          onChange={(event) => onChange(field.name, event.target.checked)}
          className="size-4 rounded border-stone-300 text-emerald-600 focus:ring-emerald-500"
        />
        <span className="text-sm text-stone-700">{field.checkboxLabel ?? field.label}</span>
      </label>
    )
  }

  return (
    <input
      type={field.type}
      value={value}
      min={field.min}
      max={field.max}
      onChange={(event) => onChange(field.name, event.target.value)}
      className={commonClassName}
    />
  )
}

export function ResourceFormModal({
  resource,
  config,
  mode,
  item,
  isOpen,
  onClose,
  onSaved,
}) {
  const { token, user } = useAuth()
  const [values, setValues] = useState({})
  const [errors, setErrors] = useState({})
  const [formError, setFormError] = useState('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [isLoadingRefs, setIsLoadingRefs] = useState(false)
  const [references, setReferences] = useState({ sites: [], users: [], roles: [] })

  const visibleFields = useMemo(
    () =>
      config.fields.filter((field) =>
        typeof field.visible === 'function'
          ? field.visible({ mode, user, item })
          : true,
      ),
    [config.fields, item, mode, user],
  )

  const title = mode === 'create' ? config.createTitle : config.editTitle
  const description = config.description

  const initialValues = useMemo(
    () => config.getInitialValues(item, user),
    [config, item, user],
  )

  useEffect(() => {
    if (!isOpen) {
      return
    }

    setValues(initialValues)
    setErrors({})
    setFormError('')
  }, [initialValues, isOpen])

  useEffect(() => {
    let ignore = false

    async function loadReferences() {
      if (!isOpen || !config.refs?.length) {
        return
      }

      setIsLoadingRefs(true)

      try {
        const tasks = []
        const refKeys = []

        if (config.refs.includes('sites')) {
          tasks.push(apiClient.getCollection(token, '/sites'))
          refKeys.push('sites')
        }

        if (config.refs.includes('users') && canUseUserReferences(user)) {
          tasks.push(apiClient.getCollection(token, '/users'))
          refKeys.push('users')
        }

        if (config.refs.includes('roles')) {
          tasks.push(apiClient.getCollection(token, '/roles'))
          refKeys.push('roles')
        }

        const responses = await Promise.allSettled(tasks)
        const nextReferences = { sites: [], users: [], roles: [] }

        responses.forEach((response, index) => {
          const refKey = refKeys[index]
          if (response.status === 'fulfilled') {
            nextReferences[refKey] = response.value
          } else if (refKey === 'sites') {
            throw response.reason
          } else if (refKey === 'roles') {
            throw response.reason
          }
        })

        if (!ignore) {
          setReferences(nextReferences)
        }
      } catch (error) {
        if (!ignore) {
          setFormError(extractErrorMessage(error))
        }
      } finally {
        if (!ignore) {
          setIsLoadingRefs(false)
        }
      }
    }

    loadReferences()

    return () => {
      ignore = true
    }
  }, [config.refs, isOpen, token, user])

  function handleChange(name, nextValue) {
    setValues((current) => ({
      ...current,
      [name]: nextValue,
    }))
    setErrors((current) => ({
      ...current,
      [name]: '',
    }))
    setFormError('')
  }

  async function handleSubmit(event) {
    event.preventDefault()
    const nextErrors = config.validate(values, { mode, user })
    setErrors(nextErrors)

    if (Object.keys(nextErrors).length > 0) {
      return
    }

    setIsSubmitting(true)
    setFormError('')

    try {
      const payload = config.buildPayload(values, { mode, user, item })
      const savedRecord =
        mode === 'create'
          ? await apiClient.createRecord(token, resource.listEndpoint, payload)
          : await apiClient.updateRecord(token, resource.detailEndpoint(item.id), payload)

      onSaved(savedRecord)
    } catch (error) {
      setFormError(extractErrorMessage(error))
    } finally {
      setIsSubmitting(false)
    }
  }

  if (!isOpen) {
    return null
  }

  return (
    <Modal title={title} description={description} onClose={onClose}>
      <form className="space-y-5" onSubmit={handleSubmit}>
        {formError ? (
          <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
            {formError}
          </div>
        ) : null}

        {isLoadingRefs ? (
          <div className="rounded-lg border border-stone-200 bg-stone-50 px-4 py-3 text-sm text-stone-600">
            Loading form references...
          </div>
        ) : null}

        <div className="grid gap-5 md:grid-cols-2">
          {visibleFields.map((field) => {
            const options = buildOptions(field, references)
            const value = normalizeFieldValue(field, values[field.name])
            const error = errors[field.name]

            return (
              <div
                key={field.name}
                className={field.type === 'textarea' ? 'md:col-span-2' : ''}
              >
                <label className="block">
                  {field.type !== 'checkbox' ? (
                    <span className="text-sm font-medium text-stone-700">
                      {field.label}
                      {field.required ? <span className="ml-1 text-rose-600">*</span> : null}
                    </span>
                  ) : null}
                  <FieldControl
                    field={field}
                    value={value}
                    onChange={handleChange}
                    options={options}
                    error={error}
                  />
                </label>
                {field.helperText ? (
                  <p className="mt-1 text-xs leading-5 text-stone-500">{field.helperText}</p>
                ) : null}
                {error ? <p className="mt-1 text-xs text-rose-700">{error}</p> : null}
              </div>
            )
          })}
        </div>

        <div className="flex items-center justify-end gap-3 border-t border-stone-200 pt-5">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isSubmitting}
            className="rounded-md bg-emerald-600 px-4 py-2 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {isSubmitting
              ? mode === 'create'
                ? 'Saving...'
                : 'Updating...'
              : mode === 'create'
                ? 'Create record'
                : 'Save changes'}
          </button>
        </div>
      </form>
    </Modal>
  )
}
