import { Link } from 'react-router-dom'
import { ChevronRight } from 'lucide-react'
import { Badge } from './Badge.jsx'
import { EmptyState } from './EmptyState.jsx'
import { formatValue } from '../lib/formatters.js'

function renderCell(item, column) {
  const value = item[column.key]

  if (column.render) {
    return column.render(item)
  }

  if (column.badge) {
    return <Badge value={value} />
  }

  return (
    <span className="block max-w-xs truncate" title={formatValue(value, column.type)}>
      {formatValue(value, column.type)}
    </span>
  )
}

export function DataTable({
  items,
  columns,
  getRowHref,
  emptyTitle,
  emptyMessage,
}) {
  if (!items.length) {
    return <EmptyState title={emptyTitle} message={emptyMessage} />
  }

  return (
    <div className="rounded-xl border border-stone-200 bg-white shadow-sm shadow-stone-200/60">
      <div className="space-y-3 p-3 md:hidden">
        {items.map((item) => {
          const href = typeof getRowHref === 'function' ? getRowHref(item) : null
          const previewColumns = columns.slice(1, 4)
          const cardClassName = 'block rounded-lg border border-stone-200 bg-stone-50 p-4 transition hover:border-emerald-200 hover:bg-emerald-50/40'
          const cardContent = (
            <>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-base font-semibold text-stone-950">
                    {formatValue(item[columns[0].key], columns[0].type)}
                  </p>
                  <p className="mt-1 text-sm text-stone-500">Record #{item.id}</p>
                </div>
                {href ? <ChevronRight className="mt-1 size-4 shrink-0 text-stone-400" /> : null}
              </div>
              <div className="mt-4 space-y-3">
                {previewColumns.map((column) => (
                  <div key={column.key} className="flex items-start justify-between gap-4">
                    <span className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">
                      {column.label}
                    </span>
                    <div className="max-w-[58%] text-right text-sm text-stone-700">
                      {renderCell(item, column)}
                    </div>
                  </div>
                ))}
              </div>
            </>
          )

          return href ? (
            <Link key={item.id} to={href} className={cardClassName}>
              {cardContent}
            </Link>
          ) : (
            <div key={item.id} className={cardClassName}>
              {cardContent}
            </div>
          )
        })}
      </div>

      <div className="hidden overflow-x-auto md:block">
        <table className="min-w-full divide-y divide-stone-200">
          <thead className="bg-stone-50/90">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className="px-5 py-3.5 text-left text-xs font-semibold uppercase tracking-[0.08em] text-stone-500"
                >
                  {column.label}
                </th>
              ))}
              <th className="w-14 px-5 py-3.5" />
            </tr>
          </thead>
          <tbody className="divide-y divide-stone-100">
            {items.map((item, rowIndex) => {
              const href = typeof getRowHref === 'function' ? getRowHref(item) : null

              return (
                <tr
                  key={item.id}
                  className={[
                    'transition hover:bg-emerald-50/50',
                    rowIndex % 2 === 0 ? 'bg-white' : 'bg-stone-50/40',
                  ].join(' ')}
                >
                  {columns.map((column, index) => (
                    <td
                      key={column.key}
                      className={[
                        'px-5 py-4 align-top text-sm text-stone-700',
                        index === 0 ? 'font-semibold text-stone-950' : '',
                      ].join(' ')}
                    >
                      {index === 0 && href ? (
                        <Link to={href} className="block hover:text-emerald-700">
                          {renderCell(item, column)}
                        </Link>
                      ) : (
                        renderCell(item, column)
                      )}
                    </td>
                  ))}
                  <td className="px-5 py-4 text-right">
                    {href ? (
                      <Link
                        to={href}
                        className="inline-flex items-center rounded-md p-2 text-stone-500 transition hover:bg-white hover:text-stone-900"
                        aria-label="Open details"
                      >
                        <ChevronRight className="size-4" />
                      </Link>
                    ) : null}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
