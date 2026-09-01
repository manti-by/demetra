const API_URL = import.meta.env.VITE_API_URL || '';

const API_ORIGIN = resolveApiOrigin();

function resolveApiOrigin(): string {
  if (typeof window === 'undefined') return '';
  if (API_URL) {
    try {
      return new URL(API_URL).origin;
    } catch {
      return window.location.origin;
    }
  }
  return window.location.origin;
}

function assertTrustedOrigin(input: RequestInfo | URL | string): void {
  if (typeof window === 'undefined' || !API_ORIGIN) return;
  const target = new URL(input.toString(), window.location.origin);
  if (target.origin !== API_ORIGIN) {
    throw new Error(`Blocked credentialed request to untrusted origin: ${target.origin}`);
  }
}

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

export interface WaitlistedResponse {
  status: 'waitlisted';
  message: string;
}

export class WaitlistedError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'WaitlistedError';
  }
}

export function isWaitlistedError(error: unknown): error is WaitlistedError {
  return error instanceof WaitlistedError;
}

async function authFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const request = input instanceof Request ? input : undefined;
  const method = (init.method ?? request?.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    assertTrustedOrigin(request?.url ?? input);
  }
  return fetch(input, { ...init, credentials: 'include' });
}

async function authenticatedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  const request = input instanceof Request ? input : undefined;
  const method = (init.method ?? request?.method ?? 'GET').toUpperCase();
  if (method !== 'GET' && method !== 'HEAD' && method !== 'OPTIONS') {
    assertTrustedOrigin(request?.url ?? input);
  }
  return fetch(input, { ...init, credentials: 'include' });
}

export async function getCurrentUser(): Promise<User | null | 'transient'> {
  try {
    const response = await authenticatedFetch(`${API_URL}/api/v1/github/me`);
    if (response.status === 401) {
      return null;
    }
    if (!response.ok) {
      return 'transient';
    }
    const data = await response.json();
    return data;
  } catch {
    return 'transient';
  }
}

export async function exchangeCodeForToken(code: string, state: string): Promise<AuthResponse> {
  const params = new URLSearchParams({ code, state });
  const response = await authFetch(`${API_URL}/api/v1/github/callback?${params}`);
  const data = await response.json();
  if (response.status === 202 && data.status === 'waitlisted') {
    throw new WaitlistedError(data.message);
  }
  if (!response.ok) {
    throw new Error(data.detail || 'Failed to exchange code');
  }
  return data;
}

export async function signup(email: string, password: string): Promise<AuthResponse> {
  const response = await authFetch(`${API_URL}/api/v1/auth/signup`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (response.status === 202 && data.status === 'waitlisted') {
    throw new WaitlistedError(data.message);
  }
  if (!response.ok) {
    throw new Error(data.detail || 'Signup failed');
  }
  return data;
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/sessions`);
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

export interface SessionTokenTotals {
  length: number;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
}

export interface SessionHistoryResponse {
  total: SessionTokenTotals;
  history: SessionHistoryEntry[];
}

export const EMPTY_TOKEN_TOTALS: SessionTokenTotals = {
  length: 0,
  input_tokens: 0,
  output_tokens: 0,
  reasoning_tokens: 0,
  cache_read_tokens: 0,
  cache_write_tokens: 0,
};

export async function getSessionHistory(taskId: string, signal?: AbortSignal): Promise<SessionHistoryResponse> {
  const response = await authenticatedFetch(`${API_URL}/api/v1/sessions/${taskId}/history`, {
    signal,
  });
  if (response.status === 404) return { total: EMPTY_TOKEN_TOTALS, history: [] };
  if (!response.ok) throw new Error('Failed to fetch session history');
  return response.json();
}

export async function deleteSession(taskId: string): Promise<void> {
  try {
    const response = await authenticatedFetch(`${API_URL}/api/v1/sessions/${taskId}`, {
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/projects`);
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/projects`, {
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/projects/${projectId}`, {
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/projects/${projectId}`, {
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
  const response = await authenticatedFetch(`${API_URL}/api/v1/projects/${projectId}/environment`);
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
  type: 'text' | 'encrypted' = 'text',
  previousKey?: string
): Promise<ProjectEnvironmentEntry> {
  const response = await authenticatedFetch(
    `${API_URL}/api/v1/projects/${projectId}/environment/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, type, ...(previousKey ? { previous_key: previousKey } : {}) }),
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
  const response = await authenticatedFetch(
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

export interface UserEnvironmentEntry {
  id: string;
  user_id: string | null;
  key: string;
  value: string;
  type: 'text' | 'encrypted';
}

export async function getUserEnvironment(): Promise<UserEnvironmentEntry[]> {
  const response = await authenticatedFetch(`${API_URL}/api/v1/users/me/env`);
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to fetch shared environment');
  }
  return response.json();
}

export async function upsertUserEnvironment(
  key: string,
  value: string,
  type: 'text' | 'encrypted' = 'text',
  previousKey?: string
): Promise<UserEnvironmentEntry> {
  const response = await authenticatedFetch(
    `${API_URL}/api/v1/users/me/env/${encodeURIComponent(key)}`,
    {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ value, type, ...(previousKey ? { previous_key: previousKey } : {}) }),
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to save shared environment variable');
  }
  return response.json();
}

export async function deleteUserEnvironment(key: string): Promise<void> {
  const response = await authenticatedFetch(
    `${API_URL}/api/v1/users/me/env/${encodeURIComponent(key)}`,
    {
      method: 'DELETE',
    }
  );
  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to delete shared environment variable');
  }
}
