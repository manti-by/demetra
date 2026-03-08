import { useEffect, useState, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { exchangeCodeForToken } from '../services/api';

export function GitHubCallback() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const handleCallback = useCallback(async (code: string) => {
    try {
      const response = await exchangeCodeForToken(code);
      localStorage.setItem('auth_token', response.token);
      localStorage.setItem('user', JSON.stringify(response.user));
      navigate('/');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Authentication failed');
    }
  }, [navigate]);

  useEffect(() => {
    const code = searchParams.get('code');
    if (!code) {
      setError('No code provided');
      return;
    }
    handleCallback(code);
  }, [searchParams, handleCallback]);

  return (
    <div className="callback-page">
      <div className="callback-content">
        {error ? (
          <div className="callback-error">{error}</div>
        ) : (
          <>
            <div className="callback-spinner" />
            <p className="callback-text">Authenticating...</p>
          </>
        )}
      </div>
    </div>
  );
}

export default GitHubCallback;
