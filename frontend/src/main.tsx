import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import './index.css'
import { AuthProvider, useAuth } from './context/AuthContext'
import { Layout } from './components/Layout'
import { Login } from './pages/Login'
import { Dashboard } from './pages/Dashboard'
import { Transactions } from './pages/Transactions'
import { Upload } from './pages/Upload'
import { Imports } from './pages/Imports'
import { Budget } from './pages/Budget'

/**
 * Auth gate — shows Login when not authenticated,
 * loading spinner during session restoration.
 */
function AuthGate() {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="login-page">
        <span className="loader" />
      </div>
    );
  }

  if (!user) {
    return <Login />;
  }

  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="transactions" element={<Transactions />} />
          <Route path="upload" element={<Upload />} />
          <Route path="imports" element={<Imports />} />
          <Route path="budget" element={<Budget />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AuthProvider>
      <AuthGate />
    </AuthProvider>
  </StrictMode>,
)
