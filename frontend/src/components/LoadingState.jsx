import { LoaderCircle } from 'lucide-react'

export function LoadingState({
  title = 'Loading data',
  message = 'Please wait while the latest information is retrieved.',
  compact = false,
}) {
  return (
    <div
      className={[
        'flex items-center gap-3 text-sm text-stone-600',
        compact ? '' : 'rounded-xl border border-stone-200 bg-white px-4 py-5 shadow-sm shadow-stone-200/60',
      ].join(' ')}
    >
      <LoaderCircle className="size-5 animate-spin text-emerald-600" />
      <div>
        <p className="font-semibold text-stone-900">{title}</p>
        <p className="leading-6">{message}</p>
      </div>
    </div>
  )
}
