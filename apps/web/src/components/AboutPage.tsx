import { Link } from "@tanstack/react-router"
import {
  ArrowLeft,
  Bot,
  BrainCircuit,
  Database,
  ExternalLink,
  GitBranch,
  Layers,
  Lock,
  Microscope,
  Monitor,
  Search,
  Server,
  Shield,
  Sparkles,
  Zap,
} from "lucide-react"

/* ─────────────────────── Section Wrapper ─────────────────────── */

function Section({
  children,
  className = "",
}: {
  children: React.ReactNode
  className?: string
}) {
  return (
    <section
      className={`relative rounded-2xl border border-slate-200/80 bg-white/80 backdrop-blur-sm p-8 shadow-sm hover:shadow-md transition-shadow duration-300 ${className}`}
    >
      {children}
    </section>
  )
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 border border-blue-200/60 px-3 py-1 text-xs font-semibold text-blue-700 tracking-wide uppercase">
      {children}
    </span>
  )
}

function TechPill({
  icon,
  label,
  color = "slate",
}: {
  icon: React.ReactNode
  label: string
  color?: string
}) {
  const colors: Record<string, string> = {
    blue: "bg-blue-50 text-blue-700 border-blue-200/60",
    green: "bg-emerald-50 text-emerald-700 border-emerald-200/60",
    amber: "bg-amber-50 text-amber-700 border-amber-200/60",
    violet: "bg-violet-50 text-violet-700 border-violet-200/60",
    rose: "bg-rose-50 text-rose-700 border-rose-200/60",
    slate: "bg-slate-50 text-slate-700 border-slate-200/60",
    cyan: "bg-cyan-50 text-cyan-700 border-cyan-200/60",
  }
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${colors[color] ?? colors.slate}`}
    >
      {icon}
      {label}
    </span>
  )
}

/* ─────────────────────── Architecture Row Card ─────────────────────── */

function ArchLayer({
  icon,
  title,
  items,
  accent,
}: {
  icon: React.ReactNode
  title: string
  items: string[]
  accent: string
}) {
  const accents: Record<string, string> = {
    blue: "from-blue-500 to-blue-600",
    green: "from-emerald-500 to-emerald-600",
    amber: "from-amber-500 to-amber-600",
    violet: "from-violet-500 to-violet-600",
    rose: "from-rose-500 to-rose-600",
  }
  return (
    <div className="flex items-start gap-4 group">
      <div
        className={`shrink-0 w-10 h-10 rounded-xl bg-gradient-to-br ${accents[accent] ?? accents.blue} flex items-center justify-center text-white shadow-md group-hover:scale-110 transition-transform duration-200`}
      >
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <h4 className="font-semibold text-slate-800 text-sm">{title}</h4>
        <ul className="mt-1.5 space-y-1">
          {items.map((item) => (
            <li key={item} className="text-xs text-slate-500 leading-relaxed flex items-start gap-1.5">
              <span className="mt-1.5 w-1 h-1 rounded-full bg-slate-300 shrink-0" />
              {item}
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}

/* ─────────────────────── Methodology Card ─────────────────────── */

function MethodCard({
  number,
  title,
  description,
  icon,
  accent,
}: {
  number: string
  title: string
  description: string
  icon: React.ReactNode
  accent: string
}) {
  const accents: Record<string, string> = {
    blue: "bg-blue-500",
    green: "bg-emerald-500",
    amber: "bg-amber-500",
    violet: "bg-violet-500",
  }
  return (
    <div className="relative rounded-xl border border-slate-200/80 bg-white p-6 hover:shadow-lg hover:-translate-y-0.5 transition-all duration-300 group overflow-hidden">
      {/* Accent stripe */}
      <div className={`absolute top-0 left-0 right-0 h-1 ${accents[accent] ?? accents.blue} opacity-80 group-hover:opacity-100 transition-opacity`} />

      <div className="flex items-center gap-3 mb-3">
        <span className="text-2xl font-black text-slate-200 select-none">{number}</span>
        <div className="w-8 h-8 rounded-lg bg-slate-100 flex items-center justify-center text-slate-600 group-hover:text-blue-600 transition-colors">
          {icon}
        </div>
      </div>
      <h4 className="font-bold text-slate-800 text-sm mb-2">{title}</h4>
      <p className="text-xs text-slate-500 leading-relaxed">{description}</p>
    </div>
  )
}

/* ─────────────────────── Benchmark Row ─────────────────────── */

function BenchmarkRow({
  model,
  accuracy,
  highlight,
}: {
  model: string
  accuracy: string
  highlight?: boolean
}) {
  const pct = parseFloat(accuracy) * 100
  return (
    <tr className={highlight ? "bg-blue-50/60" : "hover:bg-slate-50/80 transition-colors"}>
      <td className="py-2.5 px-4 text-xs font-medium text-slate-700 whitespace-nowrap">
        {highlight && <span className="inline-block w-1.5 h-1.5 rounded-full bg-blue-500 mr-2" />}
        {model}
      </td>
      <td className="py-2.5 px-4 text-xs text-slate-600 font-mono">{accuracy}</td>
      <td className="py-2.5 px-4">
        <div className="h-2 w-full bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${highlight ? "bg-blue-500" : "bg-slate-300"}`}
            style={{ width: `${pct}%` }}
          />
        </div>
      </td>
    </tr>
  )
}

