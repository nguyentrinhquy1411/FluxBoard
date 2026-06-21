import {
  AssistantRuntimeProvider,
  ComposerPrimitive,
  MessagePartPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
  useLocalRuntime,
  useMessage,
  useAui,
  type ChatModelAdapter,
  type ThreadMessage,
} from "@assistant-ui/react"
import { useQuery, useQueryClient } from "@tanstack/react-query"
import {
  ArrowUp,
  Bot,
  Loader2,
  Sparkles,
  CheckCircle2,
  Circle,
  ArrowRight,
  CornerDownRight,
  Lightbulb,
  Terminal,
} from "lucide-react"
import { useMemo, useState, useEffect } from "react"
import ReactMarkdown from "react-markdown"
import { api } from "@/lib/api"
import { useUser } from "@/contexts/UserContext"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

export function AIAssistantSidebar({
  projectId,
  isAdmin,
}: {
  projectId: number
  isAdmin: boolean
}) {
  const queryClient = useQueryClient()
  const { currentEmail } = useUser()
  const board = useQuery({ queryKey: ["board", projectId], queryFn: () => api.board(projectId) })
  const suggestionsQuery = useQuery({
    queryKey: ["aiSuggestions", projectId],
    queryFn: () => api.aiSuggestions(projectId),
    staleTime: Infinity,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnMount: false,
    refetchOnReconnect: false,
  })

  const projectKey = board.data?.project.key ?? "TASK"
  const quickActions = (suggestionsQuery.data?.suggestions ?? []).filter(
    (action) => isAdmin || !isMutationPrompt(action.prompt),
  )

  const adapter = useMemo<ChatModelAdapter>(
    () => ({
      async run({ messages, abortSignal }) {
        const prompt = latestUserText(messages)
        if (!prompt.trim()) {
          return { content: [{ type: "text", text: "Ask a Kanban question to get started." }] }
        }
        if (!isAdmin && isMutationPrompt(prompt)) {
          return {
            content: [
              {
                type: "text",
                text:
                  "Viewers can ask read-only questions, but creating, moving, " +
                  "archiving, or restoring tasks is admin-only.",
              },
            ],
          }
        }

        const response = await api.aiQuery(projectId, prompt, currentEmail, abortSignal)
        queryClient.invalidateQueries({ queryKey: ["board", projectId] })
        queryClient.invalidateQueries({ queryKey: ["archived", projectId] })

        return {
          content: [
            {
              type: "text",
              text: formatAssistantResponse(response.answer, response.action, response.used_model),
            },
          ],
          metadata: {
            custom: {
              presentation: response.presentation,
              sql: response.sql,
              used_model: response.used_model,
              action: response.action,
            },
          },
        }
      },
    }),
    [currentEmail, isAdmin, projectId, queryClient],
  )

  const runtime = useLocalRuntime(adapter, {
    initialMessages: [
      {
        role: "assistant",
        content: [
          {
            type: "text",
            text: isAdmin
              ? "I can summarize the board, inspect tasks, create cards, move work, and archive/restore tasks."
              : "I can answer read-only questions about this board.",
          },
        ],
      },
    ],
  })

  if (board.isLoading) {
    return (
      <aside className="flex h-full w-[360px] shrink-0 flex-col border-l border-slate-200 bg-white p-4">
        <Skeleton className="h-12 w-full" />
        <Skeleton className="mt-4 h-96 w-full" />
      </aside>
    )
  }

  return (
    <aside className="flex h-screen w-[380px] shrink-0 flex-col border-l border-slate-200 bg-white shadow-xl">
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50">
            <Sparkles className="h-4 w-4 text-blue-600" />
          </div>
          <div className="min-w-0">
            <h2 className="text-sm font-semibold text-slate-900">AI Kanban Copilot</h2>
            <p className="truncate text-xs text-slate-500">
              {board.data?.project.name ?? "Project"} · {isAdmin ? "admin" : "read-only"}
            </p>
          </div>
        </div>
        <div className="mt-3 rounded-lg border border-slate-100 bg-slate-50 px-3 py-2 text-xs text-slate-600">
          Asking as <span className="font-semibold text-slate-800">{currentEmail}</span>
        </div>
      </div>

      <AssistantRuntimeProvider runtime={runtime}>
        <AssistantThread
          isAdmin={isAdmin}
          projectKey={projectKey}
          quickActions={quickActions}
          suggestionsLoading={suggestionsQuery.isLoading}
        />
      </AssistantRuntimeProvider>
    </aside>
  )
}

