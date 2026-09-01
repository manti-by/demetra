import { useState, type FormEvent } from 'react';
import { signup, loginWithPassword, isWaitlistedError } from '../services/api';
import { Loader } from './Loader';

export function PasswordAuthForm() {
  const [mode, setMode] = useState<'login' | 'signup'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [waitlistMessage, setWaitlistMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setError(null);
    setWaitlistMessage(null);
    setLoading(true);

    try {
      const fn = mode === 'login' ? loginWithPassword : signup;
      const response = await fn(email, password);
      localStorage.setItem('user', JSON.stringify(response.user));
      if (response.token) {
        localStorage.setItem('auth_token', response.token);
      }
      window.location.reload();
    } catch (err) {
      if (isWaitlistedError(err)) {
        setWaitlistMessage(err.message);
      } else {
        setError(err instanceof Error ? err.message : 'Authentication failed');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="password-auth-form">
      <div className="auth-divider">
        <span>or</span>
      </div>
      <form onSubmit={handleSubmit}>
        <div className="auth-field">
          <input
            type="email"
            aria-label="Email address"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            autoComplete="email"
          />
        </div>
        <div className="auth-field">
          <input
            type="password"
            aria-label="Password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
          />
        </div>
        {waitlistMessage && (
          <p className="auth-info" role="status">{waitlistMessage}</p>
        )}
        {error && <p className="auth-error" role="alert">{error}</p>}
        <button type="submit" className="auth-submit" disabled={loading}>
          {loading ? <Loader size={20} /> : mode === 'login' ? 'Sign in' : 'Create account'}
        </button>
      </form>
      <p className="auth-toggle">
        {mode === 'login' ? (
          <>
            No account?{' '}
            <button type="button" className="auth-link" onClick={() => { setMode('signup'); setError(null); }}>
              Create one
            </button>
          </>
        ) : (
          <>
            Already have an account?{' '}
            <button type="button" className="auth-link" onClick={() => { setMode('login'); setError(null); }}>
              Sign in
            </button>
          </>
        )}
      </p>
    </div>
  );
}
