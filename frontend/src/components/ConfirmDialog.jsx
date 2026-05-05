import { AlertTriangle } from 'lucide-react'
import { Modal } from './Modal.jsx'

export function ConfirmDialog({
  isOpen,
  title,
  description,
  confirmLabel = 'Confirm',
  tone = 'default',
  onConfirm,
  onClose,
}) {
  if (!isOpen) {
    return null
  }

  const confirmClassName =
    tone === 'danger'
      ? 'bg-rose-600 hover:bg-rose-700'
      : 'bg-emerald-600 hover:bg-emerald-700'

  return (
    <Modal title={title} description={description} onClose={onClose} maxWidthClassName="max-w-lg">
      <div className="space-y-5">
        <div className="flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          <AlertTriangle className="mt-0.5 size-5 shrink-0 text-amber-600" />
          <p>{description}</p>
        </div>
        <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="rounded-md border border-stone-300 bg-white px-4 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={onConfirm}
            className={`rounded-md px-4 py-2 text-sm font-semibold text-white transition ${confirmClassName}`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </Modal>
  )
}
