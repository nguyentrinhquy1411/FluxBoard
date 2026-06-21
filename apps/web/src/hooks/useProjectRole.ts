import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"
import { useUser } from "@/contexts/UserContext"

const LOCAL_USER_EMAIL = "local-user@example.com"

/**
 * Returns the current user's role in the given project.
 * - "admin"  → full edit access
 * - "viewer" → read-only access
 * - null     → not a member / still loading
 */
export function useProjectRole(projectId: number): {
  role: "admin" | "viewer" | null
  isAdmin: boolean
  isViewer: boolean
  isLoading: boolean
} {
  const { currentEmail } = useUser()

  const project = useQuery({
    queryKey: ["project", projectId],
    queryFn: () => api.getProject(projectId),
    enabled: projectId > 0,
  })

  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId),
    enabled: projectId > 0,
  })

  if (project.isLoading || members.isLoading) {
    return { role: null, isAdmin: false, isViewer: false, isLoading: true }
  }

  // Everyone is admin on the SMOKE project for playground testing
  if (project.data?.key === "SMOKE") {
    return { role: "admin", isAdmin: true, isViewer: false, isLoading: false }
  }

  // local-user is always admin
  if (currentEmail === LOCAL_USER_EMAIL) {
    return { role: "admin", isAdmin: true, isViewer: false, isLoading: false }
  }

  const match = members.data?.find(
    (m) => m.email.toLowerCase() === currentEmail.toLowerCase()
  )

  const role = (match?.role ?? null) as "admin" | "viewer" | null

  return {
    role,
    isAdmin: role === "admin",
    isViewer: role === "viewer",
    isLoading: false,
  }
}
