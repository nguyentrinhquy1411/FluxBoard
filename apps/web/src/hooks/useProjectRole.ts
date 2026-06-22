import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export function useProjectRole(projectId: number): {
  role: "admin" | "viewer" | null
  isAdmin: boolean
  isViewer: boolean
  isLoading: boolean
} {
  const membership = useQuery({
    queryKey: ["membership", projectId],
    queryFn: () => api.membership(projectId),
    enabled: projectId > 0,
    retry: false,
  })

  if (membership.isLoading) {
    return { role: null, isAdmin: false, isViewer: false, isLoading: true }
  }

  const role = (membership.data?.role ?? null) as "admin" | "viewer" | null

  return {
    role,
    isAdmin: role === "admin",
    isViewer: role === "viewer",
    isLoading: false,
  }
}
