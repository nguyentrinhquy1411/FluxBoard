import {
  draggable,
  dropTargetForElements,
  monitorForElements,
} from "@atlaskit/pragmatic-drag-and-drop/element/adapter"
import { attachClosestEdge, extractClosestEdge, Edge } from "@atlaskit/pragmatic-drag-and-drop-hitbox/closest-edge"
import { DropIndicator } from "@atlaskit/pragmatic-drag-and-drop-react-drop-indicator/box"
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { GripVertical, Plus, CalendarDays, User } from "lucide-react"
import { useEffect, useRef, useState } from "react"
import { TaskDrawer } from "@/components/TaskDrawer"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Skeleton } from "@/components/ui/skeleton"
import { useProjectRole } from "@/hooks/useProjectRole"
import { api, Board, Task } from "@/lib/api"

type DragTaskData = {
  type: "task"
  taskId: number
  sourceStatusId: number
}

type DropColumnData = {
  type: "column"
  statusId: number
}

export function KanbanBoard({ projectId }: { projectId: number }) {
  const { isAdmin } = useProjectRole(projectId)
  const queryClient = useQueryClient()
  const [newTitle, setNewTitle] = useState("")
  const [selectedTask, setSelectedTask] = useState<Task | null>(null)
  const [activeDragId, setActiveDragId] = useState<number | null>(null)
  const board = useQuery({ queryKey: ["board", projectId], queryFn: () => api.board(projectId) })

  const createTask = useMutation({
    mutationFn: () => api.createTask(projectId, { title: newTitle }),
    onSuccess: (createdTask) => {
      setNewTitle("")
      queryClient.setQueryData<Board>(["board", projectId], (current) => {
        if (!current) return current
        return {
          ...current,
          columns: current.columns.map((column) =>
            column.status.id === createdTask.status_id
              ? { ...column, tasks: [...column.tasks, createdTask] }
              : column,
          ),
        }
      })
    },
  })

  const moveTask = useMutation({
    mutationFn: ({
      taskId,
      statusId,
      afterTaskId,
      beforeTaskId,
    }: {
      taskId: number
      statusId: number
      afterTaskId?: number
      beforeTaskId?: number
    }) => api.moveTask(taskId, statusId, afterTaskId, beforeTaskId),
    onMutate: async ({ taskId, statusId, afterTaskId, beforeTaskId }) => {
      await queryClient.cancelQueries({ queryKey: ["board", projectId] })
      const previousBoard = queryClient.getQueryData<Board>(["board", projectId])

      if (previousBoard) {
        let movedTask: Task | undefined

        // Step 1: Remove the task from its current column
        const stripped = previousBoard.columns.map((column) => {
          const tasks = column.tasks.filter((t) => {
            if (t.id === taskId) { movedTask = { ...t, status_id: statusId }; return false }
            return true
          })
          return { ...column, tasks }
        })

        if (movedTask) {
          // Step 2: Insert at the correct position in the target column
          const optimistic = stripped.map((column) => {
            if (column.status.id !== statusId) return column
            const tasks = [...column.tasks]

            if (afterTaskId !== undefined) {
              const afterIdx = tasks.findIndex((t) => t.id === afterTaskId)
              if (afterIdx !== -1) {
                tasks.splice(afterIdx + 1, 0, movedTask!)
              } else {
                tasks.push(movedTask!)
              }
            } else if (beforeTaskId !== undefined) {
              const beforeIdx = tasks.findIndex((t) => t.id === beforeTaskId)
              if (beforeIdx !== -1) {
                tasks.splice(beforeIdx, 0, movedTask!)
              } else {
                tasks.unshift(movedTask!)
              }
            } else {
              tasks.push(movedTask!)
            }

            return { ...column, tasks }
          })

          queryClient.setQueryData(["board", projectId], {
            ...previousBoard,
            columns: optimistic,
          })
        }
      }
      return { previousBoard }
    },
    onError: (_err, _variables, context) => {
      if (context?.previousBoard) {
        queryClient.setQueryData(["board", projectId], context.previousBoard)
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["board", projectId] })
    },
  })

  useEffect(() => {
    if (!isAdmin) return
    return monitorForElements({
      onDragStart({ source }) {
        const data = source.data as Partial<DragTaskData>
        if (data.type === "task" && typeof data.taskId === "number") {
          setActiveDragId(data.taskId)
        }
      },
      onDrop({ source, location }) {
        setActiveDragId(null)
        const sourceData = source.data as Partial<DragTaskData>
        if (sourceData.type !== "task" || typeof sourceData.taskId !== "number") {
          return
        }

        const dropTargets = location.current.dropTargets
        if (dropTargets.length === 0) {
          return
        }

        const taskTarget = dropTargets.find((target) => target.data.type === "task")
        const columnTarget = dropTargets.find((target) => target.data.type === "column")
        const targetData = (taskTarget?.data ?? columnTarget?.data) as Record<string, unknown>

        if (targetData.type === "task") {
          const targetTaskId = targetData.taskId as number
          const targetStatusId = targetData.statusId as number
          const closestEdge = extractClosestEdge(targetData)

          if (!closestEdge) return

          const columns = board.data?.columns || []
          const targetColumn = columns.find((c) => c.status.id === targetStatusId)
          if (!targetColumn) return

          // Filter out the dragged task first so indexes represent the final state
          const siblingTasks = targetColumn.tasks.filter((t) => t.id !== sourceData.taskId)
          const targetIdx = siblingTasks.findIndex((t) => t.id === targetTaskId)
          if (targetIdx === -1) return

          let afterTaskId: number | undefined
          let beforeTaskId: number | undefined

          if (closestEdge === "top") {
            beforeTaskId = targetTaskId
            afterTaskId = targetIdx > 0 ? siblingTasks[targetIdx - 1].id : undefined
          } else {
            afterTaskId = targetTaskId
            beforeTaskId = targetIdx < siblingTasks.length - 1 ? siblingTasks[targetIdx + 1].id : undefined
          }

          moveTask.mutate({
            taskId: sourceData.taskId,
            statusId: targetStatusId,
            afterTaskId,
            beforeTaskId,
          })
        } else if (targetData.type === "column") {
          const statusId = targetData.statusId as number
          if (sourceData.sourceStatusId === statusId) {
            return
          }
          moveTask.mutate({
            taskId: sourceData.taskId,
            statusId,
          })
        }
      },
    })
  }, [moveTask, board.data, isAdmin])

  if (board.isLoading) {
    return <Skeleton className="h-[calc(100vh-160px)] min-h-[450px] w-full" />
  }
  if (board.isError || !board.data) {
    const errorMsg = (board.error as Error)?.message || ""
    const isForbidden = errorMsg.includes("Forbidden") || errorMsg.includes("403")
    return (
      <Card className="p-8 max-w-lg mx-auto mt-8 border-red-500/20 bg-slate-900 text-slate-100 shadow-xl">
        <h2 className="text-lg font-bold text-red-400 mb-2">
          {isForbidden ? "Access Denied" : "Unable to load board"}
        </h2>
        <p className="text-sm text-slate-400">
          {isForbidden
            ? "You are not a member of this project. If you were invited, please accept the invitation link or switch to your invited email using the switch button in the bottom left."
            : "Unable to load board. Start the API server and retry."}
        </p>
      </Card>
    )
  }

  return (
    <div className="w-full">
      <div className="min-w-0">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold">{board.data.project.name}</h1>
            <p className="text-sm text-muted-foreground">{board.data.project.key}</p>
          </div>
          {isAdmin && (
          <div className="flex gap-2">
            <Input
              className="w-72"
              placeholder="New card title"
              value={newTitle}
              onChange={(event) => setNewTitle(event.target.value)}
            />
            <Button
              disabled={!newTitle.trim() || createTask.isPending}
              onClick={() => createTask.mutate()}
            >
              <Plus className="mr-1 h-4 w-4" /> Card
            </Button>
          </div>
          )}
        </div>
        <div className="flex h-[calc(100vh-160px)] min-h-[450px] gap-3 overflow-x-auto rounded-xl bg-blue-700/90 p-3">
          {board.data.columns.map((column) => (
            <KanbanColumn
              key={column.status.id}
              statusId={column.status.id}
              title={column.status.name}
              tasks={column.tasks}
              onSelect={setSelectedTask}
              activeDragId={activeDragId}
              isAdmin={isAdmin}
            />
          ))}
        </div>
      </div>

      <TaskDrawer
        task={selectedTask}
        open={selectedTask !== null}
        onOpenChange={(open) => !open && setSelectedTask(null)}
        statuses={board.data.columns.map((column) => column.status)}
        projectId={projectId}
        isAdmin={isAdmin}
      />
    </div>
  )
}

