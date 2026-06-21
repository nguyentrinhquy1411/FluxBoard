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

const API_BASE = import.meta.env.VITE_API_BASE_URL || (import.meta.env.PROD ? "" : "http://127.0.0.1:8000")

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const email = localStorage.getItem("cpv-identity") || "local-user@example.com"
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      "content-type": "application/json",
      "X-User-Email": email,
      ...init?.headers,
    },
  })
  if (!response.ok) {
    throw new Error(await response.text())
  }
  return response.json() as Promise<T>
}

export const api = {
  listProjects: (userEmail?: string) =>
    request<Project[]>(
      userEmail ? `/api/projects?user_email=${encodeURIComponent(userEmail)}` : "/api/projects"
    ),
  createProject: (payload: { name: string; key: string; description?: string }) =>
    request<Project>("/api/projects", { method: "POST", body: JSON.stringify(payload) }),
  board: (projectId: number) => request<Board>(`/api/projects/${projectId}/board`),
  archivedTasks: (projectId: number) => request<Task[]>(`/api/projects/${projectId}/archived`),
  createTask: (projectId: number, payload: Partial<Task> & { title: string }) =>
    request<Task>(`/api/projects/${projectId}/tasks`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  updateTask: (taskId: number, payload: Partial<Task>) =>
    request<Task>(`/api/tasks/${taskId}`, { method: "PATCH", body: JSON.stringify(payload) }),
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
  aiQuery: (projectId: number, question: string, userEmail?: string, signal?: AbortSignal) =>
    request<AIQueryResponse>("/api/ai/query", {
      method: "POST",
      signal,
      body: JSON.stringify({ project_id: projectId, question, user_email: userEmail }),
    }),
  aiSuggestions: (projectId: number) =>
    request<SuggestionsResponse>(`/api/projects/${projectId}/ai/suggestions`),
  listMembers: (projectId: number) =>
    request<ProjectMember[]>(`/api/projects/${projectId}/members`),
  addMember: (projectId: number, payload: { email: string; role: string }) =>
    request<ProjectMember>(`/api/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  removeMember: (memberId: number) =>
    request<void>(`/api/members/${memberId}`, { method: "DELETE" }),
  createInvite: (projectId: number, payload: { role: string; expires_in_hours?: number }) =>
    request<ProjectInviteRead>(`/api/projects/${projectId}/invites`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  getInvite: (token: string) =>
    request<ProjectInviteRead>(`/api/invites/${token}`),
  acceptInvite: (token: string, payload: { email: string; name?: string }) =>
    request<{ project_id: number }>(`/api/invites/${token}/accept`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
}
