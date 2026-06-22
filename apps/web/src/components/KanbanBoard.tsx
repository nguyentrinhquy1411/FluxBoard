import {
  draggable,
  dropTargetForElements,
  monitorForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter"
import { attachClosestEdge, extractClosestEdge, Edge } from "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge"
import { DropIndicator } from "@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/box"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { GripVertical, Plus, CalendarDays, User, Loader2, X } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { TaskDrawer } from "@/components/TaskDrawer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Skeleton } from "@/components/ui/skeleton"
import { useProjectRole } from "@/hooks/useProjectRole"
import { api, Board, Task } from "@/lib/api"
import { toast } from "sonner"

type DragTaskData = { type: "task"; taskId: number; sourceStatusId: number }
type DropColumnData = { type: "column"; statusId: number }

const PRIORITY_COLORS: Record<string, string> = {
  critical: "bg-red-500",
  high:     "bg-orange-400",
  medium:   "bg-yellow-400",
  low:      "bg-slate-300",
}

export function KanbanBoard({ projectId }: { projectId: number }) {
  const { isAdmin } = useProjectRole(projectId)
  const queryClient = useQueryClient()
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [activeDragId, setActiveDragId] = useState<number | null>(null)
  const board = useQuery({ queryKey: ["board", projectId], queryFn: () => api.board(projectId) })

  const moveTask = useMutation({
    mutationFn: ({
      taskId, statusId, afterTaskId, beforeTaskId,
    }: { taskId: number; statusId: number; afterTaskId?: number; beforeTaskId?: number }) =>
      api.moveTask(taskId, statusId, afterTaskId, beforeTaskId),
    onMutate: async ({ taskId, statusId, afterTaskId, beforeTaskId }) => {
      await queryClient.cancelQueries({ queryKey: ["board", projectId] })
      const previousBoard = queryClient.getQueryData<Board>(["board", projectId])
      if (previousBoard) {
        let movedTask: Task | undefined
        const stripped = previousBoard.columns.map((col) => {
          const tasks = col.tasks.filter((t) => {
            if (t.id === taskId) { movedTask = { ...t, status_id: statusId }; return false }
            return true
          })
          return { ...col, tasks }
        })
        if (movedTask) {
          const optimistic = stripped.map((col) => {
            if (col.status.id !== statusId) return col
            const tasks = [...col.tasks]
            if (afterTaskId !== undefined) {
              const idx = tasks.findIndex((t) => t.id === afterTaskId)
              tasks.splice(idx !== -1 ? idx + 1 : tasks.length, 0, movedTask!)
            } else if (beforeTaskId !== undefined) {
              const idx = tasks.findIndex((t) => t.id === beforeTaskId)
              tasks.splice(idx !== -1 ? idx : 0, 0, movedTask!)
            } else {
              tasks.push(movedTask!)
            }
            return { ...col, tasks }
          })
          queryClient.setQueryData(["board", projectId], { ...previousBoard, columns: optimistic })
        }
      }
      return { previousBoard }
    },
    onError: (err, _v, ctx) => {
      if (ctx?.previousBoard) queryClient.setQueryData(["board", projectId], ctx.previousBoard)
      toast.error(`Failed to move task: ${(err as Error).message}`)
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["board", projectId] }),
  })

  useEffect(() => {
    if (!isAdmin) return
    return monitorForElements({
      onDragStart({ source }) {
        const d = source.data as Partial<DragTaskData>
        if (d.type === "task" && typeof d.taskId === "number") setActiveDragId(d.taskId)
      },
      onDrop({ source, location }) {
        setActiveDragId(null)
        const sourceData = source.data as Partial<DragTaskData>
        if (sourceData.type !== "task" || typeof sourceData.taskId !== "number") return
        const dropTargets = location.current.dropTargets
        if (!dropTargets.length) return
        const taskTarget = dropTargets.find((t) => t.data.type === "task")
        const colTarget = dropTargets.find((t) => t.data.type === "column")
        const targetData = (taskTarget?.data ?? colTarget?.data) as Record<string, unknown>
        if (targetData.type === "task") {
          const targetTaskId = targetData.taskId as number
          const targetStatusId = targetData.statusId as number
          const closestEdge = extractClosestEdge(targetData)
          if (!closestEdge) return
          const targetCol = board.data?.columns.find((c) => c.status.id === targetStatusId)
          if (!targetCol) return
          const siblings = targetCol.tasks.filter((t) => t.id !== sourceData.taskId)
          const targetIdx = siblings.findIndex((t) => t.id === targetTaskId)
          if (targetIdx === -1) return
          moveTask.mutate({
            taskId: sourceData.taskId,
            statusId: targetStatusId,
            ...(closestEdge === "top"
              ? { beforeTaskId: targetTaskId, afterTaskId: targetIdx > 0 ? siblings[targetIdx - 1].id : undefined }
              : { afterTaskId: targetTaskId, beforeTaskId: targetIdx < siblings.length - 1 ? siblings[targetIdx + 1].id : undefined }),
          })
        } else if (targetData.type === "column") {
          const statusId = targetData.statusId as number
          if (sourceData.sourceStatusId !== statusId) {
            moveTask.mutate({ taskId: sourceData.taskId, statusId })
          }
        }
      },
    })
  }, [moveTask, board.data, isAdmin])

  if (board.isLoading) return <Skeleton className="h-[calc(100vh-160px)] w-full rounded-2xl" />

  if (board.isError || !board.data) {
    const msg = (board.error as Error)?.message ?? ""
    return (
      <Card className="mx-auto mt-8 max-w-md border-red-200 p-8 text-center shadow-sm">
        <h2 className="text-lg font-bold text-red-600 mb-2">
          {msg.includes("403") ? "Access Denied" : "Board unavailable"}
        </h2>
        <p className="text-sm text-slate-500">
          {msg.includes("403")
            ? "You're not a member of this project."
            : "Could not load board. Check the API server."}
        </p>
      </Card>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Board header */}
      <div className="mb-4 flex items-center justify-between">
        <div>
          <h1 className="text-xl font-bold text-slate-800">{board.data.project.name}</h1>
          <span className="text-xs font-semibold text-slate-400 tracking-widest uppercase">
            {board.data.project.key}
          </span>
        </div>
      </div>

      {/* Board */}
      <div
        className="flex flex-1 gap-3 overflow-x-auto rounded-2xl p-3"
        style={{ background: "linear-gradient(135deg, #1a6196 0%, #1d7a9c 50%, #1565a8 100%)" }}
      >
        {board.data.columns.map((col) => (
          <KanbanColumn
            key={col.status.id}
            statusId={col.status.id}
            title={col.status.name}
            tasks={col.tasks}
            onSelect={setSelectedTask}
            activeDragId={activeDragId}
            isAdmin={isAdmin}
            projectId={projectId}
          />
        ))}
      </div>

      <TaskDrawer
        task={selectedTask}
        open={selectedTask !== null}
        onOpenChange={(open) => !open && setSelectedTask(null)}
        statuses={board.data.columns.map((c) => c.status)}
        projectId={projectId}
        isAdmin={isAdmin}
      />
    </div>
  )
}