/* ═══════════════════════ MAIN ABOUT PAGE ═══════════════════════ */

export function AboutPage() {
  return (
    <div className="max-w-5xl mx-auto py-2 space-y-8 animate-in fade-in duration-500">
      {/* ── Back link ───────────────────────────────────────── */}
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm text-slate-500 hover:text-blue-600 transition-colors group"
      >
        <ArrowLeft className="h-4 w-4 group-hover:-translate-x-0.5 transition-transform" />
        Back to Board
      </Link>

      {/* ── Hero ───────────────────────────────────────────── */}
      <div className="relative overflow-hidden rounded-2xl bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 p-10 shadow-xl">
        {/* Decorative blobs */}
        <div className="absolute -top-20 -right-20 w-72 h-72 bg-blue-500/10 rounded-full blur-3xl" />
        <div className="absolute -bottom-24 -left-24 w-80 h-80 bg-indigo-500/10 rounded-full blur-3xl" />

        <div className="relative z-10">
          <div className="flex items-center gap-3 mb-4">
            <Sparkles className="h-8 w-8 text-blue-400" />
            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-blue-400 via-indigo-300 to-purple-400 bg-clip-text text-transparent">
              CPV Kanban AI
            </h1>
          </div>
          <p className="text-slate-400 max-w-2xl text-sm leading-relaxed">
            A multi-agent, schema-adaptive system for natural language querying over dynamic
            project-management databases. Built with a security-first architecture featuring
            read-only replicas, speculative database branching, and semantic entity grounding —
            designed for enterprise-grade reliability.
          </p>
          <div className="flex flex-wrap gap-2 mt-6">
            <TechPill icon={<Server className="h-3 w-3" />} label="FastAPI" color="green" />
            <TechPill icon={<Monitor className="h-3 w-3" />} label="React + Vite" color="blue" />
            <TechPill icon={<Database className="h-3 w-3" />} label="TiDB Cloud" color="cyan" />
            <TechPill icon={<BrainCircuit className="h-3 w-3" />} label="Groq LLM" color="violet" />
            <TechPill icon={<Shield className="h-3 w-3" />} label="RBAC + OAuth 2.1" color="amber" />
            <TechPill icon={<Layers className="h-3 w-3" />} label="Vercel Edge" color="rose" />
          </div>
        </div>
      </div>

      {/* ── System Architecture ─────────────────────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <Layers className="h-3 w-3" />
            Architecture
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-1">Multi-Layer System Design</h2>
        <p className="text-sm text-slate-500 mb-8 max-w-2xl">
          The platform is structured as a four-layer pipeline where each layer is independently
          deployable, testable, and horizontally scalable.
        </p>

        <div className="grid md:grid-cols-2 gap-6">
          <ArchLayer
            accent="blue"
            icon={<Monitor className="h-5 w-5" />}
            title="Presentation Layer"
            items={[
              "React 18 SPA with TanStack Router & TanStack Query",
              "Kanban drag-and-drop board with real-time optimistic updates",
              "AI Copilot sidebar with streaming Groq LLM responses",
              "Identity-based RBAC UI gating (admin/viewer roles)",
            ]}
          />
          <ArchLayer
            accent="green"
            icon={<Server className="h-5 w-5" />}
            title="API & Orchestration Layer"
            items={[
              "FastAPI with Pydantic validation and dependency injection",
              "Master Orchestrator routing NL queries to specialized agents",
              "Security agent with veto authority over all generated SQL",
              "Schema pruning agent reducing context tokens by ~93%",
            ]}
          />
          <ArchLayer
            accent="violet"
            icon={<BrainCircuit className="h-5 w-5" />}
            title="Intelligence Layer"
            items={[
              "Multi-agent pipeline: Planner → Executor → Validator → Synthesizer",
              "Semantic Entity Grounding (JiraAnchor) via cosine similarity",
              "Execution-driven feedback loop with auto-correction",
              "TTL-based schema caching (InProcess / Redis / Redis Cluster)",
            ]}
          />
          <ArchLayer
            accent="amber"
            icon={<Database className="h-5 w-5" />}
            title="Data & Security Layer"
            items={[
              "TiDB Cloud with read-only replica for all AI queries",
              "Speculative database branching (Copy-on-Write isolation)",
              "Parameterized queries — zero SQL injection surface",
              "PII filtering + multi-session behavioral anomaly detection",
            ]}
          />
        </div>

        {/* Visual flow diagram */}
        <div className="mt-10 rounded-xl bg-slate-50 border border-slate-200/80 p-6 overflow-x-auto">
          <p className="text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-4">Data Flow</p>
          <div className="flex items-center gap-3 min-w-[700px]">
            {[
              { label: "User NL Query", color: "bg-blue-500" },
              { label: "Security Agent", color: "bg-red-500" },
              { label: "Schema Pruner", color: "bg-amber-500" },
              { label: "SQL Generator", color: "bg-violet-500" },
              { label: "Sandbox Exec", color: "bg-emerald-500" },
              { label: "Validator", color: "bg-cyan-500" },
              { label: "Response", color: "bg-blue-500" },
            ].map((step, i, arr) => (
              <div key={step.label} className="flex items-center gap-3">
                <div className="flex flex-col items-center gap-1.5">
                  <div
                    className={`w-3 h-3 rounded-full ${step.color} shadow-sm`}
                  />
                  <span className="text-[10px] font-medium text-slate-600 whitespace-nowrap">
                    {step.label}
                  </span>
                </div>
                {i < arr.length - 1 && (
                  <div className="w-12 h-px bg-slate-300 relative">
                    <div className="absolute right-0 -top-[3px] w-0 h-0 border-l-4 border-l-slate-300 border-y-[3px] border-y-transparent" />
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Research Methodology ───────────────────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <Microscope className="h-3 w-3" />
            Methodology
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-1">Three Research Pillars</h2>
        <p className="text-sm text-slate-500 mb-8 max-w-2xl">
          The system is built on three peer-reviewed research directions, each targeting a
          critical weakness in naive NL-to-SQL approaches.
        </p>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          <MethodCard
            number="01"
            accent="blue"
            icon={<GitBranch className="h-4 w-4" />}
            title="Adaptive Schema Pruning & Speculative Branching"
            description="3-layer entity resolution with BFS foreign-key graph traversal reduces prompt tokens by 93% while maintaining 1.00 recall. TiDB Copy-on-Write branching isolates all experimental queries in ephemeral sandboxes."
          />
          <MethodCard
            number="02"
            accent="amber"
            icon={<Lock className="h-4 w-4" />}
            title="Multi-Tier Security Framework"
            description="Security agent holds absolute veto over generated SQL. OAuth 2.1 + PKCE authentication, RBAC-driven schema filtering, and PII entity detection guard every query before execution."
          />
          <MethodCard
            number="03"
            accent="violet"
            icon={<Search className="h-4 w-4" />}
            title="Semantic Entity Grounding & Execution Feedback"
            description="JiraAnchor maps ambiguous natural language entities to real catalog values via embedding cosine similarity, raising component accuracy from 16.9% to 66.2%. Execution-driven feedback loop auto-corrects syntax errors."
          />
        </div>
      </Section>

      {/* ── Problem Statement: Naive vs Agentic ────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <Zap className="h-3 w-3" />
            Problem Space
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-1">Why Naive NL-to-SQL Fails</h2>
        <p className="text-sm text-slate-500 mb-6 max-w-2xl">
          Traditional single-prompt approaches collapse under real-world conditions. Our
          multi-agent architecture addresses each failure mode with a dedicated mechanism.
        </p>

        <div className="overflow-x-auto rounded-xl border border-slate-200/80">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Failure Mode</th>
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Impact</th>
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Agent Fix</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {[
                {
                  mode: "Silent Wrong Results",
                  impact: "Revenue inflated 76% due to duplicate joins",
                  fix: "Validation agent runs on sandboxed branch & cross-checks reference queries",
                },
                {
                  mode: "Unsafe SQL Execution",
                  impact: "DELETE/UPDATE on production data",
                  fix: "Security agent blocks all non-SELECT statements with veto authority",
                },
                {
                  mode: "Access Control Violations",
                  impact: "PII leakage (emails, financials)",
                  fix: "RBAC schema filtering before query compilation",
                },
                {
                  mode: "Context Overflow",
                  impact: "DDL of 100+ tables exceeds token limit",
                  fix: "Schema pruning reduces 93% of context via graph-based entity resolution",
                },
                {
                  mode: "Ambiguity Resolution",
                  impact: "Wrong metric (quantity vs revenue)",
                  fix: "Refinement agent pauses pipeline to clarify with user",
                },
              ].map((row) => (
                <tr key={row.mode} className="hover:bg-slate-50/60 transition-colors">
                  <td className="py-3 px-4 text-xs font-semibold text-slate-700">{row.mode}</td>
                  <td className="py-3 px-4 text-xs text-slate-500">{row.impact}</td>
                  <td className="py-3 px-4 text-xs text-slate-600">{row.fix}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Section>

      {/* ── Benchmark Results ──────────────────────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <Bot className="h-3 w-3" />
            Benchmarks
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-1">LLM Accuracy on Jackal-5K</h2>
        <p className="text-sm text-slate-500 mb-6 max-w-2xl">
          Benchmark results from the Jackal-5K dataset — 5,000 NL↔JQL pairs executed against
          a live Jira instance with 200K+ tasks. Even top-tier models average only ~60% accuracy,
          validating our multi-agent approach.
        </p>

        <div className="overflow-x-auto rounded-xl border border-slate-200/80">
          <table className="w-full text-left">
            <thead>
              <tr className="bg-slate-50 border-b border-slate-200">
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Model</th>
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider">Avg Accuracy</th>
                <th className="py-3 px-4 text-[10px] font-bold text-slate-500 uppercase tracking-wider w-48" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              <BenchmarkRow model="Gemini 2.5 Pro" accuracy="0.603" highlight />
              <BenchmarkRow model="OpenAI o4-Mini" accuracy="0.595" />
              <BenchmarkRow model="GPT-4o" accuracy="0.589" />
              <BenchmarkRow model="Claude Sonnet 4" accuracy="0.587" />
              <BenchmarkRow model="GPT-5" accuracy="0.583" />
              <BenchmarkRow model="Claude Opus 4" accuracy="0.576" />
              <BenchmarkRow model="Gemini 2.5 Flash" accuracy="0.581" />
            </tbody>
          </table>
        </div>

        <div className="mt-6 rounded-xl bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200/60 p-5">
          <h4 className="font-bold text-sm text-blue-800 mb-2 flex items-center gap-2">
            <Zap className="h-4 w-4" />
            Agentic Systems on Spider 2.0
          </h4>
          <div className="grid sm:grid-cols-3 gap-4">
            {[
              { name: "ByteBrain-Agent", score: "84.1%", desc: "Multi-agent + metadata synergy" },
              { name: "PExA (Bloomberg)", score: "70.2%", desc: "Parallel probe + validation" },
              { name: "GPT-4o Baseline", score: "10.1%", desc: "Single-prompt static approach" },
            ].map((s) => (
              <div key={s.name} className="text-center">
                <p className="text-2xl font-black text-blue-700">{s.score}</p>
                <p className="text-xs font-semibold text-slate-700 mt-1">{s.name}</p>
                <p className="text-[10px] text-slate-500 mt-0.5">{s.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </Section>

      {/* ── Tech Stack ─────────────────────────────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <Layers className="h-3 w-3" />
            Tech Stack
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-6">Technologies & Infrastructure</h2>

        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {[
            {
              category: "Frontend",
              items: ["React 18", "TanStack Router", "TanStack Query", "Vite 5", "Radix UI", "Lucide Icons", "Sonner Toasts"],
              color: "blue",
            },
            {
              category: "Backend",
              items: ["FastAPI", "SQLAlchemy ORM", "Pydantic v2", "Python 3.14", "Uvicorn ASGI"],
              color: "green",
            },
            {
              category: "Database",
              items: ["TiDB Cloud (MySQL-compatible)", "Read-Only Replicas", "Copy-on-Write Branching", "SQLite (local dev)"],
              color: "cyan",
            },
            {
              category: "AI / ML",
              items: ["Groq Cloud (LLM inference)", "LangChain agents", "Embedding cosine similarity", "Schema graph pruning"],
              color: "violet",
            },
            {
              category: "Security",
              items: ["OAuth 2.1 + PKCE", "RBAC role gating", "Parameterized queries", "PII entity filtering"],
              color: "amber",
            },
            {
              category: "DevOps",
              items: ["Vercel (Edge + Serverless)", "Turborepo monorepo", "GitHub Actions CI", "Ruff + ESLint linting"],
              color: "rose",
            },
          ].map((group) => {
            const borderColors: Record<string, string> = {
              blue: "border-blue-200/60",
              green: "border-emerald-200/60",
              cyan: "border-cyan-200/60",
              violet: "border-violet-200/60",
              amber: "border-amber-200/60",
              rose: "border-rose-200/60",
            }
            const headColors: Record<string, string> = {
              blue: "text-blue-700",
              green: "text-emerald-700",
              cyan: "text-cyan-700",
              violet: "text-violet-700",
              amber: "text-amber-700",
              rose: "text-rose-700",
            }
            return (
              <div
                key={group.category}
                className={`rounded-xl border ${borderColors[group.color] ?? ""} bg-white p-5 hover:shadow-md transition-shadow duration-200`}
              >
                <h4 className={`font-bold text-sm mb-3 ${headColors[group.color] ?? ""}`}>
                  {group.category}
                </h4>
                <ul className="space-y-1.5">
                  {group.items.map((item) => (
                    <li key={item} className="text-xs text-slate-600 flex items-start gap-1.5">
                      <span className="mt-1.5 w-1 h-1 rounded-full bg-slate-300 shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
        </div>
      </Section>

      {/* ── References ─────────────────────────────────────── */}
      <Section>
        <div className="flex items-center gap-2 mb-6">
          <Badge>
            <ExternalLink className="h-3 w-3" />
            References
          </Badge>
        </div>

        <h2 className="text-xl font-bold text-slate-800 mb-4">Key Academic References</h2>

        <div className="grid sm:grid-cols-2 gap-3">
          {[
            {
              title: "Jackal: Execution-Based Benchmark for LLMs on Text-to-JQL",
              venue: "arXiv 2509.23579",
              url: "https://arxiv.org/html/2509.23579v1",
            },
            {
              title: "Agentic Jackal: Semantic Value Grounding for Text-to-JQL",
              venue: "arXiv 2604.09470",
              url: "https://arxiv.org/html/2604.09470v1",
            },
            {
              title: "Model Context Protocol (MCP) — Google Cloud",
              venue: "Google Cloud Docs",
              url: "https://cloud.google.com/discover/what-is-model-context-protocol",
            },
            {
              title: "Database Branching for AI Agents: TINE Solves Schema Drift",
              venue: "PingCAP Blog",
              url: "https://www.pingcap.com/blog/database-branching-ai-agents-tine/",
            },
            {
              title: "MCP Security Design Considerations — NSA",
              venue: "NSA Cybersecurity",
              url: "https://www.nsa.gov/Portals/75/documents/Cybersecurity/CSI_MCP_SECURITY.pdf",
            },
            {
              title: "PExA: Parallel Exploration Agent for Text-to-SQL",
              venue: "AI CERTs News",
              url: "https://www.aicerts.ai/news/pexa-pushes-text-to-sql-benchmarks-forward/",
            },
          ].map((ref) => (
            <a
              key={ref.url}
              href={ref.url}
              target="_blank"
              rel="noopener noreferrer"
              className="group flex items-start gap-3 rounded-lg border border-slate-200/80 p-4 hover:border-blue-300 hover:bg-blue-50/40 transition-all duration-200"
            >
              <ExternalLink className="h-4 w-4 text-slate-400 group-hover:text-blue-500 mt-0.5 shrink-0 transition-colors" />
              <div className="min-w-0">
                <p className="text-xs font-semibold text-slate-700 group-hover:text-blue-700 transition-colors leading-snug">
                  {ref.title}
                </p>
                <p className="text-[10px] text-slate-400 mt-0.5">{ref.venue}</p>
              </div>
            </a>
          ))}
        </div>
      </Section>

      {/* ── Footer ─────────────────────────────────────────── */}
      <div className="text-center text-xs text-slate-400 pb-6 space-y-1">
        <p className="font-medium">CPV Kanban AI — Adaptive Multi-Agent Query System</p>
        <p>Built with ❤️ for enterprise-grade project management intelligence</p>
      </div>
    </div>
  )
}
