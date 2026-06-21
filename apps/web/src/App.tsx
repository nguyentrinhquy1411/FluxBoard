import { createRootRoute, createRoute, createRouter, Outlet, RouterProvider, Link, useRouterState, useNavigate } from "@tanstack/react-router"
import { QueryClient, QueryClientProvider, useQuery, useMutation, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { AIAssistantSidebar } from "@/components/AIAssistant"
import { KanbanBoard } from "@/components/KanbanBoard"
import { ProjectSwitcher } from "@/components/ProjectSwitcher"
import { ProjectMembers } from "@/components/ProjectMembers"
import { IdentityModal } from "@/components/IdentityModal"
import { UserProvider, useUser } from "@/contexts/UserContext"
import { useProjectRole } from "@/hooks/useProjectRole"
import { useState } from "react"
import { Archive, LayoutDashboard, Sparkles, Bot, RotateCcw, UserPlus, Shield, Eye, LogOut } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"

const rootRoute = createRootRoute({
  component: RootLayout,
})

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeRoute,
})

const projectRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId",
  component: ProjectRoute,
})

const projectArchivedRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/archived",
  component: ProjectArchivedRoute,
})

const joinRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/join/$token",
  component: JoinRoute,
})

const routeTree = rootRoute.addChildren([indexRoute, projectRoute, projectArchivedRoute, joinRoute])
const router = createRouter({ routeTree })
const queryClient = new QueryClient()

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

