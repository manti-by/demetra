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
