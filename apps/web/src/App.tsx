import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
  RouterProvider,
  Link,
  useRouterState,
  useNavigate,
} from "@tanstack/react-router"
import {
  QueryClient,
  QueryClientProvider,
  useQuery,
  useMutation,
  useQueryClient,
} from "@tanstack/react-query"
import { api } from "@/lib/api"
import { AIAssistantSidebar } from "@/components/AIAssistant"
import { KanbanBoard } from "@/components/KanbanBoard"
import { ProjectSwitcher } from "@/components/ProjectSwitcher"
import { ProjectMembers } from "@/components/ProjectMembers"
import { AboutPage } from "@/components/AboutPage"
import { LoginForm } from "@/components/LoginForm"
import { RegisterForm } from "@/components/RegisterForm"
import { AuthProvider, useAuth } from "@/contexts/AuthContext"
import { useProjectRole } from "@/hooks/useProjectRole"
import { useState, useEffect } from "react"
import {
  Archive,
  LayoutDashboard,
  Sparkles,
  Bot,
  RotateCcw,
  UserPlus,
  Shield,
  Eye,
  LogOut,
  LogIn,
  Users,
  Info,
} from "lucide-react"
import { Toaster, toast } from "sonner"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Input } from "@/components/ui/input"

// ── Routes ──────────────────────────────────────────────────────────────────

const rootRoute = createRootRoute({ component: RootLayout })

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: HomeRoute,
})

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: () => <LoginForm />,
})

const registerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/register",
  component: () => <RegisterForm />,
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

const projectMembersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/projects/$projectId/members",
  component: ProjectMembersRoute,
})

const joinRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/join/$token",
  component: JoinRoute,
})

const aboutRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/about",
  component: AboutPage,
})

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  registerRoute,
  projectRoute,
  projectArchivedRoute,
  projectMembersRoute,
  joinRoute,
  aboutRoute,
])
const router = createRouter({ routeTree })
const queryClient = new QueryClient()

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router
  }
}

// ── Root Layout ──────────────────────────────────────────────────────────────

function RootLayout() {
  const [showAIPanel, setShowAIPanel] = useState(() => {
    return localStorage.getItem("show-ai-panel") !== "false"
  })

  const matches = useRouterState({ select: (s) => s.matches })
  const currentPath = matches[matches.length - 1]?.pathname ?? "/"

  const projectMatch = matches.find((m) => m.pathname.includes("/projects/"))
  const projectId = projectMatch
    ? (projectMatch.params as { projectId?: string }).projectId
    : undefined

  // All hooks must be called before any early return
  const projectRole = useProjectRole(projectId ? Number(projectId) : 0)

  const toggleAIPanel = () => {
    setShowAIPanel((prev) => {
      const next = !prev
      localStorage.setItem("show-ai-panel", String(next))
      return next
    })
  }

  // Auth pages bypass the shell layout entirely
  const isAuthPage = currentPath === "/login" || currentPath === "/register"
  if (isAuthPage) {
    return <Outlet />
  }

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

          {/* Project Switcher */}
          <div className="flex flex-col gap-1 px-2 shrink-0">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-2">
              Select Project
            </span>
            <ProjectSwitcher projectId={projectId ? Number(projectId) : undefined} />
          </div>

          {/* Nav links if a project is selected */}
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
              {projectRole.isAdmin && (
                <Link
                  to="/projects/$projectId/members"
                  params={{ projectId }}
                  activeProps={{ className: "bg-blue-600/20 text-blue-400 font-semibold" }}
                  inactiveProps={{ className: "text-slate-400 hover:bg-slate-800 hover:text-slate-100" }}
                  className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm shrink-0"
                >
                  <Users className="h-4 w-4" />
                  <span>Members & Access</span>
                </Link>
              )}
            </div>
          )}
        </div>

        {/* About link */}
        <div className="px-2 shrink-0">
          <Link
            to="/about"
            activeProps={{ className: "bg-blue-600/20 text-blue-400 font-semibold" }}
            inactiveProps={{ className: "text-slate-400 hover:bg-slate-800 hover:text-slate-100" }}
            className="flex items-center gap-3 px-3 py-2 rounded-lg transition-colors text-sm"
          >
            <Info className="h-4 w-4" />
            <span>About &amp; Design</span>
          </Link>
        </div>

        {/* Bottom: account widget + AI toggle */}
        <div className="flex flex-col gap-2 pt-4 border-t border-slate-800/80 shrink-0">
          <AccountWidget projectId={projectId ? Number(projectId) : undefined} />
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
                <span
                  className={`w-8 h-4 rounded-full p-0.5 transition-colors duration-200 ${showAIPanel ? "bg-blue-500" : "bg-slate-600"}`}
                >
                  <span
                    className={`block w-3 h-3 rounded-full bg-white transition-transform duration-200 ${showAIPanel ? "translate-x-4" : "translate-x-0"}`}
                  />
                </span>
              </button>
            </div>
          )}
        </div>
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto p-6 min-w-0">
        <Outlet />
      </main>
      {projectId && showAIPanel && (
        <AIAssistantSidebar projectId={Number(projectId)} isAdmin={projectRole.isAdmin} />
      )}
    </div>
  )
}

