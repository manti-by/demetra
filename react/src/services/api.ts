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

export async function exchangeCodeForToken(code: string, state: string): Promise<AuthResponse> {
  const response = await fetch(`${API_URL}/api/v1/github/callback?code=${code}&state=${state}`, {
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
  name: string | null;
  build_plan: string | null;
  posted_to_linear: boolean;
  created_at: string;
  updated_at: string;
  status: string | null;
  state: string | null;
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

export interface Project {
  id: string;
  user_id: string | null;
  linear_project_id: string | null;
  name: string;
  repository_url: string;
  local_path: string | null;
  created_at: string;
  updated_at: string;
}

export async function getProjects(): Promise<Project[]> {
  const response = await fetch(`${API_URL}/api/v1/projects`, {
    credentials: 'include',
  });
  if (!response.ok) {
    throw new Error('Failed to fetch projects');
  }
  return response.json();
}

export async function createProject(data: {
  name: string;
  repository_url: string;
  linear_project_id?: string;
}): Promise<Project> {
  const response = await fetch(`${API_URL}/api/v1/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to create project');
  }
  return response.json();
}

export async function updateProject(
  projectId: string,
  data: {
    name?: string;
    repository_url?: string;
    linear_project_id?: string;
  }
): Promise<Project> {
  const response = await fetch(`${API_URL}/api/v1/projects/${projectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    credentials: 'include',
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update project');
  }
  return response.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await fetch(`${API_URL}/api/v1/projects/${projectId}`, {
    method: 'DELETE',
    credentials: 'include',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete project');
  }
}
