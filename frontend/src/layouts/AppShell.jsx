import { Bell, LayoutDashboard, LogOut, ShieldCheck, Smartphone } from 'lucide-react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'
import { useEffect, useState } from 'react'
import { resources } from '../config/resources.jsx'
import { useAuth } from '../context/AuthContext.jsx'
import { apiClient } from '../api/client.js'
import { ConfirmDialog } from '../components/ConfirmDialog.jsx'
import { formatValue } from '../lib/formatters.js'
import { canAccessQuickReport, canShowResourceInNav, canViewDashboard, formatRoleLabel } from '../lib/rbac.js'

function getPageTitle(pathname) {
  if (pathname === '/dashboard') {
    return 'Dashboard'
  }

  if (pathname === '/quick-report') {
    return 'Quick Report'
  }

  const exactMatch = resources.find(
    (resource) =>
      pathname === resource.route || pathname.startsWith(`${resource.route}/`),
  )

  return exactMatch?.label ?? 'OHS Management'
}

export function AppShell() {
  const location = useLocation()
  const { logout, token, user, primaryRole, assignedSiteId } = useAuth()
  const [unreadCount, setUnreadCount] = useState(0)
  const [isLogoutConfirmOpen, setIsLogoutConfirmOpen] = useState(false)
  const visibleResources = resources.filter((resource) =>
    canShowResourceInNav(resource.key, user),
  )
  const showDashboard = canViewDashboard(user)
  const showQuickReport = canAccessQuickReport(user)

  useEffect(() => {
    let ignore = false

    async function loadUnreadCount() {
      try {
        const response = await apiClient.getUnreadNotificationCount(token)
        if (!ignore) {
          setUnreadCount(response.unread_count)
        }
      } catch {
        if (!ignore) {
          setUnreadCount(0)
        }
      }
    }

    loadUnreadCount()

    return () => {
      ignore = true
    }
  }, [token, location.pathname])

  return (
    <div className="min-h-screen bg-transparent">
      <div className="mx-auto flex min-h-screen max-w-[1600px]">
        <aside className="hidden w-72 shrink-0 border-r border-stone-200 bg-[#fbfcf8] px-5 py-6 lg:flex lg:flex-col">
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-emerald-600 text-white shadow-sm shadow-emerald-300/40">
              <ShieldCheck className="size-5" />
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">
                OHS Platform
              </p>
              <p className="text-base font-semibold text-stone-950">Management Console</p>
            </div>
          </div>

          <nav className="mt-8 flex-1 space-y-1.5">
            {showDashboard ? (
              <NavLink
                to="/dashboard"
                className={({ isActive }) =>
                  [
                    'flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition',
                    isActive
                      ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                      : 'text-stone-700 hover:bg-stone-100 hover:text-stone-950',
                  ].join(' ')
                }
              >
                <LayoutDashboard className="size-4" />
                <span>Dashboard</span>
              </NavLink>
            ) : null}
            {showQuickReport ? (
              <NavLink
                to="/quick-report"
                className={({ isActive }) =>
                  [
                    'flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition',
                    isActive
                      ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                      : 'text-stone-700 hover:bg-stone-100 hover:text-stone-950',
                  ].join(' ')
                }
              >
                <Smartphone className="size-4" />
                <span>Quick Report</span>
              </NavLink>
            ) : null}
            {visibleResources.map((resource) => {
              const Icon = resource.icon

              return (
                <NavLink
                  key={resource.key}
                  to={resource.route}
                  className={({ isActive }) =>
                    [
                      'flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-medium transition',
                      isActive
                        ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                        : 'text-stone-700 hover:bg-stone-100 hover:text-stone-950',
                    ].join(' ')
                  }
                >
                  <Icon className="size-4" />
                  <span>{resource.label}</span>
                </NavLink>
              )
            })}
          </nav>

          <div className="rounded-xl border border-stone-200 bg-white p-4 shadow-sm shadow-stone-200/60">
            <p className="text-sm font-semibold text-stone-950">{user?.full_name}</p>
            <p className="mt-1 text-sm text-stone-600">{user?.email}</p>
            <p className="mt-2 text-xs font-medium uppercase tracking-[0.08em] text-stone-500">
              {formatRoleLabel(primaryRole)}
            </p>
            {assignedSiteId ? (
              <p className="mt-1 text-xs text-stone-500">Assigned site #{assignedSiteId}</p>
            ) : null}
            <button
              type="button"
              onClick={() => setIsLogoutConfirmOpen(true)}
              className="mt-4 inline-flex items-center gap-2 rounded-md border border-stone-300 px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50"
            >
              <LogOut className="size-4" />
              Logout
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="border-b border-stone-200 bg-white/90 px-4 py-4 backdrop-blur sm:px-6 lg:px-8">
            <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-stone-500">
                  Occupational Health and Safety
                </p>
                <h1 className="mt-1 text-xl font-semibold tracking-tight text-stone-950 sm:text-2xl">
                  {getPageTitle(location.pathname)}
                </h1>
              </div>
              <div className="flex items-center gap-3">
                <div className="inline-flex items-center gap-2 rounded-full border border-stone-200 bg-stone-50 px-3 py-2 text-sm text-stone-700">
                  <Bell className="size-4 text-amber-600" />
                  <span>{formatValue(unreadCount, 'number')} unread</span>
                </div>
                <button
                  type="button"
                  onClick={() => setIsLogoutConfirmOpen(true)}
                  className="inline-flex items-center gap-2 rounded-md border border-stone-300 bg-white px-3 py-2 text-sm font-medium text-stone-700 transition hover:bg-stone-50 lg:hidden"
                >
                  <LogOut className="size-4" />
                  Logout
                </button>
              </div>
            </div>
            <div className="mt-4 flex gap-2 overflow-x-auto pb-1 lg:hidden">
              {showDashboard ? (
                <NavLink
                  to="/dashboard"
                  className={({ isActive }) =>
                    [
                      'inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition',
                      isActive
                        ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                        : 'bg-stone-100 text-stone-700 hover:bg-stone-200',
                    ].join(' ')
                  }
                >
                  <LayoutDashboard className="size-4" />
                  Dashboard
                </NavLink>
              ) : null}
              {showQuickReport ? (
                <NavLink
                  to="/quick-report"
                  className={({ isActive }) =>
                    [
                      'inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition',
                      isActive
                        ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                        : 'bg-stone-100 text-stone-700 hover:bg-stone-200',
                    ].join(' ')
                  }
                >
                  <Smartphone className="size-4" />
                  Quick Report
                </NavLink>
              ) : null}
              {visibleResources.map((resource) => {
                const Icon = resource.icon

                return (
                  <NavLink
                    key={resource.key}
                    to={resource.route}
                    className={({ isActive }) =>
                      [
                        'inline-flex shrink-0 items-center gap-2 rounded-full px-3 py-2 text-sm font-medium transition',
                        isActive
                          ? 'bg-emerald-100 text-emerald-900 shadow-sm'
                          : 'bg-stone-100 text-stone-700 hover:bg-stone-200',
                      ].join(' ')
                    }
                  >
                    <Icon className="size-4" />
                    {resource.label}
                  </NavLink>
                )
              })}
            </div>
          </header>

          <main className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <Outlet />
          </main>
        </div>
      </div>
      <ConfirmDialog
        isOpen={isLogoutConfirmOpen}
        title="Sign out of the workspace?"
        description="This will clear the current session from the browser and return you to the login screen."
        confirmLabel="Sign out"
        tone="danger"
        onClose={() => setIsLogoutConfirmOpen(false)}
        onConfirm={logout}
      />
    </div>
  )
}
