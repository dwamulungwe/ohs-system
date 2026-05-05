import { X } from 'lucide-react'

export function Modal({
  title,
  description,
  onClose,
  children,
  maxWidthClassName = 'max-w-3xl',
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-stone-950/50 px-4 py-6 backdrop-blur-sm">
      <div className={`max-h-[90vh] w-full overflow-hidden rounded-xl border border-stone-200 bg-white shadow-2xl ${maxWidthClassName}`}>
        <div className="flex items-start justify-between border-b border-stone-200 px-5 py-4 sm:px-6">
          <div>
            <h2 className="text-lg font-semibold tracking-tight text-stone-950">{title}</h2>
            {description ? (
              <p className="mt-1 max-w-2xl text-sm leading-6 text-stone-600">{description}</p>
            ) : null}
          </div>
          <button
            type="button"
            onClick={onClose}
            className="inline-flex rounded-md p-2 text-stone-500 transition hover:bg-stone-100 hover:text-stone-900"
            aria-label="Close modal"
          >
            <X className="size-5" />
          </button>
        </div>
        <div className="max-h-[calc(90vh-84px)] overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
      </div>
    </div>
  )
}
