import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { Loader } from '../components/Loader';
import { exchangeCodeForToken, isWaitlistedError } from '../services/api';

export function GitHubCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);
  const [waitlistMessage, setWaitlistMessage] = useState<string | null>(null);

  const handleCallback = useCallback(async (code: string, state: string) => {
    try {
      const response = await exchangeCodeForToken(code, state);
      if (!response.token) {
        throw new Error('No token in response');
      }
      localStorage.setItem('auth_token', response.token);
      localStorage.setItem('user', JSON.stringify(response.user));
      navigate('/');
    } catch (e) {
      if (isWaitlistedError(e)) {
        setWaitlistMessage(e.message);
      } else {
        setError(e instanceof Error ? e.message : 'Authentication failed');
      }
    }
  }, [navigate]);

  useEffect(() => {
    const code = searchParams.get('code');
    const state = searchParams.get('state');
    if (!code || !state) {
      setError('No code or state provided');
      return;
    }
    handleCallback(code, state);
  }, [searchParams, handleCallback]);

  return (
    <div className="callback-page">
      <div className="callback-content">
        {waitlistMessage ? (
          <div className="callback-waitlist">
            <p className="auth-info" role="status">{waitlistMessage}</p>
            <button type="button" className="auth-link" onClick={() => navigate('/')}>
              Back to sign in
            </button>
          </div>
        ) : error ? (
          <div className="callback-error">{error}</div>
        ) : (
          <Loader size={48} />
        )}
      </div>
    </div>
  );
}

export default GitHubCallback;