function KanbanColumn({
  statusId, title, tasks, onSelect, activeDragId, isAdmin, projectId,
}: {
  statusId: number; title: string; tasks: Task[]; onSelect: (t: Task) => void
  activeDragId: number | null; isAdmin: boolean; projectId: number
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [isOver, setIsOver] = useState(false)
  const [addingCard, setAddingCard] = useState(false)
  const [newTitle, setNewTitle] = useState("")
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const queryClient = useQueryClient()

  const createTask = useMutation({
    mutationFn: (title: string) =>
      api.createTask(projectId, { title, status_id: statusId } as Parameters<typeof api.createTask>[1] & { status_id: number }),
    onSuccess: (created) => {
      setNewTitle("")
      setAddingCard(false)
      queryClient.setQueryData<Board>(["board", projectId], (cur) => {
        if (!cur) return cur
        return {
          ...cur,
          columns: cur.columns.map((c) =>
            c.status.id === statusId ? { ...c, tasks: [...c.tasks, created] } : c
          ),
        }
      })
    },
    onError: (e: Error) => toast.error(`Failed to add card: ${e.message}`),
  })

  useEffect(() => {
    if (addingCard) textareaRef.current?.focus()
  }, [addingCard])

  useEffect(() => {
    const el = ref.current
    if (!el || !isAdmin) return
    return dropTargetForElements({
      element: el,
      getData: (): DropColumnData => ({ type: "column", statusId }),
      onDragEnter: () => setIsOver(true),
      onDragLeave: () => setIsOver(false),
      onDrop: () => setIsOver(false),
    })
  }, [statusId, isAdmin])

  const handleAddCard = () => {
    const t = newTitle.trim()
    if (!t || createTask.isPending) return
    createTask.mutate(t)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleAddCard() }
    if (e.key === "Escape") { setAddingCard(false); setNewTitle("") }
  }

  return (
    <div
      ref={ref}
      className={`flex w-[272px] shrink-0 flex-col rounded-xl transition-all ${
        activeDragId !== null && isOver ? "ring-2 ring-white/60" : ""
      }`}
      style={{ maxHeight: "calc(100vh - 220px)" }}
    >
      {/* Column header */}
      <div className="flex items-center justify-between rounded-t-xl bg-white/20 px-3 py-2.5 backdrop-blur-sm">
        <h2 className="text-sm font-bold text-white">{title}</h2>
        <span className="flex h-5 min-w-[20px] items-center justify-center rounded-full bg-white/25 px-1.5 text-[11px] font-bold text-white">
          {tasks.length}
        </span>
      </div>

      {/* Cards list */}
      <div className="flex flex-1 flex-col gap-2 overflow-y-auto rounded-b-xl bg-white/10 p-2 backdrop-blur-sm">
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onSelect={onSelect} isAdmin={isAdmin} />
        ))}

        {tasks.length === 0 && !addingCard && (
          <div className="rounded-lg border border-dashed border-white/30 p-3 text-center text-xs text-white/60">
            Drop cards here
          </div>
        )}

        {/* Inline add-card form */}
        {addingCard ? (
          <div className="rounded-xl bg-white p-2 shadow-lg">
            <textarea
              ref={textareaRef}
              className="w-full resize-none rounded-lg border border-blue-200 bg-slate-50 px-3 py-2 text-sm text-slate-800 outline-none placeholder:text-slate-400 focus:border-blue-400 focus:ring-2 focus:ring-blue-100"
              placeholder="Enter a title for this card…"
              rows={3}
              value={newTitle}
              onChange={(e) => setNewTitle(e.target.value)}
              onKeyDown={handleKeyDown}
              disabled={createTask.isPending}
            />
            <div className="mt-2 flex items-center gap-2">
              <Button
                size="sm"
                className="h-8 bg-blue-600 hover:bg-blue-500 text-white font-semibold px-3 rounded-lg"
                disabled={!newTitle.trim() || createTask.isPending}
                onClick={handleAddCard}
              >
                {createTask.isPending ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  "Add card"
                )}
              </Button>
              <button
                onClick={() => { setAddingCard(false); setNewTitle("") }}
                className="rounded-lg p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          </div>
        ) : isAdmin ? (
          <button
            onClick={() => setAddingCard(true)}
            className="flex items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-white/80 hover:bg-white/20 hover:text-white transition-colors"
          >
            <Plus className="h-4 w-4" />
            Add a card
          </button>
        ) : null}
      </div>
    </div>
  )
}