function AssistantThread({
  isAdmin,
  projectKey,
  quickActions,
  suggestionsLoading,
}: {
  isAdmin: boolean
  projectKey: string
  quickActions: Array<{ label: string; prompt: string }>
  suggestionsLoading: boolean
}) {
  return (
    <ThreadPrimitive.Root className="flex min-h-0 flex-1 flex-col">
      <ThreadPrimitive.Viewport className="flex min-h-0 flex-1 flex-col overflow-y-auto px-4 py-4">
        <ThreadPrimitive.Messages>
          {() => <AssistantMessage />}
        </ThreadPrimitive.Messages>

        <ThreadPrimitive.Empty>
          <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-slate-200 bg-slate-50 p-6 text-center">
            <Bot className="mb-3 h-8 w-8 text-blue-500" />
            <p className="text-sm font-semibold text-slate-800">Ask about your Kanban board</p>
            <p className="mt-1 text-xs text-slate-500">
              Try task lookup, status summaries, blocked work, or overdue tasks.
            </p>
          </div>
        </ThreadPrimitive.Empty>

        <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto bg-white pt-3">
          <QuickActions actions={quickActions} loading={suggestionsLoading} />
          <ComposerPrimitive.Root className="rounded-xl border border-slate-200 bg-white shadow-sm focus-within:border-blue-300 focus-within:ring-2 focus-within:ring-blue-100">
            <ComposerPrimitive.Input
              rows={2}
              placeholder={
                isAdmin
                  ? `Ask, create, move, or archive. Example: show ${projectKey}-3`
                  : `Ask read-only questions. Example: summarize ${projectKey}`
              }
              className="max-h-36 min-h-20 w-full resize-none bg-transparent px-3 py-3 text-sm text-slate-800 outline-none placeholder:text-slate-400"
            />
            <div className="flex items-center justify-between border-t border-slate-100 px-2 py-2">
              <span className="px-1 text-[10px] text-slate-400">Enter to send</span>
              <ComposerPrimitive.Send asChild>
                <Button size="sm" className="h-8 gap-1 rounded-lg px-3">
                  <ArrowUp className="h-3.5 w-3.5" />
                  Send
                </Button>
              </ComposerPrimitive.Send>
            </div>
          </ComposerPrimitive.Root>
        </ThreadPrimitive.ViewportFooter>
      </ThreadPrimitive.Viewport>
    </ThreadPrimitive.Root>
  )
}

interface CustomMetadata {
  presentation?: {
    title: string
    summary: string
    highlights: string[]
    next_steps: string[]
  }
  sql?: string
  used_model?: string
  action?: string
}

