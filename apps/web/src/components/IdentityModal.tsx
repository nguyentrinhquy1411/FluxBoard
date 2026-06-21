import { useQuery } from "@tanstack/react-query"
import { LogIn, User, Shield, Eye } from "lucide-react"
import { useState } from "react"
import { api } from "@/lib/api"
import { useUser } from "@/contexts/UserContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"

const LOCAL_USER_EMAIL = "local-user@example.com"

export function IdentityModal({
  projectId,
  projectName,
}: {
  projectId: number
  projectName: string
}) {
  const { setIdentity } = useUser()
  const [selected, setSelected] = useState(LOCAL_USER_EMAIL)
  const [customEmail, setCustomEmail] = useState("")

  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId),
  })

  const handleContinue = () => {
    const email = customEmail.trim() || selected
    if (email) setIdentity(email)
  }

  const handleGuest = () => {
    setIdentity(customEmail.trim() || "guest@example.com")
  }

  // Find selected member info
  const selectedMember = members.data?.find((m) => m.email === selected)

  return (
    // Backdrop
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-sm">
      <div className="w-full max-w-sm bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden animate-in fade-in slide-in-from-bottom-4 duration-300">
        {/* Header */}
        <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-5">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-white/20 flex items-center justify-center">
              <LogIn className="h-4 w-4 text-white" />
            </div>
            <div>
              <p className="text-blue-200 text-[10px] font-semibold uppercase tracking-wider">
                Identify yourself
              </p>
              <h2 className="text-white font-bold text-base leading-tight">
                {projectName}
              </h2>
            </div>
          </div>
        </div>

        {/* Body */}
        <div className="p-6 space-y-4">
          <p className="text-sm text-slate-400">
            Select who you are to continue. Your role determines what you can
            edit in this project.
          </p>

          {/* Member list */}
          <div className="space-y-2 max-h-52 overflow-y-auto pr-1">
            {members.isLoading && (
              <p className="text-xs text-slate-500 text-center py-4">
                Loading members…
              </p>
            )}
            {members.data?.map((m) => {
              const label = m.display_name ?? m.email
              const isActive = selected === m.email
              return (
                <button
                  key={m.id}
                  onClick={() => setSelected(m.email)}
                  className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border transition-all text-left ${
                    isActive
                      ? "bg-blue-600/20 border-blue-500/50 text-white"
                      : "bg-slate-800/60 border-slate-700/60 text-slate-300 hover:bg-slate-800 hover:border-slate-600"
                  }`}
                >
                  {/* Avatar */}
                  <MemberInitials name={label} active={isActive} />

                  {/* Info */}
                  <div className="min-w-0 flex-1">
                    <p className="text-sm font-semibold truncate">{label}</p>
                    {m.display_name && (
                      <p className="text-[10px] text-slate-500 truncate">{m.email}</p>
                    )}
                  </div>

                  {/* Role badge */}
                  <RoleBadge role={m.role} />
                </button>
              )
            })}
          </div>

          {/* Selected role callout */}
          {selectedMember && (
            <div
              className={`flex items-center gap-2 rounded-lg px-3 py-2 text-xs font-medium ${
                selectedMember.role === "admin"
                  ? "bg-blue-500/10 text-blue-300 border border-blue-500/20"
                  : "bg-amber-500/10 text-amber-300 border border-amber-500/20"
              }`}
            >
              {selectedMember.role === "admin" ? (
                <Shield className="h-3.5 w-3.5 shrink-0" />
              ) : (
                <Eye className="h-3.5 w-3.5 shrink-0" />
              )}
              {selectedMember.role === "admin"
                ? "You have full edit access."
                : "You have view-only access. Editing is disabled."}
            </div>
          )}

          <div className="space-y-2 rounded-xl border border-slate-700/60 bg-slate-800/50 p-3">
            <label className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Or enter email manually
            </label>
            <Input
              type="email"
              value={customEmail}
              placeholder="teammate@example.com"
              onChange={(event) => setCustomEmail(event.target.value)}
              className="border-slate-700 bg-slate-900 text-slate-100 placeholder:text-slate-600"
            />
            {customEmail.trim() && (
              <p className="text-[11px] text-slate-500">
                Unknown emails open as non-members until they are invited to this project.
              </p>
            )}
          </div>

          <Button
            className="w-full h-10 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl"
            onClick={handleContinue}
            disabled={!selected}
          >
            Continue
          </Button>
          <Button
            variant="outline"
            className="w-full h-10 rounded-xl border-slate-700 bg-transparent text-slate-300 hover:bg-slate-800 hover:text-white"
            onClick={handleGuest}
          >
            Continue as Guest
          </Button>
        </div>
      </div>
    </div>
  )
}

function MemberInitials({ name, active }: { name: string; active: boolean }) {
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
  const color = active ? "bg-blue-500" : colors[name.charCodeAt(0) % colors.length]

  return (
    <span
      className={`h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 ${color}`}
    >
      {initials || <User className="h-3 w-3" />}
    </span>
  )
}

function RoleBadge({ role }: { role: string }) {
  return (
    <span
      className={`text-[9px] font-bold uppercase tracking-wider px-1.5 py-0.5 rounded-full ${
        role === "admin"
          ? "bg-blue-500/20 text-blue-300"
          : "bg-amber-500/20 text-amber-300"
      }`}
    >
      {role}
    </span>
  )
}
