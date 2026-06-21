import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Archive, CalendarDays, Eye, UserCircle2, X, Loader2 } from "lucide-react"
import { toast } from "sonner"
import { useState } from "react"
import { api, Board, ProjectMember, Status, Task } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sheet } from "@/components/ui/sheet"
import { Textarea } from "@/components/ui/textarea"

export function TaskDrawer({
  task,
  open,
  onOpenChange,
  statuses,
  projectId,
  isAdmin,
}: {
  task: Task | null
  open: boolean
  onOpenChange: (open: boolean) => void
  statuses: Status[]
  projectId: number
  isAdmin: boolean
}) {
  if (!task) return null

  return (
    <Sheet open={open} onOpenChange={onOpenChange} title="Task details">
      <TaskEditor
        key={task.id}
        task={task}
        statuses={statuses}
        projectId={projectId}
        isAdmin={isAdmin}
        onOpenChange={onOpenChange}
      />
    </Sheet>
  )
}

function MemberAvatar({ name, size = "sm" }: { name: string; size?: "sm" | "md" }) {
  const initials = name
    .split(/\s+/)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase()

  const colors = [
    "bg-blue-500", "bg-indigo-500", "bg-purple-500", "bg-pink-500",
    "bg-rose-500", "bg-orange-500", "bg-amber-500", "bg-teal-500",
  ]
  const color = colors[name.charCodeAt(0) % colors.length]
  const sizeClass = size === "sm" ? "h-5 w-5 text-[9px]" : "h-7 w-7 text-xs"

  return (
    <span className={`inline-flex items-center justify-center rounded-full font-bold text-white shrink-0 ${color} ${sizeClass}`}>
      {initials || "?"}
    </span>
  )
}