function KanbanColumn({
  statusId,
  title,
  tasks,
  onSelect,
  activeDragId,
  isAdmin,
}: {
  statusId: number
  title: string
  tasks: Task[]
  onSelect: (task: Task) => void
  activeDragId: number | null
  isAdmin: boolean
}) {
  const ref = useRef<HTMLDivElement | null>(null)
  const [isOver, setIsOver] = useState(false)

  useEffect(() => {
    const element = ref.current
    if (!element || !isAdmin) return
    return dropTargetForElements({
      element,
      getData: (): DropColumnData => ({ type: "column", statusId }),
      onDragEnter: () => setIsOver(true),
      onDragLeave: () => setIsOver(false),
      onDrop: () => setIsOver(false),
    })
  }, [statusId, isAdmin])

  return (
    <div
      ref={ref}
      className={`flex flex-col h-full w-72 shrink-0 rounded-xl bg-slate-100 p-3 shadow-sm ${
        activeDragId !== null && isOver ? "ring-2 ring-blue-300" : ""
      }`}
    >
      <div className="mb-3 flex items-center justify-between shrink-0">
        <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
        <Badge>{tasks.length}</Badge>
      </div>
      <div className="flex-1 space-y-2 overflow-y-auto pr-1">
        {tasks.length === 0 && (
          <div className="rounded-lg border border-dashed border-slate-300 p-3 text-sm text-slate-500">
            Drop cards here
          </div>
        )}
        {tasks.map((task) => (
          <TaskCard key={task.id} task={task} onSelect={onSelect} isAdmin={isAdmin} />
        ))}
      </div>
    </div>
  )
}

