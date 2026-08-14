import { useCallback, useEffect, useMemo, useState } from 'react'
import { AlertTriangle, ArrowLeftRight, Boxes, CheckCircle2, ClipboardCheck, Download, HardHat, PackagePlus, RefreshCw, Search, ShieldCheck, ShoppingCart, Users } from 'lucide-react'
import { apiClient } from '../api/client.js'
import { useAuth } from '../context/AuthContext.jsx'
import { formatDate, formatDateTime, formatValue } from '../lib/formatters.js'
import { hasPermission } from '../lib/rbac.js'

const tabs = [
  ['dashboard', 'Dashboard', ShieldCheck],
  ['catalogue', 'Catalogue', HardHat],
  ['inventory', 'Inventory', Boxes],
  ['issues', 'Issues', PackagePlus],
  ['requests', 'Requests', ShoppingCart],
  ['inspections', 'Inspections', ClipboardCheck],
  ['compliance', 'Compliance', Users],
  ['movements', 'Stock Movements', ArrowLeftRight],
]

const inputClass = 'w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm outline-none transition focus:border-emerald-500 focus:ring-2 focus:ring-emerald-100'
const buttonClass = 'inline-flex items-center justify-center gap-2 rounded-lg bg-emerald-700 px-3 py-2 text-sm font-semibold text-white transition hover:bg-emerald-800 disabled:cursor-not-allowed disabled:opacity-50'

function Card({ label, value, detail, warning = false }) {
  return (
    <article className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-stone-500">{label}</p>
      <p className={`mt-2 text-2xl font-semibold ${warning ? 'text-amber-700' : 'text-stone-950'}`}>{value ?? 'Unavailable'}</p>
      {detail ? <p className="mt-1 text-xs text-stone-500">{detail}</p> : null}
    </article>
  )
}

function Empty({ children = 'No PPE records match this view.' }) {
  return <div className="rounded-xl border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-500">{children}</div>
}

