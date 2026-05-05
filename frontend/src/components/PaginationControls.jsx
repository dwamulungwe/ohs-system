export function PaginationControls({
  skip,
  limit,
  total,
  itemsCount,
  onPrevious,
  onNext,
}) {
  const start = itemsCount === 0 ? 0 : skip + 1
  const end = skip + itemsCount
  const hasPrevious = skip > 0
  const hasNext = skip + itemsCount < total || itemsCount === limit

  return (
    <div className="flex flex-col gap-3 border-t border-stone-200 px-4 py-4 text-sm text-stone-600 sm:flex-row sm:items-center sm:justify-between">
      <p>
        Showing <span className="font-medium text-stone-900">{start}</span> to{' '}
        <span className="font-medium text-stone-900">{end}</span> of{' '}
        <span className="font-medium text-stone-900">{total}</span>
      </p>
      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={onPrevious}
          disabled={!hasPrevious}
          className="rounded-md border border-stone-300 bg-white px-3 py-2 font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={onNext}
          disabled={!hasNext}
          className="rounded-md border border-stone-300 bg-white px-3 py-2 font-medium text-stone-700 transition hover:bg-stone-50 disabled:cursor-not-allowed disabled:opacity-50"
        >
          Next
        </button>
      </div>
    </div>
  )
}
