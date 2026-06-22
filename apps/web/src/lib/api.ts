import { getAuthToken, triggerUnauthorized } from "@/contexts/AuthContext"

export type Project = {
  id: number
  name: string
  key: string
  description?: string | null
  created_at: string
  updated_at: string
}

export type ProjectMember = {
  id: number
  project_id: number
  email: string
  display_name?: string | null
  role: string
  created_at: string
}

export type ProjectInviteRead = {
  id: number
  project_id: number
  project_name: string
  token: string
  role: string
  expires_at: string
  created_at: string
}

export type Status = {
  id: number
  name: string
  category: string
  color: string
  position: string
}

export type Label = {
  id: number
  name: string
  color: string
}

export type Task = {
  id: number
  key?: string | null
  sequence_number?: number | null
  rank: string
  project_id: number
  status_id: number
  title: string
  description?: string | null
  priority: string
  assignee?: string | null
  due_date?: string | null
  archived: boolean
  position: string
  labels: Label[]
  created_at: string
  updated_at: string
}

export type BoardColumn = {
  status: Status
  tasks: Task[]
}

export type Board = {
  project: Project
  columns: BoardColumn[]
}

export type AIResponsePresentation = {
  title: string
  summary: string
  highlights: string[]
  next_steps: string[]
}

export type AIQueryResponse = {
  answer: string
  sql: string
  rows: Array<Record<string, unknown>>
  used_model: string
  fallback: boolean
  action: string
  affected_tasks: Task[]
  presentation?: AIResponsePresentation | null
}

export type Suggestion = {
  label: string
  prompt: string
}

export type SuggestionsResponse = {
  suggestions: Suggestion[]
}

export type AuthUser = {
  id: number
  email: string
  display_name: string | null
  is_active: boolean
}

export type TokenResponse = {
  access_token: string
  token_type: string
  user: AuthUser
}

export type MembershipResponse = {
  role: "admin" | "viewer" | null
  is_member: boolean
}

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "" : "http://127.0.0.1:8000")

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAuthToken()
  const headers: Record<string, string> = {
    "content-type": "application/json",
    ...(init?.headers as Record<string, string>),
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`
  }
  const response = await fetch(`${API_BASE}${path}`, { ...init, headers })
  if (response.status === 401) {
    triggerUnauthorized()
    throw new Error("Authentication required")
  }
  if (!response.ok) {
    throw new Error(await response.text())
  }
  if (response.status === 204) return undefined as T
  return response.json() as Promise<T>
}

export const api = {
  // ── Auth ──────────────────────────────────────────────────────────────────
  auth: {
    register: (email: string, password: string, displayName?: string) =>
      request<TokenResponse>("/api/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password, display_name: displayName ?? null }),
      }),
    login: (email: string, password: string) =>
      request<TokenResponse>("/api/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    me: () => request<AuthUser>("/api/auth/me"),
  },

  // ── Projects ──────────────────────────────────────────────────────────────
  listProjects: () => request<Project[]>("/api/projects"),
  createProject: (payload: { name: string; key: string; description?: string }) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  getProject: (projectId: number) => request<Project>(`/api/projects/${projectId}`),
  membership: (projectId: number) =>
    request<MembershipResponse>(`/api/projects/${projectId}/membership`),

  // ── Board ─────────────────────────────────────────────────────────────────
  board: (projectId: number) => request<Board>(`/api/projects/${projectId}/board`),
  archivedTasks: (projectId: number) =>
    request<Task[]>(`/api/projects/${projectId}/archived`),

  // ── Tasks ─────────────────────────────────────────────────────────────────
  createTask: (projectId: number, payload: Partial<Task> & { title: string }) =>
    request<Task>(`/api/projects/${projectId}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (taskId: number, payload: Partial<Task>) =>
    request<Task>(`/api/tasks/${taskId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  moveTask: (taskId: number, statusId: number, afterTaskId?: number, beforeTaskId?: number) =>
    request<Task>(`/api/tasks/${taskId}/move`, {
      method: "POST",
      body: JSON.stringify({
        status_id: statusId,
        after_task_id: afterTaskId,
        before_task_id: beforeTaskId,
      }),
    }),
  archiveTask: (taskId: number) =>
    request<Task>(`/api/tasks/${taskId}/archive`, { method: "POST" }),
  restoreTask: (taskId: number) =>
    request<Task>(`/api/tasks/${taskId}/restore`, { method: "POST" }),

  // ── AI ────────────────────────────────────────────────────────────────────
  aiQuery: (projectId: number, question: string, signal?: AbortSignal) =>
    request<AIQueryResponse>("/api/ai/query", {
      method: "POST",
      signal,
      body: JSON.stringify({ project_id: projectId, question }),
    }),
  aiSuggestions: (projectId: number) =>
    request<SuggestionsResponse>(`/api/projects/${projectId}/ai/suggestions`),

  // ── Members ───────────────────────────────────────────────────────────────
  listMembers: (projectId: number) =>
    request<ProjectMember[]>(`/api/projects/${projectId}/members`),
  addMember: (projectId: number, payload: { email: string; role: string }) =>
    request<ProjectMember>(`/api/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  removeMember: (memberId: number) =>
    request<void>(`/api/members/${memberId}`, { method: "DELETE" }),

  // ── Invites ───────────────────────────────────────────────────────────────
  createInvite: (projectId: number, payload: { role: string; expires_in_hours?: number }) =>
    request<ProjectInviteRead>(`/api/projects/${projectId}/invites`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getInvite: (token: string) => request<ProjectInviteRead>(`/api/invites/${token}`),
  acceptInvite: (token: string, displayName?: string) =>
    request<{ project_id: number }>(`/api/invites/${token}/accept`, {
      method: "POST",
      body: JSON.stringify({ name: displayName ?? null }),
    }),
}