function RootLayout() {
  const [showAIPanel, setShowAIPanel] = useState(() => {
    return localStorage.getItem("show-ai-panel") !== "false"
  })

  const toggleAIPanel = () => {
    setShowAIPanel((prev) => {
      const next = !prev
      localStorage.setItem("show-ai-panel", String(next))
      return next
    })
  }

  // Extract projectId if we are on a project-specific route
  const matches = useRouterState({ select: (s) => s.matches })
  const projectMatch = matches.find((m) => m.pathname.includes("/projects/"))
  const projectId = projectMatch ? (projectMatch.params as { projectId?: string }).projectId : undefined
  const projectRole = useProjectRole(projectId ? Number(projectId) : 0)

  return (
    <div className="flex min-h-screen w-screen overflow-hidden bg-slate-50 font-sans">
        {/* Left Sidebar */}
        <aside className="w-64 min-w-[256px] h-screen max-h-screen bg-slate-900 text-slate-100 flex flex-col justify-between p-4 border-r border-slate-800 shadow-md select-none shrink-0 overflow-hidden">
          <div className="flex flex-col gap-6 overflow-y-auto flex-1 pr-1">
            {/* Logo */}
            <div className="flex items-center gap-2 px-2 py-1 shrink-0">
              <Sparkles className="h-6 w-6 text-blue-400" />
              <span className="text-lg font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-200 bg-clip-text text-transparent">
                CPV Kanban AI
              </span>
            </div>

            {/* Project Switcher section */}
            <div className="flex flex-col gap-1 px-2 shrink-0">
              <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Select Project
              </span>
              <ProjectSwitcher projectId={projectId ? Number(projectId) : undefined} />
            </div>

            {/* Navigation links if a project is selected */}
            {projectId && (
              <div className="flex flex-col gap-1 flex-1">
                <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider px-2 mb-2">
                  Project Workspace
                </span>
                <Link
                  to="/projects/$projectId"
                  params={{ projectId }}
                  activeProps={{ className: "bg-blue-600/20 text-blue-400 font-semibold" }}
                  inactiveProps={{ className: "text-slate-400 hover:bg-slate-800 hover:text-slate-100" }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm shrink-0"
                >
                  <LayoutDashboard className="h-4 w-4" />
                  <span>Kanban Board</span>
                </Link>
                <Link
                  to="/projects/$projectId/archived"
                  params={{ projectId }}
                  activeProps={{ className: "bg-blue-600/20 text-blue-400 font-semibold" }}
                  inactiveProps={{ className: "text-slate-400 hover:bg-slate-800 hover:text-slate-100" }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm shrink-0"
                >
                  <Archive className="h-4 w-4" />
                  <span>Archived Tasks</span>
                </Link>

                <div className="mt-4 pt-4 border-t border-slate-800/60">
                  <ProjectMembers projectId={Number(projectId)} isAdmin={projectRole.isAdmin} />
                </div>
              </div>
            )}
          </div>

          {/* Bottom section: identity + AI toggle */}
          <div className="flex flex-col gap-2 pt-4 border-t border-slate-800/80 shrink-0">
            {/* Current identity widget */}
            <IdentityWidget projectId={projectId ? Number(projectId) : undefined} />

            {/* AI panel control toggle */}
            {projectId && (
              <div className="pt-2 border-t border-slate-800">
                <button
                  onClick={toggleAIPanel}
                  className="w-full flex justify-between items-center bg-slate-800 hover:bg-slate-700 hover:text-white px-3 py-2.5 rounded-lg text-sm text-slate-300 transition-colors"
                >
                  <span className="flex items-center gap-2">
                    <Bot className="h-4 w-4 text-blue-400" />
                    <span>AI Copilot Panel</span>
                  </span>
                  <span className={`w-8 h-4 rounded-full p-0.5 transition-colors duration-200 ${showAIPanel ? 'bg-blue-500' : 'bg-slate-600'}`}>
                    <span className={`block w-3 h-3 rounded-full bg-white transition-transform duration-200 ${showAIPanel ? 'translate-x-4' : 'translate-x-0'}`} />
                  </span>
                </button>
              </div>
            )}
          </div>
        </aside>

        {/* Main Content Area */}
      <main className="flex-1 overflow-y-auto p-6 min-w-0">
        <Outlet />
      </main>
      {projectId && showAIPanel && (
        <AIAssistantSidebar projectId={Number(projectId)} isAdmin={projectRole.isAdmin} />
      )}
      </div>
  )
}

function HomeRoute() {
  const { currentEmail } = useUser()
  const projects = useQuery({
    queryKey: ["projects", currentEmail],
    queryFn: () => api.listProjects(currentEmail),
  })
  return (
    <div className="rounded-lg border border-border bg-white p-8">
      <h1 className="text-2xl font-semibold">Choose or create a project</h1>
      <p className="mt-2 text-muted-foreground">
        The board, task drawer, and AI analyst appear after a project is selected.
      </p>
      {projects.data?.length === 0 && (
        <p className="mt-4 text-sm">Create your first project from the control in the sidebar.</p>
      )}
    </div>
  )
}

function ProjectRoute() {
  const { projectId } = projectRoute.useParams()
  const { currentEmail } = useUser()

  const projectQuery = useQuery({
    queryKey: ["project", Number(projectId)],
    queryFn: () => api.getProject(Number(projectId)),
  })

  const isSmokeProject = projectQuery.data?.key === "SMOKE"
  const needsIdentity = currentEmail === "local-user@example.com" && !isSmokeProject && !projectQuery.isLoading

  const boardEnabled = !projectQuery.isLoading && (
    currentEmail !== "local-user@example.com" || isSmokeProject
  )


  return (
    <>
      {needsIdentity && projectQuery.data && (
        <IdentityModal
          projectId={Number(projectId)}
          projectName={projectQuery.data.name}
        />
      )}
      {boardEnabled ? (
        <KanbanBoard projectId={Number(projectId)} />
      ) : (
        <div className="flex items-center justify-center p-12">
          <Skeleton className="h-64 w-full" />
        </div>
      )}
    </>
  )
}

function ProjectArchivedRoute() {
  const { projectId } = projectArchivedRoute.useParams()
  const queryClient = useQueryClient()
  const { isAdmin } = useProjectRole(Number(projectId))
  const archived = useQuery({
    queryKey: ["archived", Number(projectId)],
    queryFn: () => api.archivedTasks(Number(projectId)),
  })
  const restore = useMutation({
    mutationFn: api.restoreTask,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["archived", Number(projectId)] })
      queryClient.invalidateQueries({ queryKey: ["board", Number(projectId)] })
    },
  })

  return (
    <div className="w-full">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold flex items-center gap-2 text-slate-800">
          <Archive className="h-6 w-6 text-slate-600" />
          Archived Tasks
        </h1>
        <p className="text-sm text-slate-500">
          View and restore cards that were archived from the main board.
        </p>
      </div>

      <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
        {archived.isLoading && <div className="space-y-4"><Skeleton className="h-12 w-full" /><Skeleton className="h-12 w-full" /></div>}
        {archived.isError && (
          <p className="text-sm text-red-600">Could not load archived tasks.</p>
        )}
        {archived.data?.length === 0 && (
          <p className="text-slate-400 text-sm py-4 text-center">No archived tasks in this project.</p>
        )}
        
        {archived.data && archived.data.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {archived.data.map((task) => (
              <div key={task.id} className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between gap-4">
                <div>
                  <div className="text-[10px] font-semibold text-blue-600 mb-1">
                    {task.key ?? `#${task.id}`}
                  </div>
                  <h3 className="text-sm font-semibold text-slate-800 leading-snug">{task.title}</h3>
                  {task.description && (
                    <p className="text-xs text-slate-500 mt-1 line-clamp-2">{task.description}</p>
                  )}
                </div>
                
                <div className="flex items-center justify-between mt-2 pt-3 border-t border-slate-100">
                  <span className="text-xs capitalize px-2 py-0.5 bg-slate-200 text-slate-600 rounded font-medium">
                    {task.priority}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={!isAdmin || restore.isPending}
                    onClick={() => restore.mutate(task.id)}
                    className="h-8 text-xs gap-1 hover:bg-blue-50 hover:text-blue-600 hover:border-blue-200"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    {isAdmin ? "Restore" : "View only"}
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
function JoinRoute() {
  const { token } = joinRoute.useParams()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { setIdentity } = useUser()
  const [name, setName] = useState("")
  const [email, setEmail] = useState("")

  const inviteStatus = useQuery({
    queryKey: ["inviteStatus", token],
    queryFn: () => api.getInvite(token),
    retry: false,
  })

  const acceptInvite = useMutation({
    mutationFn: () => api.acceptInvite(token, { email, name: name.trim() || undefined }),
    onSuccess: (data) => {
      setIdentity(email)
      queryClient.invalidateQueries({ queryKey: ["members", data.project_id] })
      navigate({ to: "/projects/$projectId", params: { projectId: String(data.project_id) } })
    },
  })

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault()
    if (!email.trim() || acceptInvite.isPending) return
    acceptInvite.mutate()
  }

  if (inviteStatus.isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-8">
          <Skeleton className="h-12 w-12 rounded-full mx-auto mb-4 bg-white/10" />
          <Skeleton className="h-6 w-3/4 mx-auto mb-2 bg-white/10" />
          <Skeleton className="h-4 w-1/2 mx-auto mb-6 bg-white/10" />
          <Skeleton className="h-10 w-full mb-3 bg-white/10" />
          <Skeleton className="h-10 w-full mb-4 bg-white/10" />
          <Skeleton className="h-11 w-full bg-white/10" />
        </div>
      </div>
    )
  }

  if (inviteStatus.isError) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white/5 backdrop-blur-sm rounded-2xl border border-red-500/30 p-8 text-center">
          <div className="h-14 w-14 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
            <span className="text-2xl">⚠️</span>
          </div>
          <h2 className="text-xl font-bold text-white mb-2">Invalid or Expired Invite</h2>
          <p className="text-sm text-slate-400">
            This invitation link has expired or is invalid. Please ask the project administrator for a new invite link.
          </p>
        </div>
      </div>
    )
  }

  const invite = inviteStatus.data!

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      {/* Background glow */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        {/* Card */}
        <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
          {/* Header band */}
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center">
                <UserPlus className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-blue-200 text-xs font-semibold uppercase tracking-wider">You've been invited</p>
                <h1 className="text-white text-lg font-bold leading-tight">{invite.project_name}</h1>
              </div>
            </div>
            <div className="mt-3 inline-flex items-center gap-1.5 bg-white/15 rounded-full px-3 py-1">
              <span className="h-2 w-2 rounded-full bg-green-400" />
              <span className="text-white/90 text-xs font-medium capitalize">{invite.role} access</span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleJoin} className="px-8 py-7 space-y-4">
            <p className="text-sm text-slate-400">
              Fill in your details to join this workspace. Your name will be visible to other team members.
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Your Name
              </label>
              <Input
                type="text"
                placeholder="Jane Smith"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-blue-500/20"
              />
            </div>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Email Address <span className="text-red-400">*</span>
              </label>
              <Input
                type="email"
                placeholder="jane@company.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full bg-white/5 border-white/10 text-white placeholder:text-slate-500 focus:border-blue-500 focus:ring-blue-500/20"
              />
            </div>

            {acceptInvite.isError && (
              <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">
                Failed to join: {(acceptInvite.error as Error).message}
              </p>
            )}

            <Button
              type="submit"
              className="w-full h-11 bg-blue-600 hover:bg-blue-500 text-white font-semibold text-sm rounded-xl transition-all duration-200 shadow-lg shadow-blue-600/30 hover:shadow-blue-500/40"
              disabled={!email.trim() || acceptInvite.isPending}
            >
              {acceptInvite.isPending ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Joining...
                </span>
              ) : (
                <span className="flex items-center gap-2">
                  <UserPlus className="h-4 w-4" />
                  Accept & Join Workspace
                </span>
              )}
            </Button>

            <p className="text-center text-[11px] text-slate-600">
              This link expires {new Date(invite.expires_at).toLocaleString()}
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}