// ── Account Widget ───────────────────────────────────────────────────────────

function AccountWidget({ projectId }: { projectId?: number }) {
  const { user, status, logout } = useAuth()
  const { role } = useProjectRole(projectId ?? 0)

  if (status === "loading") return null

  if (status === "anonymous") {
    return (
      <div className="border-t border-slate-800 pt-3">
        <Link
          to="/login"
          className="flex items-center gap-2 px-3 py-2 rounded-lg bg-blue-600/20 hover:bg-blue-600/30 text-blue-300 text-sm font-medium transition-colors"
        >
          <LogIn className="h-4 w-4" />
          Sign in
        </Link>
      </div>
    )
  }

  const displayName = user?.display_name ?? user?.email ?? "Unknown"
  const effectiveRole = role ?? "viewer"

  return (
    <div className="border-t border-slate-800 pt-3">
      <div className="flex items-center gap-2 px-2 py-1.5 rounded-lg bg-slate-800/50">
        <div
          className={`h-7 w-7 rounded-full flex items-center justify-center shrink-0 ${
            effectiveRole === "admin" ? "bg-blue-600/30" : "bg-amber-600/20"
          }`}
        >
          {effectiveRole === "admin" ? (
            <Shield className="h-3.5 w-3.5 text-blue-400" />
          ) : (
            <Eye className="h-3.5 w-3.5 text-amber-400" />
          )}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-semibold text-slate-200 truncate">{displayName}</p>
          <p
            className={`text-[10px] font-medium capitalize ${
              effectiveRole === "admin" ? "text-blue-400" : "text-amber-400"
            }`}
          >
            {effectiveRole}
          </p>
        </div>
        <button
          onClick={logout}
          title="Sign out"
          className="text-slate-500 hover:text-slate-200 transition-colors p-1 rounded"
        >
          <LogOut className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

// ── Routes ───────────────────────────────────────────────────────────────────

function HomeRoute() {
  const { user } = useAuth()
  const projects = useQuery({
    queryKey: ["projects", user?.id ?? null],
    queryFn: () => api.listProjects(),
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
  const { status } = useAuth()

  const projectQuery = useQuery({
    queryKey: ["project", Number(projectId)],
    queryFn: () => api.getProject(Number(projectId)),
    retry: false,
  })

  if (projectQuery.isLoading || status === "loading") {
    return (
      <div className="flex items-center justify-center p-12">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (projectQuery.isError) {
    const isAuthError =
      projectQuery.error instanceof Error &&
      projectQuery.error.message === "Authentication required"
    if (isAuthError) {
      return <AuthPrompt redirectTo={`/projects/${projectId}`} />
    }
    return (
      <div className="flex flex-col items-center justify-center p-12 text-center h-full">
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
          <h2 className="text-xl font-bold text-slate-800">Project Not Found</h2>
          <p className="mt-2 text-sm text-slate-500">
            The project may have been deleted, or you do not have permission to view it.
          </p>
          <Link to="/">
            <Button className="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-sm">
              Go to Homepage
            </Button>
          </Link>
        </div>
      </div>
    )
  }

  return <KanbanBoard projectId={Number(projectId)} />
}

function AuthPrompt({ redirectTo }: { redirectTo: string }) {
  return (
    <div className="flex flex-col items-center justify-center p-12 text-center h-full">
      <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 max-w-md w-full">
        <div className="mx-auto h-12 w-12 rounded-full bg-blue-50 flex items-center justify-center mb-4">
          <Shield className="h-6 w-6 text-blue-500" />
        </div>
        <h2 className="text-xl font-bold text-slate-800">Sign in required</h2>
        <p className="mt-2 text-sm text-slate-500">
          You need to be signed in and a project member to view this page.
        </p>
        <Link to="/login" search={{ redirect: redirectTo }}>
          <Button className="mt-6 bg-blue-600 hover:bg-blue-700 text-white font-semibold shadow-sm gap-2">
            <LogIn className="h-4 w-4" />
            Sign in
          </Button>
        </Link>
      </div>
    </div>
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
      toast.success("Task restored successfully")
      queryClient.invalidateQueries({ queryKey: ["archived", Number(projectId)] })
      queryClient.invalidateQueries({ queryKey: ["board", Number(projectId)] })
    },
    onError: (error) => {
      toast.error(`Failed to restore task: ${error.message}`)
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
        {archived.isLoading && (
          <div className="space-y-4">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}
        {archived.isError && (
          <p className="text-sm text-red-600">Could not load archived tasks.</p>
        )}
        {archived.data?.length === 0 && (
          <p className="text-slate-400 text-sm py-4 text-center">
            No archived tasks in this project.
          </p>
        )}

        {archived.data && archived.data.length > 0 && (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {archived.data.map((task) => (
              <div
                key={task.id}
                className="p-4 rounded-xl border border-slate-200 bg-slate-50/50 flex flex-col justify-between gap-4"
              >
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
                    {restore.isPending ? (
                      <span className="h-3.5 w-3.5 border-2 border-blue-500 border-t-transparent rounded-full animate-spin shrink-0" />
                    ) : (
                      <RotateCcw className="h-3.5 w-3.5" />
                    )}
                    {isAdmin ? (restore.isPending ? "Restoring..." : "Restore") : "View only"}
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
  const { user, status } = useAuth()
  const [displayName, setDisplayName] = useState("")

  // Redirect anon users to login, preserving the join URL as redirect target
  useEffect(() => {
    if (status === "anonymous") {
      navigate({ to: "/login", search: { redirect: `/join/${token}` } })
    }
  }, [status, token, navigate])

  const inviteStatus = useQuery({
    queryKey: ["inviteStatus", token],
    queryFn: () => api.getInvite(token),
    retry: false,
    enabled: status === "authenticated",
  })

  const acceptInvite = useMutation({
    mutationFn: () => api.acceptInvite(token, displayName.trim() || undefined),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["members", data.project_id] })
      queryClient.invalidateQueries({ queryKey: ["membership", data.project_id] })
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      navigate({ to: "/projects/$projectId", params: { projectId: String(data.project_id) } })
    },
  })

  const handleJoin = (e: React.FormEvent) => {
    e.preventDefault()
    if (acceptInvite.isPending) return
    acceptInvite.mutate()
  }

  if (status === "loading" || status === "anonymous") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-8">
          <Skeleton className="h-12 w-12 rounded-full mx-auto mb-4 bg-white/10" />
          <Skeleton className="h-6 w-3/4 mx-auto mb-2 bg-white/10" />
        </div>
      </div>
    )
  }

  if (inviteStatus.isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="w-full max-w-md bg-white/5 backdrop-blur-sm rounded-2xl border border-white/10 p-8">
          <Skeleton className="h-12 w-12 rounded-full mx-auto mb-4 bg-white/10" />
          <Skeleton className="h-6 w-3/4 mx-auto mb-2 bg-white/10" />
          <Skeleton className="h-4 w-1/2 mx-auto mb-6 bg-white/10" />
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
            This invitation link has expired or is invalid. Please ask the project administrator
            for a new invite link.
          </p>
        </div>
      </div>
    )
  }

  const invite = inviteStatus.data!

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-96 h-96 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-40 -left-40 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl" />
      </div>

      <div className="relative w-full max-w-md">
        <div className="bg-white/5 backdrop-blur-md rounded-2xl border border-white/10 shadow-2xl overflow-hidden">
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-8 py-6">
            <div className="flex items-center gap-3">
              <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center">
                <UserPlus className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-blue-200 text-xs font-semibold uppercase tracking-wider">
                  You've been invited
                </p>
                <h1 className="text-white text-lg font-bold leading-tight">
                  {invite.project_name}
                </h1>
              </div>
            </div>
            <div className="mt-3 inline-flex items-center gap-1.5 bg-white/15 rounded-full px-3 py-1">
              <span className="h-2 w-2 rounded-full bg-green-400" />
              <span className="text-white/90 text-xs font-medium capitalize">
                {invite.role} access
              </span>
            </div>
          </div>

          <form onSubmit={handleJoin} className="px-8 py-7 space-y-4">
            <p className="text-sm text-slate-400">
              Joining as{" "}
              <span className="text-slate-200 font-medium">{user?.email}</span>. You can set a
              display name that will be shown to other team members.
            </p>

            <div className="space-y-1.5">
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider">
                Display Name{" "}
                <span className="text-slate-500 normal-case font-normal">(optional)</span>
              </label>
              <Input
                type="text"
                placeholder="Jane Smith"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
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
              disabled={acceptInvite.isPending}
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

function ProjectMembersRoute() {
  const { projectId } = projectMembersRoute.useParams()
  const { status } = useAuth()

  const projectQuery = useQuery({
    queryKey: ["project", Number(projectId)],
    queryFn: () => api.getProject(Number(projectId)),
    retry: false,
  })

  const { isAdmin, isLoading: isRoleLoading } = useProjectRole(Number(projectId))

  if (projectQuery.isLoading || isRoleLoading || status === "loading") {
    return (
      <div className="flex items-center justify-center p-12">
        <Skeleton className="h-64 w-full" />
      </div>
    )
  }

  if (projectQuery.isError) {
    const isAuthError =
      projectQuery.error instanceof Error &&
      projectQuery.error.message === "Authentication required"
    if (isAuthError) {
      return <AuthPrompt redirectTo={`/projects/${projectId}/members`} />
    }
  }

  if (!isAdmin) {
    return (
      <div className="w-full max-w-md mx-auto mt-12 bg-white rounded-2xl border border-slate-200 p-8 shadow-md text-center">
        <div className="mx-auto w-12 h-12 rounded-full bg-red-100 flex items-center justify-center mb-4">
          <Shield className="h-6 w-6 text-red-600" />
        </div>
        <h2 className="text-xl font-bold text-slate-800 mb-2">Access Denied</h2>
        <p className="text-slate-500 text-sm mb-6">
          Only project administrators can access the members directory and permissions
          configuration.
        </p>
        <Link
          to="/projects/$projectId"
          params={{ projectId }}
          className="inline-flex items-center justify-center h-10 px-4 bg-slate-900 hover:bg-slate-800 text-white text-sm font-semibold rounded-xl transition-all"
        >
          Back to Kanban Board
        </Link>
      </div>
    )
  }

  return (
    <div className="w-full max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2 text-slate-800">
          <Users className="h-6 w-6 text-slate-600" />
          Members & Access Control
        </h1>
        <p className="text-sm text-slate-500">
          Manage team members, update permissions, and invite new members to this workspace.
        </p>
      </div>
      <ProjectMembers projectId={Number(projectId)} isAdmin={isAdmin} />
    </div>
  )
}

// ── App root ─────────────────────────────────────────────────────────────────

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Toaster richColors position="top-right" />
      </AuthProvider>
    </QueryClientProvider>
  )
}
