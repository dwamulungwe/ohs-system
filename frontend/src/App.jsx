import { Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from './layouts/AppShell.jsx'
import { LoginPage } from './pages/LoginPage.jsx'
import { DashboardPage } from './pages/DashboardPage.jsx'
import { ProtectedRoute } from './components/ProtectedRoute.jsx'
import { ResourceListPage } from './pages/ResourceListPage.jsx'
import { ResourceDetailPage } from './pages/ResourceDetailPage.jsx'
import { QuickReportPage } from './pages/QuickReportPage.jsx'
import { resources } from './config/resources.jsx'
import { useAuth } from './context/AuthContext.jsx'
import { getDefaultRoute } from './lib/rbac.js'

function HomeRedirect() {
  const { user } = useAuth()
  return <Navigate to={getDefaultRoute(user)} replace />
}

function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedRoute />}>
        <Route element={<AppShell />}>
          <Route index element={<HomeRedirect />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/quick-report" element={<QuickReportPage />} />
          {resources.map((resource) => (
            <Route key={resource.key}>
              <Route
                path={resource.route}
                element={<ResourceListPage resource={resource} />}
              />
              {resource.detailEndpoint ? (
                <Route
                  path={`${resource.route}/:id`}
                  element={<ResourceDetailPage resource={resource} />}
                />
              ) : null}
            </Route>
          ))}
        </Route>
      </Route>
      <Route path="*" element={<HomeRedirect />} />
    </Routes>
  )
}

export default App