function AssistantMessage() {
  const role = useMessage((message) => message.role)
  const isUser = role === "user"
  const statusType = useMessage((message) => message.status?.type)
  const metadata = useMessage((message) => (message as { metadata?: { custom?: CustomMetadata } }).metadata?.custom)

  if (role === "assistant") {
    if (statusType === "running") {
      return (
        <MessagePrimitive.Root className="mb-3 flex justify-start">
          <div className="w-[92%]">
            <AgentThinkingProgress />
          </div>
        </MessagePrimitive.Root>
      )
    }

    if (metadata?.presentation) {
      return (
        <MessagePrimitive.Root className="mb-3 flex justify-start">
          <div className="w-[92%] rounded-2xl rounded-bl-sm bg-white p-4 text-slate-700 shadow-md">
            <PresentationMessage
              presentation={metadata.presentation}
              sql={metadata.sql}
              usedModel={metadata.used_model}
              action={metadata.action}
            />
          </div>
        </MessagePrimitive.Root>
      )
    }
  }

  return (
    <MessagePrimitive.Root
      className={`mb-3 flex ${isUser ? "justify-end" : "justify-start"}`}
    >
      <div
        className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm leading-relaxed ${
          isUser
            ? "rounded-br-sm bg-blue-600 text-white"
            : "rounded-bl-sm bg-slate-100 text-slate-700"
        }`}
      >
        <MessagePrimitive.Content
          components={{
            Text: MessageText,
          }}
        />
      </div>
    </MessagePrimitive.Root>
  )
}

function MessageText() {
  return (
    <MessagePartPrimitive.Text
      component={MarkdownMessageText}
      className="whitespace-pre-wrap [&_code]:rounded [&_code]:bg-slate-200 [&_code]:px-1"
    />
  )
}

function MarkdownMessageText({ children, className }: { children?: string; className?: string }) {
  return (
    <div className={className}>
      <ReactMarkdown>{children ?? ""}</ReactMarkdown>
    </div>
  )
}

function MarkdownInline({ children, className }: { children: string; className?: string }) {
  return (
    <span className={className}>
      <ReactMarkdown components={{ p: ({ children }) => <>{children}</> }}>
        {children}
      </ReactMarkdown>
    </span>
  )
}

function QuickActions({
  actions,
  loading,
}: {
  actions: Array<{ label: string; prompt: string }>
  loading: boolean
}) {
  if (loading) {
    return (
      <div className="mb-2 flex items-center gap-1.5 text-xs text-slate-400">
        <Loader2 className="h-3 w-3 animate-spin" />
        Loading suggestions
      </div>
    )
  }
  if (actions.length === 0) return null

  return (
    <div className="mb-2 flex gap-1.5 overflow-x-auto pb-1">
      {actions.slice(0, 6).map((action) => (
        <ThreadPrimitive.Suggestion
          key={`${action.label}-${action.prompt}`}
          prompt={action.prompt}
          send
          className="shrink-0 rounded-full border border-slate-200 bg-white px-3 py-1 text-xs font-medium text-slate-600 transition-colors hover:border-blue-300 hover:text-blue-700"
        >
          {action.label}
        </ThreadPrimitive.Suggestion>
      ))}
    </div>
  )
}

function latestUserText(messages: readonly ThreadMessage[]) {
  const message = [...messages].reverse().find((item) => item.role === "user")
  return (
    message?.content
      .filter((part) => part.type === "text")
      .map((part) => part.text)
      .join("")
      .trim() ?? ""
  )
}

function formatAssistantResponse(answer: string, action: string, model: string) {
  return `${answer}\n\nAction: ${action}\nModel: ${model}`
}

function isMutationPrompt(prompt: string) {
  return /\b(create|add|new|archive|archieve|restore|unarchive|move|change|set|update|delete|remove)\b/i.test(
    prompt,
  )
}

const STEPS = [
  { id: "routing", label: "Routing Agent", description: "Checking query relevance & intent" },
  { id: "pruner", label: "Schema Pruner", description: "Locating relevant database tables" },
  { id: "veto", label: "Security Guard", description: "Enforcing query access controls" },
  { id: "branch", label: "TiDB Executor", description: "Running query speculatively on branch" },
  { id: "formatter", label: "Formatter Agent", description: "Shaping final response layout" },
]

function AgentThinkingProgress() {
  const [stepIdx, setStepIdx] = useState(0)

  useEffect(() => {
    const timer = setInterval(() => {
      setStepIdx((prev) => {
        if (prev < STEPS.length - 1) {
          return prev + 1
        }
        clearInterval(timer)
        return prev
      })
    }, 450)

    return () => {
      clearInterval(timer)
    }
  }, [])

  return (
    <div className="flex flex-col gap-3 rounded-xl bg-slate-100/50 p-4 shadow-sm backdrop-blur-sm">
      <div className="flex items-center gap-2 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        <Loader2 className="h-3 w-3 animate-spin text-blue-500" />
        Agent Workflow Executing
      </div>
      <div className="space-y-2">
        {STEPS.map((step, idx) => {
          const isDone = idx < stepIdx
          const isActive = idx === stepIdx
          const isPending = idx > stepIdx

          return (
            <div
              key={step.id}
              className={`flex items-start gap-2.5 transition-opacity duration-300 ${
                isPending ? "opacity-40" : "opacity-100"
              }`}
            >
              <div className="mt-0.5 shrink-0">
                {isDone ? (
                  <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500 shrink-0" />
                ) : isActive ? (
                  <div className="relative flex h-3.5 w-3.5 items-center justify-center">
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75"></span>
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-500"></span>
                  </div>
                ) : (
                  <Circle className="h-3.5 w-3.5 text-slate-300" />
                )}
              </div>
              <div className="min-w-0 flex-1">
                <div
                  className={`text-xs font-medium transition-colors duration-300 ${
                    isActive ? "text-blue-600" : isDone ? "text-slate-700" : "text-slate-400"
                  }`}
                >
                  {step.label}
                </div>
                {isActive && (
                  <div className="text-[10px] text-slate-500 leading-normal">
                    {step.description}
                  </div>
                )}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

function PresentationMessage({
  presentation,
  sql,
  usedModel,
  action,
}: {
  presentation: {
    title: string
    summary: string
    highlights: string[]
    next_steps: string[]
  }
  sql?: string
  usedModel?: string
  action?: string
}) {
  const api = useAui()
  const [showSql, setShowSql] = useState(false)

  const handleNextStepClick = (prompt: string) => {
    api.thread().append({
      role: "user",
      content: [{ type: "text", text: prompt }],
    })
  }

  return (
    <div className="flex flex-col gap-4 text-slate-800">
      {/* Header section with Action Title and Badge */}
      <div className="flex items-start justify-between gap-2 pb-2">
        <div className="font-semibold text-slate-900 flex items-center gap-1.5 text-xs">
          <Sparkles className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          {presentation.title}
        </div>
        <div className="flex flex-wrap gap-1">
          {action && (
            <Badge className="bg-slate-100 hover:bg-slate-100 text-slate-600 border-none py-0 px-1.5 text-[9px]">
              {action}
            </Badge>
          )}
        </div>
      </div>

      {/* Main summary */}
      <div className="text-xs font-medium text-slate-800 leading-relaxed whitespace-pre-wrap">
        <ReactMarkdown>{presentation.summary}</ReactMarkdown>
      </div>

      {/* Highlights */}
      {presentation.highlights && presentation.highlights.length > 0 && (
        <div className="space-y-1.5 rounded-lg bg-slate-50/80 p-2.5">
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider">
            Highlights
          </div>
          <div className="space-y-1">
            {presentation.highlights.map((h) => (
              <div key={h} className="flex items-start gap-1.5 text-xs text-slate-700">
                <span className="mt-1.5 flex h-1 w-1 shrink-0 rounded-full bg-blue-400" />
                <MarkdownInline className="leading-normal text-xs">{h}</MarkdownInline>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* SQL block if query is complex */}
      {sql && (
        <div className="space-y-1.5">
          <button
            type="button"
            onClick={() => setShowSql(!showSql)}
            className="flex items-center gap-1 text-[10px] font-medium text-slate-400 hover:text-slate-600 transition-colors"
          >
            <Terminal className="h-3 w-3" />
            {showSql ? "Hide compiled query" : "Show compiled query"}
          </button>
          {showSql && (
            <pre className="overflow-x-auto rounded-lg bg-slate-900 p-2 text-[10px] font-mono text-emerald-400 shadow-inner max-w-full whitespace-pre-wrap break-all leading-normal">
              <code>{sql}</code>
            </pre>
          )}
        </div>
      )}

      {/* Next Steps */}
      {presentation.next_steps && presentation.next_steps.length > 0 && (
        <div className="space-y-2 pt-3">
          <div className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1">
            <Lightbulb className="h-3 w-3 text-amber-500" />
            Suggested Actions
          </div>
          <div className="flex flex-col gap-1.5">
            {presentation.next_steps.map((step) => (
              <button
                key={step}
                type="button"
                onClick={() => handleNextStepClick(step)}
                className="group flex items-start gap-1.5 rounded-lg bg-slate-50 p-2 text-left text-xs text-slate-600 shadow-sm transition-all hover:bg-blue-50/20 hover:text-blue-700"
              >
                <CornerDownRight className="mt-0.5 h-3.5 w-3.5 text-slate-400 shrink-0 group-hover:text-blue-500 transition-colors" />
                <MarkdownInline className="flex-1 leading-normal text-xs">{step}</MarkdownInline>
                <ArrowRight className="h-3 w-3 opacity-0 group-hover:opacity-100 transition-opacity self-center shrink-0 text-blue-500 ml-1" />
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Footer details */}
      {usedModel && (
        <div className="text-[9px] text-slate-350 self-end">
          Processed by {usedModel}
        </div>
      )}
    </div>
  )
}
