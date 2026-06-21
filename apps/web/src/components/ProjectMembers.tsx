import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Copy, Shield, Trash2, User, Users } from "lucide-react"
import { useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"

export function ProjectMembers({ projectId, isAdmin }: { projectId: number; isAdmin: boolean }) {
  const queryClient = useQueryClient()
  const [role, setRole] = useState("viewer")
  const [isOpen, setIsOpen] = useState(false)
  const [inviteUrl, setInviteUrl] = useState("")
  const [copied, setCopied] = useState(false)

  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId),
  })

  const createInvite = useMutation({
    mutationFn: () => api.createInvite(projectId, { role, expires_in_hours: 24 }),
    onSuccess: (data) => {
      const generatedUrl = `${window.location.origin}/join/${data.token}`
      setInviteUrl(generatedUrl)
      setCopied(false)
    },
  })

  const removeMember = useMutation({
    mutationFn: (memberId: number) => api.removeMember(memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", projectId] })
      queryClient.invalidateQueries({ queryKey: ["aiSuggestions", projectId] })
    },
  })

  const handleCopy = () => {
    if (!inviteUrl) return
    navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="flex flex-col gap-2.5 px-2">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between text-slate-400 hover:text-slate-100 transition-colors text-xs font-semibold uppercase tracking-wider py-1.5"
      >
        <span className="flex items-center gap-2">
          <Users className="h-4 w-4 text-slate-500" />
          <span>Members & Roles</span>
        </span>
        <span className="text-slate-500 hover:text-slate-300 text-sm">
          {isOpen ? "−" : "+"}
        </span>
      </button>

      {isOpen && (
        <div className="flex flex-col gap-3 pt-1 pb-2 border-t border-slate-800/40">
          {/* Member List */}
          <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
            {members.isLoading && (
              <span className="text-[11px] text-slate-500">Loading members...</span>
            )}
            {members.data?.map((m) => (
              <div key={m.id} className="flex items-center justify-between gap-2 p-1.5 rounded-lg bg-slate-800/40 border border-slate-800/80">
                <div className="min-w-0 flex-1 flex items-center gap-1.5">
                  {m.role === "admin" ? (
                    <Shield className="h-3.5 w-3.5 text-blue-400 shrink-0" />
                  ) : (
                    <User className="h-3.5 w-3.5 text-slate-400 shrink-0" />
                  )}
                  <div className="min-w-0 flex flex-col">
                    <span className="text-xs text-slate-200 truncate font-medium">
                      {m.display_name ?? m.email}
                    </span>
                    <span className="text-[9px] text-slate-500 capitalize">
                      {m.display_name ? m.email + " · " : ""}{m.role}
                    </span>
                  </div>
                </div>
                {isAdmin && m.email !== "local-user@example.com" && (
                  <button
                    disabled={removeMember.isPending}
                    onClick={() => removeMember.mutate(m.id)}
                    className="text-slate-500 hover:text-red-400 p-1 rounded transition-colors shrink-0"
                    title="Remove member"
                  >
                    <Trash2 className="h-3 w-3" />
                  </button>
                )}
              </div>
            ))}
          </div>


          {/* Invite link generation */}
          {isAdmin && (
          <div className="flex flex-col gap-2 pt-2 border-t border-slate-850">
            <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
              Generate Invite Link (24h)
            </span>
            <div className="flex gap-2">
              <select
                className="flex-1 h-8 rounded-md border border-slate-700 bg-slate-800 text-slate-200 px-2 text-xs focus:outline-none focus:ring-1 focus:ring-blue-500"
                value={role}
                onChange={(e) => {
                  setRole(e.target.value)
                  setInviteUrl("") // clear old URL
                }}
              >
                <option value="viewer">Viewer</option>
                <option value="admin">Admin</option>
              </select>
              <Button
                size="sm"
                className="h-8 px-3 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs"
                disabled={createInvite.isPending}
                onClick={() => createInvite.mutate()}
              >
                Generate
              </Button>
            </div>

            {inviteUrl && (
              <div className="mt-1 flex flex-col gap-1.5 p-2 rounded-lg bg-slate-900 border border-slate-800">
                <span className="text-[9px] text-slate-400 break-all select-all font-mono leading-normal p-1 bg-slate-950 rounded">
                  {inviteUrl}
                </span>
                <Button
                  size="sm"
                  variant="outline"
                  className="h-7 w-full text-[10px] gap-1 border-slate-700 hover:bg-slate-800 hover:text-white"
                  onClick={handleCopy}
                >
                  {copied ? (
                    <>
                      <Check className="h-3 w-3 text-green-400" />
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <Copy className="h-3 w-3 text-slate-400" />
                      <span>Copy link</span>
                    </>
                  )}
                </Button>
              </div>
            )}
          </div>
          )}
        </div>
      )}
    </div>
  )
}
