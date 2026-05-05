import { humanize } from '../lib/formatters.js'

const toneMap = {
  critical: 'bg-rose-100 text-rose-800 ring-rose-200',
  critical_non_conformance: 'bg-rose-100 text-rose-800 ring-rose-200',
  overdue: 'bg-rose-100 text-rose-800 ring-rose-200',
  expired: 'bg-rose-100 text-rose-800 ring-rose-200',
  rejected: 'bg-rose-100 text-rose-800 ring-rose-200',
  high: 'bg-amber-100 text-amber-800 ring-amber-200',
  warning: 'bg-amber-100 text-amber-800 ring-amber-200',
  pending_approval: 'bg-amber-100 text-amber-800 ring-amber-200',
  pending_verification: 'bg-amber-100 text-amber-800 ring-amber-200',
  major_non_conformance: 'bg-amber-100 text-amber-800 ring-amber-200',
  medium: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  open: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  investigating: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  in_progress: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  suspended: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  observation: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  minor_non_conformance: 'bg-yellow-100 text-yellow-800 ring-yellow-200',
  low: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  cancelled: 'bg-stone-200 text-stone-700 ring-stone-300',
  closed: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  completed: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  compliant: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  approved: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  active: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  controlled: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  resolved: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  acknowledged: 'bg-emerald-100 text-emerald-800 ring-emerald-200',
  assigned: 'bg-sky-100 text-sky-800 ring-sky-200',
  info: 'bg-sky-100 text-sky-800 ring-sky-200',
  unread: 'bg-sky-100 text-sky-800 ring-sky-200',
  draft: 'bg-stone-200 text-stone-700 ring-stone-300',
  archived: 'bg-stone-200 text-stone-700 ring-stone-300',
  read: 'bg-stone-200 text-stone-700 ring-stone-300',
  not_applicable: 'bg-stone-200 text-stone-700 ring-stone-300',
  superseded: 'bg-stone-200 text-stone-700 ring-stone-300',
}

export function Badge({ value }) {
  const normalized = String(value ?? '').toLowerCase()
  const tone = toneMap[normalized] ?? 'bg-stone-200 text-stone-700 ring-stone-300'

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-[0.08em] ring-1 ring-inset ${tone}`}
    >
      <span className="size-1.5 rounded-full bg-current opacity-75" />
      {humanize(value)}
    </span>
  )
}
