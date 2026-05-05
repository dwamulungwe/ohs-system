export function EmptyState({ title, message }) {
  return (
    <div className="rounded-lg border border-dashed border-stone-300 bg-stone-50 px-6 py-10 text-center shadow-sm">
      <p className="text-base font-semibold text-stone-900">{title}</p>
      <p className="mt-2 text-sm text-stone-600">{message}</p>
    </div>
  )
}
