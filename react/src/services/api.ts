const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
  id: string;
  github_username: string;
  email: string;
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await fetch(`${API_URL}/api/v1/github/me`, {
      credentials: 'include',
    });
    if (!response.ok) {
      return null;
    }
    return response.json();
  } catch {
    return null;
  }
}

export async function logout(): Promise<void> {
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