function TaskCard({
  task,
  onSelect,
  isAdmin,
}: {
  task: Task
  onSelect: (task: Task) => void
  isAdmin: boolean
}) {
  const cardRef = useRef<HTMLDivElement | null>(null)
  const handleRef = useRef<HTMLButtonElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [closestEdge, setClosestEdge] = useState<Edge | null>(null)

  useEffect(() => {
    const element = cardRef.current
    if (!element || !isAdmin) return

    const dragCleanup = draggable({
      element,
      dragHandle: handleRef.current ?? undefined,
      getInitialData: (): DragTaskData => ({
        type: "task",
        taskId: task.id,
        sourceStatusId: task.status_id,
      }),
      onDragStart: () => setIsDragging(true),
      onDrop: () => setIsDragging(false),
    })

    const dropCleanup = dropTargetForElements({
      element,
      getData: ({ input, element }) => {
        const data = {
          type: "task",
          taskId: task.id,
          statusId: task.status_id,
        }
        return attachClosestEdge(data, {
          input,
          element,
          allowedEdges: ["top", "bottom"],
        })
      },
      onDragEnter: ({ self }) => {
        setClosestEdge(extractClosestEdge(self.data))
      },
      onDrag: ({ self }) => {
        setClosestEdge(extractClosestEdge(self.data))
      },
      onDragLeave: () => {
        setClosestEdge(null)
      },
      onDrop: () => {
        setClosestEdge(null)
      },
    })

    return () => {
      dragCleanup()
      dropCleanup()
    }
  }, [task.id, task.status_id, isAdmin])

  return (
    <div ref={cardRef} className="relative">
      <Card
        className={`group cursor-pointer border-slate-200 bg-white p-3 shadow-sm transition-shadow hover:shadow-md ${
          isDragging ? "opacity-60" : ""
        }`}
        onClick={() => onSelect(task)}
      >
        <div className="mb-2 flex items-center gap-2 pl-7 text-[11px] font-semibold text-blue-700">
          {task.key ?? `#${task.id}`}
        </div>
        <div className="flex items-start gap-2">
          {isAdmin && (
            <button
              ref={handleRef}
              className="mt-0.5 rounded p-1 text-slate-400 opacity-60 hover:bg-slate-100 hover:text-slate-700 group-hover:opacity-100"
              aria-label={`Drag ${task.key ?? task.title}`}
              onClick={(event) => event.stopPropagation()}
            >
              <GripVertical className="h-4 w-4" />
            </button>
          )}
          <div className="min-w-0 flex-1 font-medium leading-snug text-slate-900">{task.title}</div>
        </div>
        <div className="mt-3 flex items-center gap-2 pl-7 flex-wrap">
          <Badge className="capitalize">{task.priority}</Badge>
          {task.assignee && (
            <span className="flex items-center gap-1 text-xs text-slate-500">
              <User className="h-3 w-3" />
              <span className="truncate max-w-[80px]">{task.assignee}</span>
            </span>
          )}
          {task.due_date && (() => {
            const due = new Date(task.due_date)
            const isOverdue = due < new Date()
            return (
              <span className={`flex items-center gap-1 text-xs font-medium ${
                isOverdue ? "text-red-500" : "text-slate-400"
              }`}>
                <CalendarDays className="h-3 w-3" />
                {due.toLocaleDateString(undefined, { month: "short", day: "numeric" })}
              </span>
            )
          })()}
          {!task.assignee && (
            <span className="text-xs text-slate-400/60 italic">Unassigned</span>
          )}
        </div>
      </Card>
      {closestEdge && <DropIndicator edge={closestEdge} gap="8px" />}
    </div>
  )
}
