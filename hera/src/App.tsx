import { lazy, Suspense, useCallback } from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { GitHubLoginButton } from './components/GitHubLoginButton';
import { Header } from './components/Header';
import './App.css';

const GitHubCallback = lazy(() => import('./pages/GitHubCallback').then(m => ({ default: m.GitHubCallback })));
const LogConsole = lazy(() => import('./components/LogConsole').then(m => ({ default: m.LogConsole })));

const LOGIN_TITLE = 'Demetra';
const LOGIN_SUBTITLE = 'AI-powered workflow orchestration for developers. Automate your development workflow with intelligent agents.';

function LoadingSpinner() {
  return (
    <div className="loading-container">
      <div className="loading-spinner" />
    </div>
  );
}

function LoginView() {
  return (
    <div className="login-container">
      <h1 className="login-title">{LOGIN_TITLE}</h1>
      <p className="login-subtitle">{LOGIN_SUBTITLE}</p>
      <GitHubLoginButton />
    </div>
  );
}

function AppContent() {
  const { user, loading, logout } = useAuth();

  const handleLogout = useCallback(async () => {
    await logout();
    window.location.reload();
  }, [logout]);

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div className="app">
      <Header user={user} onLogout={handleLogout} />
      <main className="main-content">
        {user ? (
          <Suspense fallback={<div className="loading-container"><div className="loading-spinner" /></div>}>
            <LogConsole />
          </Suspense>
        ) : (
          <LoginView />
        )}
      </main>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          <Route path="/" element={<AppContent />} />
          <Route path="/github/callback" element={<GitHubCallback />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}

export default App;