function TaskCard({ task, onSelect, isAdmin }: { task: Task; onSelect: (t: Task) => void; isAdmin: boolean }) {
  const cardRef = useRef<HTMLDivElement | null>(null)
  const handleRef = useRef<HTMLButtonElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [closestEdge, setClosestEdge] = useState<Edge | null>(null)

  useEffect(() => {
    const el = cardRef.current
    if (!el || !isAdmin) return
    const drag = draggable({
      element: el,
      dragHandle: handleRef.current ?? undefined,
      getInitialData: (): DragTaskData => ({ type: "task", taskId: task.id, sourceStatusId: task.status_id }),
      onDragStart: () => setIsDragging(true),
      onDrop: () => setIsDragging(false),
    })
    const drop = dropTargetForElements({
      element: el,
      getData: ({ input, element }) =>
        attachClosestEdge({ type: "task", taskId: task.id, statusId: task.status_id }, {
          input, element, allowedEdges: ["top", "bottom"],
        }),
      onDragEnter: ({ self }) => setClosestEdge(extractClosestEdge(self.data)),
      onDrag: ({ self }) => setClosestEdge(extractClosestEdge(self.data)),
      onDragLeave: () => setClosestEdge(null),
      onDrop: () => setClosestEdge(null),
    })
    return () => { drag(); drop() }
  }, [task.id, task.status_id, isAdmin])

  const priorityDot = PRIORITY_COLORS[task.priority] ?? "bg-slate-300"
  const isOverdue = task.due_date && new Date(task.due_date) < new Date()

  return (
    <div ref={cardRef} className="relative">
      <div
        className={`group cursor-pointer rounded-xl bg-white shadow-sm transition-shadow hover:shadow-md ${
          isDragging ? "opacity-50 rotate-1" : ""
        }`}
        onClick={() => onSelect(task)}
      >
        {/* Priority strip */}
        <div className={`h-1 rounded-t-xl ${priorityDot}`} />

        <div className="px-3 py-2.5">
          {/* Labels row */}
          <div className="mb-2 flex items-center gap-1.5 flex-wrap">
            {task.labels?.map((l) => (
              <span
                key={l.id}
                className="inline-block h-2 w-8 rounded-full"
                style={{ background: l.color || "#94a3b8" }}
                title={l.name}
              />
            ))}
          </div>

          {/* Title + drag handle */}
          <div className="flex items-start gap-1.5">
            {isAdmin && (
              <button
                ref={handleRef}
                className="mt-0.5 shrink-0 rounded p-0.5 text-slate-300 opacity-0 transition-opacity hover:bg-slate-100 hover:text-slate-500 group-hover:opacity-100"
                onClick={(e) => e.stopPropagation()}
                aria-label="Drag"
              >
                <GripVertical className="h-3.5 w-3.5" />
              </button>
            )}
            <p className="flex-1 text-sm font-medium leading-snug text-slate-800">{task.title}</p>
          </div>

          {/* Meta row */}
          <div className="mt-2.5 flex items-center justify-between gap-2">
            <span className="text-[10px] font-semibold text-slate-400">{task.key ?? `#${task.id}`}</span>
            <div className="flex items-center gap-2">
              {task.due_date && (
                <span className={`flex items-center gap-0.5 text-[11px] font-medium ${isOverdue ? "text-red-500" : "text-slate-400"}`}>
                  <CalendarDays className="h-3 w-3" />
                  {new Date(task.due_date).toLocaleDateString(undefined, { month: "short", day: "numeric" })}
                </span>
              )}
              {task.assignee && (
                <div className="flex h-5 w-5 items-center justify-center rounded-full bg-blue-500 text-[10px] font-bold text-white">
                  {task.assignee.charAt(0).toUpperCase()}
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
      {closestEdge && <DropIndicator edge={closestEdge} gap="8px" />}
    </div>
  )
}