export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <UserProvider>
        <RouterProvider router={router} />
      </UserProvider>
    </QueryClientProvider>
  )
}

// ── Identity Widget ─────────────────────────────────────────────────────────

function IdentityWidget({ projectId }: { projectId?: number }) {
  const { currentEmail, clearIdentity, isLocalUser } = useUser()
  const { role } = useProjectRole(projectId ?? 0)

  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId!),
    enabled: projectId != null && projectId > 0,
  })

  const member = members.data?.find((m) => m.email === currentEmail)
  const displayName = member?.display_name ?? (isLocalUser ? "Local User" : currentEmail)

  const handleSwitch = () => {
    clearIdentity()
  }

  return (
    <div className="border-t border-slate-800 pt-3">
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-800/50">
        {/* Role icon */}
        <div className={`h-7 w-7 rounded-full flex items-center justify-center shrink-0 ${
          role === "admin" || isLocalUser ? "bg-blue-600/30" : "bg-amber-600/20"
        }`}>
          {role === "admin" || isLocalUser ? (
            <Shield className="h-3.5 w-3.5 text-blue-400" />
          ) : (
            <Eye className="h-3.5 w-3.5 text-amber-400" />
          )}
        </div>

        {/* Name + role */}
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-slate-200 truncate">{displayName}</p>
          <p className={`text-[10px] font-medium capitalize ${
            role === "admin" || isLocalUser ? "text-blue-400" : "text-amber-400"
          }`}>
            {isLocalUser ? "admin" : role ?? "unknown"}
          </p>
        </div>

        {/* Switch button */}
        <button
          onClick={handleSwitch}
          title="Switch user"
          className="text-slate-500 hover:text-slate-200 transition-colors p-1 rounded"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}
