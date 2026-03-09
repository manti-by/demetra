const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
  id: string;
  github_username: string;
  email: string;
}

export interface AuthResponse {
  token: string;
  user: User;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/github/me`, {
      credentials: 'include',
    });
    if (!response.ok) {
      return null;
    }
    const data = await response.json();
    return data;
  } catch (error) {
    return null;
  }
}

export async function exchangeCodeForToken(code: string): Promise<AuthResponse> {
  const response = await fetch(`${API_URL}/api/v1/github/callback?code=${code}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to exchange code');
  }
  return response.json();
}

export async function logout(): Promise<void> {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
  try {
    await fetch(`${API_URL}/api/v1/github/logout`, {
      method: 'POST',
      credentials: 'include',
    });
  } catch {
    // Ignore errors
  }
}

export function login(): void {
  window.location.href = `${API_URL}/api/v1/github/login`;
}

export async function updateUserKeys(keys: Record<string, string>): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/users/me/keys`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify({ keys }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update keys');
  }
}

export interface Session {
  task_id: string;
  session_id: string;
  build_plan: string | null;
  posted_to_linear: boolean;
  created_at: string;
  updated_at: string;
  status: string | null;
}

export async function getSessions(status?: string): Promise<Session[]> {
  const params = status ? `?status=${status}` : '';
  const response = await fetch(`${API_URL}/api/v1/sessions${params}`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to fetch sessions');
  }
  return response.json();
}
