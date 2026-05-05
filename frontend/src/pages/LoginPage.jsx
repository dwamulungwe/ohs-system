import { ShieldCheck } from 'lucide-react'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { canViewDashboard, canViewResource, getDefaultRoute } from '../lib/rbac.js'

export function LoginPage() {
  const { login, isAuthenticated, user } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('AdminPass123')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState('')

  const from = location.state?.from?.pathname ?? '/dashboard'

  function resolveDestination(currentUser) {
    if (from === '/dashboard') {
      return getDefaultRoute(currentUser)
    }

    const resourceKey = from.startsWith('/') ? from.slice(1).split('/')[0] : ''
    if (from === '/dashboard' && canViewDashboard(currentUser)) return from
    if (resourceKey && canViewResource(resourceKey, currentUser)) {
      return from
    }
    return getDefaultRoute(currentUser)
  }

  useEffect(() => {
    if (isAuthenticated && user) {
      navigate(getDefaultRoute(user), { replace: true })
    }
  }, [isAuthenticated, navigate, user])

  async function handleSubmit(event) {
    event.preventDefault()
    setIsSubmitting(true)
    setError('')

    try {
      const currentUser = await login(email, password)
      navigate(resolveDestination(currentUser), { replace: true })
    } catch (requestError) {
      setError(requestError.message ?? 'Unable to sign in')
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="grid w-full max-w-5xl overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-xl lg:grid-cols-[1.1fr_0.9fr]">
        <section className="hidden bg-[#16352f] p-10 text-white lg:flex lg:flex-col lg:justify-between">
          <div>
            <div className="inline-flex items-center gap-3 rounded-lg bg-white/8 px-4 py-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-emerald-500">
                <ShieldCheck className="size-5" />
              </div>
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.14em] text-emerald-200">
                  OHS Management System
                </p>
                <p className="text-lg font-semibold">Role-Aware Workspace</p>
              </div>
            </div>
            <h1 className="mt-12 max-w-md text-4xl font-semibold leading-tight">
              Keep incidents, hazards, inspections, and actions visible in one place.
            </h1>
            <p className="mt-5 max-w-lg text-sm leading-7 text-emerald-50/90">
              This frontend is wired directly to the local FastAPI backend so you can
              review the live operational data model and test the system manually.
            </p>
          </div>
          <div className="grid grid-cols-2 gap-4">
            {[
              ['Dashboard', 'Live overview metrics'],
              ['Notifications', 'Actionable reminders'],
              ['Permits', 'Permit-to-work visibility'],
              ['Training', 'Compliance status tracking'],
            ].map(([title, text]) => (
              <div key={title} className="rounded-lg border border-white/10 bg-white/5 p-4">
                <p className="text-sm font-semibold">{title}</p>
                <p className="mt-2 text-sm text-emerald-50/80">{text}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="p-8 sm:p-10">
          <div className="mx-auto max-w-md">
            <p className="text-sm font-semibold uppercase tracking-[0.14em] text-emerald-700">
              Sign In
            </p>
            <h2 className="mt-2 text-3xl font-semibold tracking-tight text-stone-950">
              Access your OHS workspace
            </h2>
            <p className="mt-3 text-sm leading-6 text-stone-600">
              Use your API credentials to connect to the running OHS backend.
            </p>

            <form className="mt-10 space-y-5" onSubmit={handleSubmit}>
              <label className="block">
                <span className="text-sm font-medium text-stone-700">Email</span>
                <input
                  type="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  className="mt-2 w-full rounded-lg border border-stone-300 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10"
                  autoComplete="email"
                  required
                />
              </label>

              <label className="block">
                <span className="text-sm font-medium text-stone-700">Password</span>
                <input
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  className="mt-2 w-full rounded-lg border border-stone-300 bg-white px-4 py-3 text-sm text-stone-900 outline-none transition focus:border-emerald-500 focus:ring-4 focus:ring-emerald-500/10"
                  autoComplete="current-password"
                  required
                />
              </label>

              {error ? (
                <div className="rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={isSubmitting}
                className="inline-flex w-full items-center justify-center rounded-lg bg-emerald-600 px-4 py-3 text-sm font-semibold text-white transition hover:bg-emerald-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {isSubmitting ? 'Signing in...' : 'Sign in'}
              </button>
            </form>
          </div>
        </section>
      </div>
    </div>
  )
}
