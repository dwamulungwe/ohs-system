import { AlertTriangle, RefreshCcw } from 'lucide-react'

export function ErrorState({ message, onRetry }) {
  return (
    <div className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-5 text-sm text-rose-900 shadow-sm shadow-rose-100/70">
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-rose-600" />
        <div className="flex-1">
          <p className="font-semibold">Something went wrong</p>
          <p className="mt-1 leading-6 text-rose-800">{message}</p>
        </div>
        {onRetry ? (
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-2 rounded-md border border-rose-200 bg-white px-3 py-2 text-sm font-medium text-rose-800 transition hover:bg-rose-100"
          >
            <RefreshCcw className="size-4" />
            Retry
          </button>
        ) : null}
      </div>
    </div>
  )
}
