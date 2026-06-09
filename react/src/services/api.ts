const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
  id: string;
  github_username: string;
  email: string;
  avatar_url: string | null;
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

export async function exchangeCodeForToken(code: string, state: string): Promise<AuthResponse> {
  const params = new URLSearchParams({ code, state });
  const response = await fetch(`${API_URL}/api/v1/github/callback?${params}`, {
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

export interface Session {
  task_id: string;
  session_id: string;
  name: string | null;
  build_plan: string | null;
  posted_to_linear: boolean;
  created_at: string;
  updated_at: string;
  step: string | null;
  pr_link: string | null;
}

export async function getSessions(): Promise<Session[]> {
  const response = await fetch(`${API_URL}/api/v1/sessions`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to fetch sessions');
  }
  return response.json();
}

export async function deleteSession(taskId: string): Promise<void> {
  try {
    const response = await fetch(`${API_URL}/api/v1/sessions/${taskId}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to delete session');
    }
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Network error deleting session';
    throw new Error(message);
  }
}
