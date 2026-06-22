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
  RefreshCw,
  Activity,
  AlertTriangle,
  Info,
  Heart,
  Trash2,
  Copy,
  Check,
} from "lucide-react"
import { useMemo, useState } from "react"
import ReactMarkdown from "react-markdown"
import { api, type DigestResponse, type DigestIssue } from "@/lib/api"
import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Badge } from "@/components/ui/badge"

type SidebarTab = "chat" | "digest"

export function AIAssistantSidebar({
  projectId,
  isAdmin,
}: {
  projectId: number
  isAdmin: boolean
}) {
  const [tab, setTab] = useState<SidebarTab>("chat")
  const [clearKey, setClearKey] = useState(0)
  const { user } = useAuth()
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
      {/* Header */}
      <div className="border-b border-slate-200 px-4 py-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-blue-50">
              <Sparkles className="h-4 w-4 text-blue-600" />
            </div>
            <div className="min-w-0">
              <h2 className="text-sm font-semibold text-slate-900">AI Kanban Copilot</h2>
              <p className="truncate text-xs text-slate-500">
                {user?.display_name ?? user?.email ?? "guest"} ·{" "}
                <span className={isAdmin ? "text-blue-600" : "text-slate-400"}>
                  {isAdmin ? "admin" : "read-only"}
                </span>
              </p>
            </div>
          </div>
          {tab === "chat" && (
            <button
              onClick={() => setClearKey((k) => k + 1)}
              title="Clear conversation"
              className="rounded-lg p-2 text-slate-400 hover:bg-slate-100 hover:text-slate-600 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>

        {/* Tab switcher */}
        <div className="mt-3 flex gap-1 rounded-lg bg-slate-100 p-1">
          <button
            onClick={() => setTab("chat")}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === "chat"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Bot className="h-3.5 w-3.5" />
            Copilot
          </button>
          <button
            onClick={() => setTab("digest")}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
              tab === "digest"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            <Activity className="h-3.5 w-3.5" />
            Board Digest
          </button>
        </div>
      </div>

      {tab === "chat" ? (
        <ChatPanel
          key={clearKey}
          isAdmin={isAdmin}
          projectId={projectId}
          projectKey={projectKey}
          quickActions={quickActions}
          suggestionsLoading={suggestionsQuery.isLoading}
        />
      ) : (
        <DigestPanel projectId={projectId} />
      )}
    </aside>
  )
}

// ── Chat panel: owns the runtime so it fully resets when key changes ──────────

function ChatPanel({
  isAdmin,
  projectId,
  projectKey,
  quickActions,
  suggestionsLoading,
}: {
  isAdmin: boolean
  projectId: number
  projectKey: string
  quickActions: Array<{ label: string; prompt: string }>
  suggestionsLoading: boolean
}) {
  const queryClient = useQueryClient()

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
                text: "Viewers can ask read-only questions, but creating, moving, archiving, or restoring tasks is admin-only.",
              },
            ],
          }
        }

        const response = await api.aiQuery(projectId, prompt, abortSignal)
        queryClient.invalidateQueries({ queryKey: ["board", projectId] })
        queryClient.invalidateQueries({ queryKey: ["archived", projectId] })

        return {
          content: [{ type: "text", text: response.answer }],
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
    [isAdmin, projectId, queryClient],
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

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AssistantThread
        isAdmin={isAdmin}
        projectKey={projectKey}
        quickActions={quickActions}
        suggestionsLoading={suggestionsLoading}
      />
    </AssistantRuntimeProvider>
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
  const metadata = useMessage(
    (message) => (message as { metadata?: { custom?: CustomMetadata } }).metadata?.custom,
  )
  const rawText = useMessage((message) =>
    message.content
      .filter((p) => p.type === "text")
      .map((p) => (p as { type: "text"; text: string }).text)
      .join(""),
  )

  const [copied, setCopied] = useState(false)

  const handleCopy = () => {
    const text = metadata?.presentation
      ? [
          metadata.presentation.title,
          metadata.presentation.summary,
          ...(metadata.presentation.highlights ?? []),
        ].join("\n")
      : rawText
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    })
  }

  if (isUser) {
    return (
      <MessagePrimitive.Root className="mb-3 flex justify-end">
        <div className="max-w-[88%] rounded-2xl rounded-br-sm bg-blue-600 px-3 py-2 text-sm leading-relaxed text-white">
          <MessagePrimitive.Content components={{ Text: MessageText }} />
        </div>
      </MessagePrimitive.Root>
    )
  }

  if (statusType === "running") {
    return (
      <MessagePrimitive.Root className="mb-3 flex justify-start">
        <div className="w-[92%]">
          <AgentThinkingProgress />
        </div>
      </MessagePrimitive.Root>
    )
  }

  return (
    <MessagePrimitive.Root className="group mb-3 flex justify-start">
      <div className="relative w-[92%]">
        {metadata?.presentation ? (
          <div className="rounded-2xl rounded-bl-sm bg-white p-4 text-slate-700 shadow-md">
            <PresentationMessage
              presentation={metadata.presentation}
              sql={metadata.sql}
              usedModel={metadata.used_model}
              action={metadata.action}
            />
          </div>
        ) : (
          <div className="rounded-2xl rounded-bl-sm bg-slate-100 px-3 py-2 text-sm leading-relaxed text-slate-700">
            <MessagePrimitive.Content components={{ Text: MessageText }} />
          </div>
        )}

        {/* Copy button — appears on hover */}
        <button
          onClick={handleCopy}
          title={copied ? "Copied!" : "Copy response"}
          className="absolute -bottom-1 right-0 flex items-center gap-1 rounded-full border border-slate-200 bg-white px-2 py-0.5 text-[10px] text-slate-500 opacity-0 shadow-sm transition-opacity hover:text-blue-600 group-hover:opacity-100"
        >
          {copied ? (
            <Check className="h-3 w-3 text-emerald-500" />
          ) : (
            <Copy className="h-3 w-3" />
          )}
          {copied ? "Copied" : "Copy"}
        </button>
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

function isMutationPrompt(prompt: string) {
  return /\b(create|add|new|archive|archieve|restore|unarchive|move|change|set|update|delete|remove)\b/i.test(
    prompt,
  )
}

// ── Agent thinking progress ───────────────────────────────────────────────────

const STEPS = [
  { id: "routing", label: "Routing Agent", description: "Checking query relevance & intent" },
  { id: "pruner", label: "Schema Pruner", description: "Locating relevant database tables" },
  { id: "veto", label: "Security Guard", description: "Enforcing query access controls" },
  { id: "branch", label: "TiDB Executor", description: "Running query speculatively on branch" },
  { id: "formatter", label: "Formatter Agent", description: "Shaping final response layout" },
]

function AgentThinkingProgress() {
  const [stepIdx, setStepIdx] = useState(0)

  useState(() => {
    const timer = setInterval(() => {
      setStepIdx((prev) => {
        if (prev < STEPS.length - 1) return prev + 1
        clearInterval(timer)
        return prev
      })
    }, 450)
    return () => clearInterval(timer)
  })

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
                    <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-blue-400 opacity-75" />
                    <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-blue-500" />
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

// ── Presentation message ──────────────────────────────────────────────────────

function PresentationMessage({
  presentation,
  sql,
  usedModel,
  action,
}: {
  presentation: { title: string; summary: string; highlights: string[]; next_steps: string[] }
  sql?: string
  usedModel?: string
  action?: string
}) {
  const aui = useAui()
  const [showSql, setShowSql] = useState(false)

  const handleNextStepClick = (prompt: string) => {
    aui.thread().append({
      role: "user",
      content: [{ type: "text", text: prompt }],
    })
  }

  return (
    <div className="flex flex-col gap-4 text-slate-800">
      {/* Title + action badge */}
      <div className="flex items-start justify-between gap-2 pb-2">
        <div className="font-semibold text-slate-900 flex items-center gap-1.5 text-xs">
          <Sparkles className="h-3.5 w-3.5 text-blue-500 shrink-0" />
          {presentation.title}
        </div>
        {action && (
          <Badge className="bg-slate-100 hover:bg-slate-100 text-slate-600 border-none py-0 px-1.5 text-[9px] shrink-0">
            {action}
          </Badge>
        )}
      </div>

      {/* Summary */}
      <div className="text-xs font-medium text-slate-800 leading-relaxed whitespace-pre-wrap">
        <ReactMarkdown>{presentation.summary}</ReactMarkdown>
      </div>

      {/* Highlights */}
      {presentation.highlights?.length > 0 && (
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

      {/* SQL toggle */}
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

      {/* Suggested actions */}
      {presentation.next_steps?.length > 0 && (
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

      {usedModel && (
        <div className="text-[9px] text-slate-400 self-end">
          Processed by {usedModel}
        </div>
      )}
    </div>
  )
}

// ── Board Digest Panel ────────────────────────────────────────────────────────

function scoreColor(score: number) {
  if (score >= 8) return "text-emerald-600"
  if (score >= 5) return "text-amber-600"
  return "text-red-600"
}

function scoreBg(score: number) {
  if (score >= 8) return "bg-emerald-50 border-emerald-200"
  if (score >= 5) return "bg-amber-50 border-amber-200"
  return "bg-red-50 border-red-200"
}

function IssueBadge({ severity }: { severity: DigestIssue["severity"] }) {
  if (severity === "critical")
    return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-red-500" />
  if (severity === "warning")
    return <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-500" />
  return <Info className="h-3.5 w-3.5 shrink-0 text-blue-400" />
}

function StatPill({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex flex-col items-center rounded-lg bg-slate-50 border border-slate-100 px-3 py-2 min-w-[56px]">
      <span className="text-base font-bold text-slate-800">{value}</span>
      <span className="text-[10px] text-slate-500 capitalize">{label}</span>
    </div>
  )
}

function DigestPanel({ projectId }: { projectId: number }) {
  const [fetchedAt, setFetchedAt] = useState<number | null>(null)

  const digestQuery = useQuery({
    queryKey: ["digest", projectId, fetchedAt],
    queryFn: () => api.aiDigest(projectId),
    enabled: fetchedAt !== null,
    staleTime: Infinity,
  })

  const handleGenerate = () => setFetchedAt(Date.now())
  const stats = digestQuery.data?.stats as Record<string, number> | undefined

  return (
    <div className="flex flex-1 flex-col overflow-y-auto">
      {fetchedAt === null && (
        <div className="flex flex-1 flex-col items-center justify-center gap-4 p-6 text-center">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-blue-50">
            <Activity className="h-7 w-7 text-blue-500" />
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-800">Board Digest</p>
            <p className="mt-1 text-xs text-slate-500">
              AI-generated standup report: health score, recent activity, blockers, and recommended actions.
            </p>
          </div>
          <Button
            onClick={handleGenerate}
            className="gap-2 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl px-5"
          >
            <Sparkles className="h-4 w-4" />
            Generate Digest
          </Button>
        </div>
      )}

      {digestQuery.isLoading && (
        <div className="flex flex-1 flex-col gap-4 p-4">
          <Skeleton className="h-24 w-full rounded-xl" />
          <Skeleton className="h-16 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
          <div className="flex items-center justify-center gap-2 text-xs text-slate-500 mt-2">
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Analyzing board with AI…
          </div>
        </div>
      )}

      {digestQuery.isError && (
        <div className="m-4 rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to generate digest: {(digestQuery.error as Error).message}
        </div>
      )}

      {digestQuery.data && (
        <div className="flex flex-col gap-4 p-4">
          <div className={`rounded-xl border p-4 ${scoreBg(digestQuery.data.health_score)}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Heart className={`h-4 w-4 ${scoreColor(digestQuery.data.health_score)}`} />
                <span className="text-xs font-semibold text-slate-700 uppercase tracking-wide">
                  Board Health
                </span>
              </div>
              <span className={`text-2xl font-bold ${scoreColor(digestQuery.data.health_score)}`}>
                {digestQuery.data.health_score}
                <span className="text-sm font-normal text-slate-400">/10</span>
              </span>
            </div>
            <p className="mt-2 text-xs text-slate-700 leading-relaxed">
              {digestQuery.data.summary}
            </p>
          </div>

          {stats && (
            <div className="flex gap-2 flex-wrap">
              <StatPill label="Active" value={stats.total_active ?? 0} />
              <StatPill label="Done" value={stats.done ?? 0} />
              <StatPill label="In Progress" value={stats.in_progress ?? 0} />
              <StatPill label="Overdue" value={stats.overdue ?? 0} />
              <StatPill label="Events (24h)" value={stats.events_24h ?? 0} />
            </div>
          )}

          {digestQuery.data.issues.length > 0 && (
            <div className="rounded-xl border border-slate-200 bg-white overflow-hidden">
              <div className="px-3 py-2 bg-slate-50 border-b border-slate-100">
                <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                  Issues Detected
                </span>
              </div>
              <div className="divide-y divide-slate-100">
                {digestQuery.data.issues.map((issue, i) => (
                  <div key={i} className="flex items-start gap-2 px-3 py-2.5">
                    <IssueBadge severity={issue.severity} />
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-slate-800">{issue.title}</p>
                      <p className="text-[11px] text-slate-500 truncate">{issue.detail}</p>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {digestQuery.data.done_today.length > 0 && (
            <DigestSection
              title="Done"
              items={digestQuery.data.done_today}
              color="emerald"
              icon={<CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" />}
            />
          )}
          {digestQuery.data.in_progress.length > 0 && (
            <DigestSection
              title="In Progress"
              items={digestQuery.data.in_progress}
              color="blue"
              icon={<Circle className="h-3.5 w-3.5 text-blue-500" />}
            />
          )}
          {digestQuery.data.blockers.length > 0 && (
            <DigestSection
              title="Blockers / Risks"
              items={digestQuery.data.blockers}
              color="red"
              icon={<AlertTriangle className="h-3.5 w-3.5 text-red-500" />}
            />
          )}

          <div className="flex items-center justify-between pt-1">
            <span className="text-[10px] text-slate-400">
              Generated {new Date(digestQuery.data.generated_at).toLocaleTimeString()}
            </span>
            <button
              onClick={handleGenerate}
              className="flex items-center gap-1 text-[11px] text-slate-500 hover:text-blue-600 transition-colors"
            >
              <RefreshCw className="h-3 w-3" />
              Refresh
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function DigestSection({
  title,
  items,
  color,
  icon,
}: {
  title: string
  items: string[]
  color: "emerald" | "blue" | "red"
  icon: React.ReactNode
}) {
  const borderClass = { emerald: "border-emerald-100", blue: "border-blue-100", red: "border-red-100" }[color]
  const bgClass = { emerald: "bg-emerald-50", blue: "bg-blue-50", red: "bg-red-50" }[color]
  return (
    <div className={`rounded-xl border ${borderClass} overflow-hidden`}>
      <div className={`flex items-center gap-1.5 px-3 py-2 ${bgClass} border-b ${borderClass}`}>
        {icon}
        <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-600">
          {title}
        </span>
      </div>
      <ul className="divide-y divide-slate-100 bg-white">
        {items.map((item, i) => (
          <li key={i} className="px-3 py-2 text-xs text-slate-700 leading-relaxed">
            {item}
          </li>
        ))}
      </ul>
    </div>
  )
}
