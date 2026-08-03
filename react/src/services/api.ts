const API_URL = import.meta.env.VITE_API_URL || '';

export interface User {
  id: string;
  github_username?: string | null;
  email?: string | null;
  avatar_url?: string | null;
  role?: string | null;
}

export interface AuthResponse {
  token?: string;
  user: User;
}

async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, { ...init, credentials: 'include' });
}

export async function getCurrentUser(): Promise<User | null> {
  try {
    const response = await authFetch(`${API_URL}/api/v1/github/me`);
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
  const response = await authFetch(`${API_URL}/api/v1/github/callback?${params}`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to exchange code');
  }
  return response.json();
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  const response = await authFetch(`${API_URL}/api/v1/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Signup failed');
  }
  return response.json();
}

export async function loginWithPassword(email: string, password: string): Promise<AuthResponse> {
  const response = await authFetch(`${API_URL}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Login failed');
  }
  return response.json();
}

export async function logout(): Promise<void> {
  localStorage.removeItem('auth_token');
  localStorage.removeItem('user');
  try {
    await authFetch(`${API_URL}/api/v1/auth/logout`, {
      method: 'POST',
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
  linear_link: string | null;
}

export async function getSessions(): Promise<Session[]> {
  const response = await authFetch(`${API_URL}/api/v1/sessions`);
  if (!response.ok) {
    throw new Error('Failed to fetch sessions');
  }
  return response.json();
}

export interface SessionHistoryEntry {
  id: string;
  session_id: string;
  step: string;
  created_at: string;
  length: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  reasoning_tokens: number | null;
  cache_read_tokens: number | null;
  cache_write_tokens: number | null;
  context_tokens: number | null;
  model: string | null;
}

export async function getSessionHistory(taskId: string, signal?: AbortSignal): Promise<SessionHistoryEntry[]> {
  const response = await authFetch(`${API_URL}/api/v1/sessions/${taskId}/history`, {
    signal,
  });
  if (response.status === 404) return [];
  if (!response.ok) throw new Error('Failed to fetch session history');
  return response.json();
}

export async function deleteSession(taskId: string): Promise<void> {
  try {
    const response = await authFetch(`${API_URL}/api/v1/sessions/${taskId}`, {
      method: 'DELETE',
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
  const response = await authFetch(`${API_URL}/api/v1/projects`);
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
  const response = await authFetch(`${API_URL}/api/v1/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
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
  const response = await authFetch(`${API_URL}/api/v1/projects/${projectId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to update project');
  }
  return response.json();
}

export async function deleteProject(projectId: string): Promise<void> {
  const response = await authFetch(`${API_URL}/api/v1/projects/${projectId}`, {
    method: 'DELETE',
  });
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete project');
  }
}

export interface ProjectEnvironmentEntry {
  id: string;
  project_id: string;
  key: string;
  value: string;
  type: 'text' | 'encrypted';
}

export async function getProjectEnvironment(projectId: string): Promise<ProjectEnvironmentEntry[]> {
  const response = await authFetch(`${API_URL}/api/v1/projects/${projectId}/environment`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch project environment');
  }
  return response.json();
}

export async function upsertProjectEnvironment(
  projectId: string,
  key: string,
  value: string,
  type: 'text' | 'encrypted' = 'text'
): Promise<ProjectEnvironmentEntry> {
  const response = await authFetch(
    `${API_URL}/api/v1/projects/${projectId}/environment/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, type }),
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to save environment variable');
  }
  return response.json();
}

export async function deleteProjectEnvironment(
  projectId: string,
  key: string
): Promise<void> {
  const response = await authFetch(
    `${API_URL}/api/v1/projects/${projectId}/environment/${encodeURIComponent(key)}`,
    {
      method: 'DELETE',
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete environment variable');
  }
}
