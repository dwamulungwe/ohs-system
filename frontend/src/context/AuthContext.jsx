import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { apiClient } from '../api/client.js'
import {
  clearStoredToken,
  getStoredToken,
  setStoredToken,
} from '../lib/storage.js'
import { getPrimaryRole, getRoleNames } from '../lib/rbac.js'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => getStoredToken())
  const [user, setUser] = useState(null)
  const [isInitializing, setIsInitializing] = useState(true)

  useEffect(() => {
    let ignore = false

    async function bootstrap() {
      if (!token) {
        setIsInitializing(false)
        return
      }

      try {
        const currentUser = await apiClient.getCurrentUser(token)
        if (!ignore) {
          setUser(currentUser)
        }
      } catch {
        clearStoredToken()
        if (!ignore) {
          setToken(null)
          setUser(null)
        }
      } finally {
        if (!ignore) {
          setIsInitializing(false)
        }
      }
    }

    bootstrap()

    return () => {
      ignore = true
    }
  }, [token])

  async function login(email, password) {
    const auth = await apiClient.login(email, password)
    setStoredToken(auth.access_token)
    setToken(auth.access_token)
    const currentUser = await apiClient.getCurrentUser(auth.access_token)
    setUser(currentUser)
    return currentUser
  }

  function logout() {
    clearStoredToken()
    setToken(null)
    setUser(null)
  }

  const value = useMemo(
    () => ({
      token,
      user,
      roleNames: getRoleNames(user),
      primaryRole: getPrimaryRole(user),
      assignedSiteId: user?.assigned_site_id ?? null,
      isAuthenticated: Boolean(token && user),
      isInitializing,
      login,
      logout,
    }),
    [token, user, isInitializing],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)

  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }

  return context
}
