import './App.css';
import { AuthProvider, useAuth } from './contexts/AuthContext';
import { GitHubLoginButton } from './components/GitHubLoginButton';

function AppContent() {
  const { user, loading } = useAuth();

  if (loading) {
    return <div className="app">Loading...</div>;
  }

  return (
    <div className="app">
      {user ? <h1>Hello to Demetra</h1> : <GitHubLoginButton />}
    </div>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}

export default App;
