import { formatNumber } from '../lib/formatters.js'

export function StatCard({
  label,
  value,
  accent = 'text-emerald-700',
  accentBg = 'bg-emerald-100',
  description = 'Current total',
}) {
  return (
    <div className="rounded-xl border border-stone-200 bg-white px-5 py-5 shadow-sm shadow-stone-200/60">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-semibold text-stone-600">{label}</p>
          <p className={`mt-3 text-3xl font-semibold tracking-tight ${accent}`}>
            {formatNumber(value)}
          </p>
        </div>
        <div className={`mt-1 size-3 rounded-full ${accentBg}`} />
      </div>
      <p className="mt-4 text-sm text-stone-500">{description}</p>
    </div>
  )
}
