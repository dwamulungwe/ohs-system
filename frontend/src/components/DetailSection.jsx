import { Badge } from './Badge.jsx'
import { formatValue, humanize } from '../lib/formatters.js'

function DetailValue({ field, item }) {
  const value = item[field.key]

  if (field.badge) {
    return <Badge value={value} />
  }

  if (field.type === 'list') {
    const list = Array.isArray(value) ? value : []
    if (!list.length) {
      return <span className="text-stone-500">-</span>
    }

    return (
      <ul className="space-y-2">
        {list.map((entry, index) => (
          <li
            key={`${field.key}-${index}`}
            className="rounded-md border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-700"
          >
            {typeof entry === 'string' ? entry : JSON.stringify(entry)}
          </li>
        ))}
      </ul>
    )
  }

  if (field.type === 'attachments') {
    const attachments = Array.isArray(value) ? value : []
    if (!attachments.length) {
      return <span className="text-stone-500">No attachments</span>
    }

    return (
      <ul className="space-y-2">
        {attachments.map((attachment, index) => (
          <li
            key={`${field.key}-${index}`}
            className="rounded-md border border-stone-200 bg-stone-50 p-3"
          >
            <p className="font-medium text-stone-900">{attachment.file_name ?? 'Attachment'}</p>
            <p className="mt-1 text-sm text-stone-600">
              {attachment.content_type ?? 'Unknown type'}
              {attachment.size_bytes ? ` - ${attachment.size_bytes} bytes` : ''}
            </p>
          </li>
        ))}
      </ul>
    )
  }

  if (field.type === 'object-list') {
    const list = Array.isArray(value) ? value : []
    if (!list.length) {
      return <span className="text-stone-500">-</span>
    }

    return (
      <div className="space-y-3">
        {list.map((entry, index) => (
          <div
            key={`${field.key}-${index}`}
            className="rounded-md border border-stone-200 bg-stone-50 p-3"
          >
            {Object.entries(entry).map(([entryKey, entryValue]) => (
              <div key={entryKey} className="flex justify-between gap-4 py-1 text-sm">
                <span className="text-stone-500">{humanize(entryKey)}</span>
                <span className="text-right text-stone-900">
                  {formatValue(
                    entryValue,
                    entryKey.includes('date') || entryKey.endsWith('_at')
                      ? 'datetime'
                      : 'text',
                  )}
                </span>
              </div>
            ))}
          </div>
        ))}
      </div>
    )
  }

  if (field.type === 'longtext') {
    return (
      <p className="whitespace-pre-wrap text-sm leading-6 text-stone-700">
        {formatValue(value)}
      </p>
    )
  }

  if (field.type === 'json') {
    return (
      <pre className="overflow-x-auto rounded-md border border-stone-200 bg-stone-50 p-3 text-sm text-stone-700">
        {value ? JSON.stringify(value, null, 2) : '—'}
      </pre>
    )
  }

  return <span className="text-sm text-stone-900">{formatValue(value, field.type)}</span>
}

export function DetailSection({ title, fields, item }) {
  return (
    <section className="rounded-xl border border-stone-200 bg-white p-5 shadow-sm shadow-stone-200/60">
      <h2 className="text-lg font-semibold tracking-tight text-stone-950">{title}</h2>
      <div className="mt-5 grid gap-6 md:grid-cols-2">
        {fields.map((field) => (
          <div key={field.key} className={field.fullWidth ? 'md:col-span-2' : ''}>
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">
              {field.label}
            </p>
            <div className="mt-2">
              <DetailValue field={field} item={item} />
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