function Status({ value }) {
  const positive = ['compliant', 'approved', 'issued', 'passed', 'serviceable', 'good'].includes(String(value))
  const negative = ['non_compliant', 'rejected', 'lost', 'damaged', 'unserviceable', 'overdue'].includes(String(value))
  const tone = positive ? 'bg-emerald-100 text-emerald-800' : negative ? 'bg-red-100 text-red-800' : 'bg-amber-100 text-amber-800'
  return <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${tone}`}>{String(value ?? '—').replaceAll('_', ' ')}</span>
}

function Field({ label, children }) {
  return <label className="space-y-1 text-sm font-medium text-stone-700"><span>{label}</span>{children}</label>
}

function Panel({ title, description, children }) {
  return <section className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm"><h3 className="font-semibold text-stone-950">{title}</h3>{description ? <p className="mt-1 text-sm text-stone-500">{description}</p> : null}<div className="mt-4">{children}</div></section>
}

function DataTable({ headers, rows, renderRow }) {
  if (!rows?.length) return <Empty />
  return (
    <div className="overflow-x-auto rounded-xl border border-stone-200 bg-white">
      <table className="min-w-full divide-y divide-stone-200 text-sm">
        <thead className="bg-stone-50"><tr>{headers.map((header) => <th key={header} className="whitespace-nowrap px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-stone-500">{header}</th>)}</tr></thead>
        <tbody className="divide-y divide-stone-100">{rows.map(renderRow)}</tbody>
      </table>
    </div>
  )
}

export function PPEManagementPage() {
  const { token, user } = useAuth()
  const [tab, setTab] = useState(hasPermission(user, 'ppe.view') ? 'dashboard' : 'compliance')
  const [data, setData] = useState(null)
  const [catalogue, setCatalogue] = useState([])
  const [categories, setCategories] = useState([])
  const [locations, setLocations] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [profileUserId, setProfileUserId] = useState(String(user?.id ?? ''))
  const [search, setSearch] = useState('')
  const [categoryForm, setCategoryForm] = useState({ name: '' })
  const [itemForm, setItemForm] = useState({ category_id: '', name: '', code: '', is_reusable: false, inspection_required: false, expiry_tracking: false, size_applicable: false, minimum_stock_level: 0, reorder_level: 0 })
  const [locationForm, setLocationForm] = useState({ name: '', site_id: user?.assigned_site_id ?? '' })
  const [receiptForm, setReceiptForm] = useState({ item_id: '', variant_id: '', location_id: '', quantity: 1, unit_cost: '', reference: '' })
  const [issueForm, setIssueForm] = useState({ recipient_user_id: '', item_id: '', variant_id: '', stock_location_id: '', quantity: 1 })
  const [requestForm, setRequestForm] = useState({ item_id: '', variant_id: '', quantity: 1, reason: '', urgency: 'routine' })
  const [inspectionForm, setInspectionForm] = useState({ issue_id: '', condition: 'good', passed: true, defects: '', next_inspection_date: '' })

  const canManageRequirements = hasPermission(user, 'ppe.requirements_manage')
  const canReceive = hasPermission(user, 'ppe.inventory.receive')
  const canIssue = hasPermission(user, 'ppe.inventory.issue')
  const canInspect = hasPermission(user, 'ppe.inspect')
  const canReview = hasPermission(user, 'ppe.request_review')
  const canViewAll = hasPermission(user, 'ppe.view')
  const visibleTabs = canViewAll ? tabs : tabs.filter(([key]) => ['issues', 'requests', 'compliance'].includes(key))

  const loadLookups = useCallback(async () => {
    const items = await apiClient.getPpeCollection(token, 'catalogue', { limit: 500 })
    setCatalogue(items.items ?? [])
    if (canViewAll) {
      const [categoryRows, locationRows] = await Promise.all([
        apiClient.getPpeCollection(token, 'categories', { active_only: true }),
        apiClient.getPpeCollection(token, 'locations', { active_only: true }),
      ])
      setCategories(categoryRows)
      setLocations(locationRows)
    }
  }, [canViewAll, token])

  const loadTab = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      let payload
      if (tab === 'dashboard') payload = await apiClient.getPpeDashboard(token)
      if (tab === 'catalogue') payload = await apiClient.getPpeCollection(token, 'catalogue', { limit: 500, search })
      if (tab === 'inventory') payload = await apiClient.getPpeCollection(token, 'inventory', { limit: 500 })
      if (tab === 'issues') payload = await apiClient.getPpeCollection(token, 'issues', { limit: 500 })
      if (tab === 'requests') payload = await apiClient.getPpeCollection(token, 'requests', { limit: 500 })
      if (tab === 'inspections') payload = await apiClient.getPpeCollection(token, 'inspections', { limit: 500 })
      if (tab === 'compliance') payload = await apiClient.getPpeCollection(token, `employees/${profileUserId || user.id}`)
      if (tab === 'movements') payload = await apiClient.getPpeCollection(token, 'movements', { limit: 500 })
      setData(payload)
    } catch (loadError) {
      setError(loadError.message)
      setData(null)
    } finally {
      setLoading(false)
    }
  }, [profileUserId, search, tab, token, user.id])

  useEffect(() => {
    // The request owns the resulting lookup state; no external subscription is required.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadLookups().catch((loadError) => setError(loadError.message))
  }, [loadLookups])
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadTab()
  }, [loadTab])

  const rows = useMemo(() => data?.items ?? (Array.isArray(data) ? data : []), [data])

  async function submit(command, payload, reset) {
    setSaving(true); setError(''); setNotice('')
    try {
      await apiClient.ppeCommand(token, command, payload)
      setNotice('PPE record saved successfully.')
      if (reset) reset()
      await Promise.all([loadTab(), loadLookups()])
    } catch (submitError) {
      setError(submitError.message)
    } finally {
      setSaving(false)
    }
  }

  async function decide(requestId, approved) {
    await submit(`requests/${requestId}/decision`, { approved }, null)
  }

  async function download(report) {
    setError('')
    try {
      const result = await apiClient.downloadFile(token, `/ppe/exports/${report}`, { fallbackFilename: `ppe-${report}.csv` })
      const url = URL.createObjectURL(result.blob)
      const anchor = document.createElement('a'); anchor.href = url; anchor.download = result.filename; anchor.click(); URL.revokeObjectURL(url)
    } catch (downloadError) { setError(downloadError.message) }
  }

  function catalogueView() {
    return <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3"><div className="relative min-w-64 flex-1"><Search className="absolute left-3 top-2.5 size-4 text-stone-400" /><input className={`${inputClass} pl-9`} value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search item name or SKU" /></div><button className={buttonClass} onClick={loadTab}><RefreshCw className="size-4" />Refresh</button></div>
      {canManageRequirements ? <div className="grid gap-4 xl:grid-cols-2">
        <Panel title="Add category" description="Categories stay configurable for each organisation."><form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); submit('categories', categoryForm, () => setCategoryForm({ name: '' })) }}><input className={inputClass} required value={categoryForm.name} onChange={(event) => setCategoryForm({ name: event.target.value })} placeholder="e.g. Head Protection" /><button className={buttonClass} disabled={saving}>Add</button></form></Panel>
        <Panel title="Add catalogue item"><form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); submit('catalogue', { ...itemForm, category_id: Number(itemForm.category_id), minimum_stock_level: Number(itemForm.minimum_stock_level), reorder_level: Number(itemForm.reorder_level) }, () => setItemForm({ ...itemForm, name: '', code: '' })) }}>
          <Field label="Category"><select required className={inputClass} value={itemForm.category_id} onChange={(event) => setItemForm({ ...itemForm, category_id: event.target.value })}><option value="">Select category</option>{categories.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
          <Field label="Item name"><input required className={inputClass} value={itemForm.name} onChange={(event) => setItemForm({ ...itemForm, name: event.target.value })} /></Field>
          <Field label="Code / SKU"><input required className={inputClass} value={itemForm.code} onChange={(event) => setItemForm({ ...itemForm, code: event.target.value })} /></Field>
          <Field label="Reorder level"><input type="number" min="0" className={inputClass} value={itemForm.reorder_level} onChange={(event) => setItemForm({ ...itemForm, reorder_level: event.target.value })} /></Field>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={itemForm.is_reusable} onChange={(event) => setItemForm({ ...itemForm, is_reusable: event.target.checked })} />Reusable</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={itemForm.inspection_required} onChange={(event) => setItemForm({ ...itemForm, inspection_required: event.target.checked })} />Inspection required</label>
          <button className={`${buttonClass} sm:col-span-2`} disabled={saving}>Create item</button>
        </form></Panel>
      </div> : null}
      <DataTable headers={['Item', 'Code', 'Category', 'Type', 'Inspection', 'Variants']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3 font-medium text-stone-900">{item.name}</td><td className="px-4 py-3">{item.code}</td><td className="px-4 py-3">{item.category_name}</td><td className="px-4 py-3">{item.is_reusable ? 'Reusable' : 'Disposable'}</td><td className="px-4 py-3">{item.inspection_required ? 'Required' : 'No'}</td><td className="px-4 py-3">{item.variants?.map((variant) => variant.name).join(', ') || 'Standard'}</td></tr>} />
    </div>
  }

  function inventoryView() {
    return <div className="space-y-4">{canReceive ? <div className="grid gap-4 xl:grid-cols-2">
      <Panel title="Create stock location"><form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); submit('locations', { ...locationForm, site_id: locationForm.site_id ? Number(locationForm.site_id) : null }, () => setLocationForm({ ...locationForm, name: '' })) }}><Field label="Location name"><input required className={inputClass} value={locationForm.name} onChange={(event) => setLocationForm({ ...locationForm, name: event.target.value })} /></Field><Field label="Site ID (optional)"><input type="number" className={inputClass} value={locationForm.site_id} onChange={(event) => setLocationForm({ ...locationForm, site_id: event.target.value })} /></Field><button className={`${buttonClass} sm:col-span-2`} disabled={saving}>Create location</button></form></Panel>
      <Panel title="Receive stock"><form className="grid gap-3 sm:grid-cols-2" onSubmit={(event) => { event.preventDefault(); submit('inventory/receive', { ...receiptForm, item_id: Number(receiptForm.item_id), variant_id: receiptForm.variant_id ? Number(receiptForm.variant_id) : null, location_id: Number(receiptForm.location_id), quantity: Number(receiptForm.quantity), unit_cost: receiptForm.unit_cost || null }, () => setReceiptForm({ ...receiptForm, quantity: 1, reference: '' })) }}>
        <Field label="PPE item"><select required className={inputClass} value={receiptForm.item_id} onChange={(event) => setReceiptForm({ ...receiptForm, item_id: event.target.value, variant_id: '' })}><option value="">Select item</option>{catalogue.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
        <Field label="Variant"><select className={inputClass} value={receiptForm.variant_id} onChange={(event) => setReceiptForm({ ...receiptForm, variant_id: event.target.value })}><option value="">Standard</option>{catalogue.find((item) => item.id === Number(receiptForm.item_id))?.variants?.map((variant) => <option key={variant.id} value={variant.id}>{variant.name}</option>)}</select></Field>
        <Field label="Location"><select required className={inputClass} value={receiptForm.location_id} onChange={(event) => setReceiptForm({ ...receiptForm, location_id: event.target.value })}><option value="">Select location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
        <Field label="Quantity"><input required type="number" min="1" className={inputClass} value={receiptForm.quantity} onChange={(event) => setReceiptForm({ ...receiptForm, quantity: event.target.value })} /></Field>
        <Field label="Unit cost"><input type="number" min="0" step="0.01" className={inputClass} value={receiptForm.unit_cost} onChange={(event) => setReceiptForm({ ...receiptForm, unit_cost: event.target.value })} /></Field>
        <Field label="Reference"><input className={inputClass} value={receiptForm.reference} onChange={(event) => setReceiptForm({ ...receiptForm, reference: event.target.value })} /></Field>
        <button className={`${buttonClass} sm:col-span-2`} disabled={saving}><PackagePlus className="size-4" />Receive stock</button>
      </form></Panel>
    </div> : null}
      <div className="flex justify-end"><button className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700" onClick={() => download('inventory')}><Download className="size-4" />Export inventory</button></div>
      <DataTable headers={['Item', 'Variant', 'Location', 'On hand', 'Reserved', 'Available', 'Reorder', 'State']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3 font-medium">{item.item_name}</td><td className="px-4 py-3">{item.variant_name || 'Standard'}</td><td className="px-4 py-3">{item.location_name}</td><td className="px-4 py-3">{item.quantity_on_hand}</td><td className="px-4 py-3">{item.quantity_reserved}</td><td className="px-4 py-3">{item.quantity_available}</td><td className="px-4 py-3">{item.reorder_level}</td><td className="px-4 py-3"><Status value={item.low_stock ? 'low stock' : 'healthy'} /></td></tr>} />
    </div>
  }

  function issuesView() {
    return <div className="space-y-4">{canIssue ? <Panel title="Issue PPE" description="Stock is validated and reduced atomically when this record is created."><form className="grid gap-3 md:grid-cols-3" onSubmit={(event) => { event.preventDefault(); submit('issues', { ...issueForm, recipient_type: 'employee', recipient_user_id: Number(issueForm.recipient_user_id), item_id: Number(issueForm.item_id), variant_id: issueForm.variant_id ? Number(issueForm.variant_id) : null, stock_location_id: Number(issueForm.stock_location_id), quantity: Number(issueForm.quantity) }, () => setIssueForm({ ...issueForm, recipient_user_id: '', quantity: 1 })) }}>
      <Field label="Employee user ID"><input required type="number" className={inputClass} value={issueForm.recipient_user_id} onChange={(event) => setIssueForm({ ...issueForm, recipient_user_id: event.target.value })} /></Field>
      <Field label="PPE item"><select required className={inputClass} value={issueForm.item_id} onChange={(event) => setIssueForm({ ...issueForm, item_id: event.target.value, variant_id: '' })}><option value="">Select item</option>{catalogue.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
      <Field label="Variant"><select className={inputClass} value={issueForm.variant_id} onChange={(event) => setIssueForm({ ...issueForm, variant_id: event.target.value })}><option value="">Standard</option>{catalogue.find((item) => item.id === Number(issueForm.item_id))?.variants?.map((variant) => <option key={variant.id} value={variant.id}>{variant.name}</option>)}</select></Field>
      <Field label="Stock location"><select required className={inputClass} value={issueForm.stock_location_id} onChange={(event) => setIssueForm({ ...issueForm, stock_location_id: event.target.value })}><option value="">Select location</option>{locations.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
      <Field label="Quantity"><input required type="number" min="1" className={inputClass} value={issueForm.quantity} onChange={(event) => setIssueForm({ ...issueForm, quantity: event.target.value })} /></Field>
      <button className={`${buttonClass} self-end`} disabled={saving}>Issue PPE</button>
    </form></Panel> : null}
      <DataTable headers={['Recipient', 'Item', 'Variant', 'Quantity', 'Issued', 'Replacement', 'Inspection', 'Status']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3">{item.recipient_name_snapshot}</td><td className="px-4 py-3 font-medium">{item.item_name_snapshot}</td><td className="px-4 py-3">{item.variant_name_snapshot || 'Standard'}</td><td className="px-4 py-3">{item.quantity - item.returned_quantity}</td><td className="px-4 py-3">{formatDate(item.issue_date)}</td><td className="px-4 py-3">{formatDate(item.expected_replacement_date)}</td><td className="px-4 py-3">{formatDate(item.next_inspection_date)}</td><td className="px-4 py-3"><Status value={item.status} /></td></tr>} />
    </div>
  }

  function requestsView() {
    return <div className="space-y-4"><Panel title="Request PPE"><form className="grid gap-3 md:grid-cols-4" onSubmit={(event) => { event.preventDefault(); submit('requests', { ...requestForm, item_id: Number(requestForm.item_id), variant_id: requestForm.variant_id ? Number(requestForm.variant_id) : null, quantity: Number(requestForm.quantity) }, () => setRequestForm({ ...requestForm, reason: '', quantity: 1 })) }}>
      <Field label="PPE item"><select required className={inputClass} value={requestForm.item_id} onChange={(event) => setRequestForm({ ...requestForm, item_id: event.target.value, variant_id: '' })}><option value="">Select item</option>{catalogue.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}</select></Field>
      <Field label="Quantity"><input type="number" min="1" className={inputClass} value={requestForm.quantity} onChange={(event) => setRequestForm({ ...requestForm, quantity: event.target.value })} /></Field>
      <Field label="Urgency"><select className={inputClass} value={requestForm.urgency} onChange={(event) => setRequestForm({ ...requestForm, urgency: event.target.value })}><option value="routine">Routine</option><option value="urgent">Urgent</option><option value="critical">Critical</option></select></Field>
      <Field label="Reason"><input required className={inputClass} value={requestForm.reason} onChange={(event) => setRequestForm({ ...requestForm, reason: event.target.value })} /></Field>
      <button className={`${buttonClass} md:col-span-4`} disabled={saving}>Submit request</button>
    </form></Panel>
      <DataTable headers={['Requester', 'Recipient', 'Item ID', 'Quantity', 'Urgency', 'Status', 'Decision']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3">User #{item.requester_user_id}</td><td className="px-4 py-3">User #{item.recipient_user_id}</td><td className="px-4 py-3">#{item.item_id}</td><td className="px-4 py-3">{item.quantity}</td><td className="px-4 py-3"><Status value={item.urgency} /></td><td className="px-4 py-3"><Status value={item.status} /></td><td className="px-4 py-3">{canReview && item.status === 'requested' ? <div className="flex gap-2"><button className="text-xs font-semibold text-emerald-700" onClick={() => decide(item.id, true)}>Approve</button><button className="text-xs font-semibold text-red-700" onClick={() => decide(item.id, false)}>Reject</button></div> : item.decision_notes || '—'}</td></tr>} />
    </div>
  }

  function inspectionsView() {
    return <div className="space-y-4">{canInspect ? <Panel title="Record PPE inspection"><form className="grid gap-3 md:grid-cols-3" onSubmit={(event) => { event.preventDefault(); submit('inspections', { ...inspectionForm, issue_id: Number(inspectionForm.issue_id), next_inspection_date: inspectionForm.next_inspection_date || null }, () => setInspectionForm({ ...inspectionForm, issue_id: '', defects: '' })) }}>
      <Field label="PPE issue ID"><input required type="number" className={inputClass} value={inspectionForm.issue_id} onChange={(event) => setInspectionForm({ ...inspectionForm, issue_id: event.target.value })} /></Field>
      <Field label="Condition"><select className={inputClass} value={inspectionForm.condition} onChange={(event) => setInspectionForm({ ...inspectionForm, condition: event.target.value })}>{['good', 'serviceable', 'worn', 'damaged', 'unserviceable'].map((value) => <option key={value}>{value}</option>)}</select></Field>
      <Field label="Next inspection"><input type="date" className={inputClass} value={inspectionForm.next_inspection_date} onChange={(event) => setInspectionForm({ ...inspectionForm, next_inspection_date: event.target.value })} /></Field>
      <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={inspectionForm.passed} onChange={(event) => setInspectionForm({ ...inspectionForm, passed: event.target.checked })} />Inspection passed</label>
      <Field label="Defects"><input className={inputClass} value={inspectionForm.defects} onChange={(event) => setInspectionForm({ ...inspectionForm, defects: event.target.value })} /></Field>
      <button className={buttonClass} disabled={saving}>Record inspection</button>
    </form></Panel> : null}
      <DataTable headers={['Issue', 'Date', 'Inspector', 'Condition', 'Result', 'Next inspection', 'Defects']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3">#{item.issue_id}</td><td className="px-4 py-3">{formatDate(item.inspection_date)}</td><td className="px-4 py-3">User #{item.inspector_user_id}</td><td className="px-4 py-3">{item.condition}</td><td className="px-4 py-3"><Status value={item.passed ? 'passed' : 'failed'} /></td><td className="px-4 py-3">{formatDate(item.next_inspection_date)}</td><td className="px-4 py-3">{item.defects || '—'}</td></tr>} />
    </div>
  }

  function complianceView() {
    if (!data) return <Empty />
    return <div className="space-y-4">{canViewAll ? <Panel title="Employee PPE workspace"><form className="flex gap-2" onSubmit={(event) => { event.preventDefault(); loadTab() }}><input type="number" className={inputClass} value={profileUserId} onChange={(event) => setProfileUserId(event.target.value)} placeholder="Employee user ID" /><button className={buttonClass}><Search className="size-4" />Open profile</button></form></Panel> : null}
      <div className="grid gap-3 sm:grid-cols-3"><Card label="Compliance" value={<Status value={data.compliance_status} />} /><Card label="Compliance rate" value={data.compliance_rate == null ? 'Not applicable' : `${formatValue(data.compliance_rate, 'number')}%`} /><Card label="Missing mandatory" value={data.missing?.length ?? 0} warning={Boolean(data.missing?.length)} /></div>
      <div className="grid gap-4 xl:grid-cols-2"><Panel title="Required and missing"><DataTable headers={['Item', 'Level', 'Required', 'Valid', 'State']} rows={data.requirements} renderRow={(item) => <tr key={item.requirement_id}><td className="px-4 py-3 font-medium">{item.item_name}</td><td className="px-4 py-3">{item.requirement_level}</td><td className="px-4 py-3">{item.quantity_required}</td><td className="px-4 py-3">{item.quantity_valid}</td><td className="px-4 py-3"><Status value={item.satisfied ? 'compliant' : item.reason} /></td></tr>} /></Panel><Panel title="Current issues"><DataTable headers={['Item', 'Issued', 'Replacement', 'Status']} rows={data.issued} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3 font-medium">{item.item_name_snapshot}</td><td className="px-4 py-3">{formatDate(item.issue_date)}</td><td className="px-4 py-3">{formatDate(item.expected_replacement_date)}</td><td className="px-4 py-3"><Status value={item.status} /></td></tr>} /></Panel></div>
    </div>
  }

  function dashboardView() {
    if (!data) return <Empty />
    return <div className="space-y-5"><div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5"><Card label="Catalogue items" value={data.total_catalogue_items} /><Card label="Low stock" value={data.low_stock_items} warning={data.low_stock_items > 0} /><Card label="Pending requests" value={data.pending_requests} warning={data.pending_requests > 0} /><Card label="Issues this month" value={data.issues_this_month} /><Card label="PPE compliance" value={data.compliance_rate == null ? 'Not applicable' : `${data.compliance_rate}%`} /></div>
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4"><Card label="Replacement due" value={data.replacements_due} /><Card label="Replacement overdue" value={data.overdue_replacements} warning={data.overdue_replacements > 0} /><Card label="Inspection due" value={data.inspections_due} /><Card label="Inspection overdue" value={data.overdue_inspections} warning={data.overdue_inspections > 0} /><Card label="Expired PPE" value={data.expired_ppe} warning={data.expired_ppe > 0} /><Card label="Damaged PPE" value={data.damaged_ppe} warning={data.damaged_ppe > 0} /><Card label="Lost PPE" value={data.lost_ppe} warning={data.lost_ppe > 0} /><Card label="Issue cost" value={data.issue_cost == null ? 'Unavailable' : formatValue(data.issue_cost, 'currency')} detail={data.unavailable_cost_records ? `${data.unavailable_cost_records} issue(s) missing cost` : 'Complete cost coverage'} /></div>
      <Panel title="Employee compliance"><div className="grid gap-3 sm:grid-cols-4"><Card label="Requiring PPE" value={data.employees_requiring_ppe} /><Card label="Fully compliant" value={data.fully_compliant_employees} /><Card label="Partially compliant" value={data.partially_compliant_employees} warning={data.partially_compliant_employees > 0} /><Card label="Non-compliant" value={data.non_compliant_employees} warning={data.non_compliant_employees > 0} /></div></Panel>
    </div>
  }

  function movementsView() {
    return <div className="space-y-4"><div className="flex justify-end"><button className="inline-flex items-center gap-2 text-sm font-semibold text-emerald-700" onClick={() => download('movements')}><Download className="size-4" />Export movements</button></div><DataTable headers={['Timestamp', 'Type', 'Item', 'Variant', 'Location', 'Quantity', 'Balance', 'Reference', 'Actor']} rows={rows} renderRow={(item) => <tr key={item.id}><td className="px-4 py-3">{formatDateTime(item.created_at)}</td><td className="px-4 py-3"><Status value={item.movement_type} /></td><td className="px-4 py-3">#{item.item_id}</td><td className="px-4 py-3">{item.variant_id ? `#${item.variant_id}` : 'Standard'}</td><td className="px-4 py-3">#{item.location_id}</td><td className="px-4 py-3 font-semibold">{item.quantity > 0 ? '+' : ''}{item.quantity}</td><td className="px-4 py-3">{item.balance_after}</td><td className="px-4 py-3">{item.reference || item.transfer_reference || '—'}</td><td className="px-4 py-3">{item.actor_user_id ? `User #${item.actor_user_id}` : 'System'}</td></tr>} /></div>
  }

  let content = null
  if (tab === 'dashboard') content = dashboardView()
  if (tab === 'catalogue') content = catalogueView()
  if (tab === 'inventory') content = inventoryView()
  if (tab === 'issues') content = issuesView()
  if (tab === 'requests') content = requestsView()
  if (tab === 'inspections') content = inspectionsView()
  if (tab === 'compliance') content = complianceView()
  if (tab === 'movements') content = movementsView()

  return <div className="space-y-5">
    <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-emerald-900 via-emerald-800 to-teal-700 p-6 text-white shadow-lg"><div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">Enterprise PPE control</p><h2 className="mt-2 text-2xl font-semibold">Protect every person. Account for every item.</h2><p className="mt-2 max-w-3xl text-sm text-emerald-100">One tenant-safe register from catalogue and stock through issue, inspection, replacement, return and compliance.</p></div><HardHat className="size-16 text-emerald-200/70" /></div></section>
    <nav className="flex gap-2 overflow-x-auto pb-1">{visibleTabs.map(([key, label, Icon]) => <button key={key} onClick={() => setTab(key)} className={`inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm font-semibold transition ${tab === key ? 'bg-emerald-700 text-white' : 'border border-stone-200 bg-white text-stone-700 hover:bg-stone-50'}`}><Icon className="size-4" />{label}</button>)}</nav>
    {error ? <div className="flex items-start gap-2 rounded-xl border border-red-200 bg-red-50 p-3 text-sm text-red-800"><AlertTriangle className="mt-0.5 size-4 shrink-0" />{error}</div> : null}
    {notice ? <div className="flex items-start gap-2 rounded-xl border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800"><CheckCircle2 className="mt-0.5 size-4 shrink-0" />{notice}</div> : null}
    {loading ? <div className="flex items-center justify-center gap-2 p-12 text-sm text-stone-500"><RefreshCw className="size-4 animate-spin" />Loading PPE workspace…</div> : content}
  </div>
}
