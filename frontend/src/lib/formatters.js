export function formatDate(value) {
  if (!value) {
    return '--'
  }

  return new Intl.DateTimeFormat('en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(new Date(value))
}

export function formatDateTime(value) {
  if (!value) {
    return '--'
  }

  return new Intl.DateTimeFormat('en', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}

export function formatNumber(value) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }

  return new Intl.NumberFormat('en').format(Number(value))
}

export function formatFileSize(value) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }

  const size = Number(value)
  if (!Number.isFinite(size) || size < 0) {
    return '--'
  }

  if (size < 1024) {
    return `${size} B`
  }

  if (size < 1024 * 1024) {
    return `${(size / 1024).toFixed(1)} KB`
  }

  return `${(size / (1024 * 1024)).toFixed(1)} MB`
}

export function humanize(value) {
  if (value === null || value === undefined || value === '') {
    return '--'
  }

  return String(value)
    .replaceAll('_', ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

export function formatValue(value, type = 'text') {
  if (Array.isArray(value)) {
    return value.length ? value.join(', ') : '--'
  }

  if (type === 'date') {
    return formatDate(value)
  }

  if (type === 'datetime') {
    return formatDateTime(value)
  }

  if (type === 'number') {
    return formatNumber(value)
  }

  if (type === 'boolean') {
    return value ? 'Yes' : 'No'
  }

  if (type === 'enum') {
    return humanize(value)
  }

  if (value === null || value === undefined || value === '') {
    return '--'
  }

  return String(value)
}

export function summarizeList(items, limit = 2) {
  if (!Array.isArray(items) || items.length === 0) {
    return '--'
  }

  if (items.length <= limit) {
    return items.join(', ')
  }

  return `${items.slice(0, limit).join(', ')} +${items.length - limit}`
}
