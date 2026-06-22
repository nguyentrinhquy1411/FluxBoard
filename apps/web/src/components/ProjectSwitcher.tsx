import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { useNavigate } from "@tanstack/react-router"
import { Plus, Loader2 } from "lucide-react"
import { useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { useAuth } from "@/contexts/AuthContext"
import { toast } from "sonner"

export function ProjectSwitcher({ projectId }: { projectId?: number }) {
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const [name, setName] = useState("")
  const { user } = useAuth()
  const projects = useQuery({
    queryKey: ["projects", user?.id ?? null],
    queryFn: () => api.listProjects(),
  })
  const createProject = useMutation({
    mutationFn: api.createProject,
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: ["projects"] })
      setName("")
      toast.success("Project created successfully!")
      navigate({ to: "/projects/$projectId", params: { projectId: String(project.id) } })
    },
    onError: (error: Error) => {
      toast.error(`Failed to create project: ${error.message || "Unknown error"}`)
    },
  })

  return (
    <div className="flex flex-col gap-2.5 w-full">
      <select
        className="w-full h-10 rounded-md border border-slate-700 bg-slate-800 text-slate-100 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
        value={projectId ?? ""}
        onChange={(event) =>
          navigate({ to: "/projects/$projectId", params: { projectId: event.target.value } })
        }
      >
        <option value="" disabled className="bg-slate-800 text-slate-400">
          Select project
        </option>
        {projects.data?.map((project) => (
          <option key={project.id} value={project.id} className="bg-slate-800 text-slate-100">
            {project.key} · {project.name}
          </option>
        ))}
      </select>

      {user && (
        <div className="flex flex-col gap-1.5 pt-2 border-t border-slate-800/60">
          <Input
            className="w-full bg-slate-800 border-slate-700 text-slate-100 placeholder:text-slate-500 focus-visible:ring-blue-500/30"
            placeholder="New project name"
            value={name}
            onChange={(event) => setName(event.target.value)}
            disabled={createProject.isPending}
          />
          <Button
            size="sm"
            className="w-full bg-blue-600 hover:bg-blue-700 text-white font-semibold"
            disabled={!name.trim() || createProject.isPending}
            onClick={() =>
              createProject.mutate({
                name,
                key: name
                  .split(/\s+/)
                  .map((word) => word[0])
                  .join("")
                  .slice(0, 6)
                  .toUpperCase(),
              })
            }
          >
            {createProject.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Plus className="mr-1 h-4 w-4" />
            )}
            Project
          </Button>
        </div>
      )}
    </div>
  )
}
