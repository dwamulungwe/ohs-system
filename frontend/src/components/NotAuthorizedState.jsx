import { ShieldX } from 'lucide-react'

export function NotAuthorizedState({
  title = 'Not authorized',
  message = 'Your account does not have access to this area. If you believe this is a mistake, contact an administrator or OHS manager.',
}) {
  return (
    <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-6 text-amber-950 shadow-sm shadow-amber-100/70">
      <div className="flex items-start gap-3">
        <ShieldX className="mt-0.5 size-5 shrink-0 text-amber-700" />
        <div>
          <p className="font-semibold">{title}</p>
          <p className="mt-1 text-sm leading-6 text-amber-900/90">{message}</p>
        </div>
      </div>
    </div>
  )
}