function TaskEditor({
  task,
  statuses,
  projectId,
  isAdmin,
  onOpenChange,
}: {
  task: Task
  statuses: Status[]
  projectId: number
  isAdmin: boolean
  onOpenChange: (open: boolean) => void
}) {
  const queryClient = useQueryClient()
  const [title, setTitle] = useState(task.title)
  const [description, setDescription] = useState(task.description ?? "")
  const [priority, setPriority] = useState(task.priority)
  const [statusId, setStatusId] = useState(task.status_id)
  const [assignee, setAssignee] = useState(task.assignee ?? "")
  const [dueDate, setDueDate] = useState(
    task.due_date ? task.due_date.slice(0, 10) : ""
  )

  // Fetch project members for the assignee dropdown
  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId),
  })

  const mutation = useMutation({
    mutationFn: () =>
      api.updateTask(task.id, {
        title,
        description: description || null,
        priority,
        status_id: statusId,
        assignee: assignee || null,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
      }),
    onMutate: async () => {
      await queryClient.cancelQueries({ queryKey: ["board", task.project_id] })
      const previousBoard = queryClient.getQueryData<Board>(["board", task.project_id])

      if (previousBoard) {
        const updatedTask: Task = {
          ...task,
          title,
          description,
          priority,
          status_id: statusId,
          assignee: assignee || null,
          due_date: dueDate ? new Date(dueDate).toISOString() : null,
        }

        const updatedColumns = previousBoard.columns.map((column) => {
          const filteredTasks = column.tasks.filter((item) => item.id !== task.id)
          if (column.status.id === statusId) {
            return { ...column, tasks: [...filteredTasks, updatedTask] }
          }
          return { ...column, tasks: filteredTasks }
        })

        queryClient.setQueryData(["board", task.project_id], {
          ...previousBoard,
          columns: updatedColumns,
        })
      }
      return { previousBoard }
    },
    onError: (err: Error, _variables, context) => {
      if (context?.previousBoard) {
        queryClient.setQueryData(["board", task.project_id], context.previousBoard)
      }
      toast.error(`Failed to update task: ${err.message || "Unknown error"}`)
    },
    onSuccess: () => {
      toast.success("Task updated successfully!")
      onOpenChange(false)
    },
  })

  const archive = useMutation({
    mutationFn: () => api.archiveTask(task.id),
    onSuccess: (archivedTask) => {
      queryClient.setQueryData<Board>(["board", archivedTask.project_id], (current) => {
        if (!current) return current
        return {
          ...current,
          columns: current.columns.map((column) => ({
            ...column,
            tasks: column.tasks.filter((item) => item.id !== archivedTask.id),
          })),
        }
      })
      queryClient.invalidateQueries({ queryKey: ["archived", archivedTask.project_id] })
      toast.success("Task archived successfully.")
      onOpenChange(false)
    },
    onError: (err: Error) => {
      toast.error(`Failed to archive task: ${err.message || "Unknown error"}`)
    },
  })

  // Find the selected member object for preview
  const selectedMember: ProjectMember | undefined = members.data?.find(
    (m) => (m.display_name ?? m.email) === assignee || m.email === assignee
  )

  const isOverdue = dueDate && new Date(dueDate) < new Date()
  const isPending = mutation.isPending || archive.isPending

  return (
    <div className="space-y-5">
      {/* Task key badge */}
      <div className="flex items-center justify-between gap-3">
        <div className="inline-flex rounded-md bg-blue-50 px-2 py-1 text-xs font-semibold text-blue-700">
          {task.key ?? `#${task.id}`}
        </div>
        {!isAdmin && (
          <div className="inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-xs font-semibold text-amber-700">
            <Eye className="h-3.5 w-3.5" />
            View only
          </div>
        )}
      </div>

      {/* Title */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Title</label>
        <Input
          className="mt-1"
          value={title}
          readOnly={!isAdmin || isPending}
          onChange={(e) => setTitle(e.target.value)}
        />
      </div>

      {/* Description */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Description</label>
        <Textarea
          className="mt-1 min-h-[80px]"
          value={description}
          readOnly={!isAdmin || isPending}
          onChange={(e) => setDescription(e.target.value)}
          placeholder="Add a description..."
        />
      </div>

      {/* Status + Priority row */}
      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Status</label>
          <select
            className="mt-1 h-10 w-full rounded-md border border-border bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
            value={statusId}
            disabled={!isAdmin || isPending}
            onChange={(e) => setStatusId(Number(e.target.value))}
          >
            {statuses.map((status) => (
              <option key={status.id} value={status.id}>
                {status.name}
              </option>
            ))}
          </select>
        </div>
        <div>
          <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Priority</label>
          <select
            className="mt-1 h-10 w-full rounded-md border border-border bg-white px-3 text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60"
            value={priority}
            disabled={!isAdmin || isPending}
            onChange={(e) => setPriority(e.target.value)}
          >
            <option value="low">Low</option>
            <option value="medium">Medium</option>
            <option value="high">High</option>
            <option value="critical">Critical</option>
          </select>
        </div>
      </div>

      {/* Assignee */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Assignee</label>
        <div className="mt-1 relative">
          {/* Preview avatar */}
          {assignee && selectedMember && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 flex items-center gap-1.5 pointer-events-none z-10">
              <MemberAvatar name={selectedMember.display_name ?? selectedMember.email} />
            </div>
          )}
          {assignee && !selectedMember && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none z-10">
              <UserCircle2 className="h-5 w-5 text-slate-400" />
            </div>
          )}
          <select
            className={`h-10 w-full rounded-md border border-border bg-white text-sm outline-none focus:ring-2 focus:ring-primary/30 disabled:opacity-60 ${
              assignee ? "pl-9 pr-3" : "px-3"
            }`}
            value={assignee}
            onChange={(e) => setAssignee(e.target.value)}
            disabled={!isAdmin || members.isLoading || isPending}
          >
            <option value="">— Unassigned —</option>
            {members.data?.map((m) => (
              <option key={m.id} value={m.display_name ?? m.email}>
                {m.display_name ? `${m.display_name} (${m.email})` : m.email}
              </option>
            ))}
          </select>
          {isAdmin && assignee && (
            <button
              type="button"
              onClick={() => setAssignee("")}
              disabled={isPending}
              className="absolute right-8 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 p-0.5 rounded disabled:opacity-50"
              title="Clear assignee"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        {/* Member cards preview when someone is selected */}
        {selectedMember && (
          <div className="mt-2 flex items-center gap-2 rounded-lg bg-slate-50 border border-slate-200 px-3 py-2">
            <MemberAvatar name={selectedMember.display_name ?? selectedMember.email} size="md" />
            <div className="min-w-0">
              <p className="text-sm font-medium text-slate-800 truncate">
                {selectedMember.display_name ?? selectedMember.email}
              </p>
              {selectedMember.display_name && (
                <p className="text-xs text-slate-500 truncate">{selectedMember.email}</p>
              )}
              <span className="text-[10px] capitalize font-semibold text-slate-400">{selectedMember.role}</span>
            </div>
          </div>
        )}
      </div>

      {/* Due Date */}
      <div>
        <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wide flex items-center gap-1.5">
          <CalendarDays className="h-3.5 w-3.5" />
          Due Date
        </label>
        <div className="mt-1 relative">
          <Input
            type="date"
            className={`w-full ${isOverdue ? "border-red-300 text-red-600 focus:ring-red-300" : ""}`}
            value={dueDate}
            readOnly={!isAdmin || isPending}
            onChange={(e) => setDueDate(e.target.value)}
          />
          {isAdmin && dueDate && (
            <button
              type="button"
              disabled={isPending}
              onClick={() => setDueDate("")}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 disabled:opacity-50"
              title="Clear due date"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
        {isOverdue && (
          <p className="mt-1 text-xs text-red-500 font-medium">⚠ This task is overdue</p>
        )}
      </div>

      {/* Actions */}
      {isAdmin && (
        <div className="flex items-center justify-between gap-2 pt-2 border-t border-border">
          <Button disabled={isPending || !title.trim()} onClick={() => mutation.mutate()}>
            {mutation.isPending && <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />}
            Save task
          </Button>
          <Button variant="outline" disabled={isPending} onClick={() => archive.mutate()}>
            {archive.isPending ? (
              <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
            ) : (
              <Archive className="mr-1 h-4 w-4" />
            )}
            Archive
          </Button>
        </div>
      )}
    </div>
  )
}
