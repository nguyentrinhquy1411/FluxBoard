import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { Check, Copy, Shield, Trash2, Users, UserPlus, Loader2, Mail, Link as LinkIcon } from "lucide-react"
import { useState } from "react"
import { api } from "@/lib/api"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { toast } from "sonner"
import { useAuth } from "@/contexts/AuthContext"

export function ProjectMembers({ projectId, isAdmin }: { projectId: number; isAdmin: boolean }) {
  const queryClient = useQueryClient()
  const { user } = useAuth()
  const [emailInput, setEmailInput] = useState("")
  const [roleSelect, setRoleSelect] = useState("viewer")
  const [inviteRole, setInviteRole] = useState("viewer")
  const [inviteUrl, setInviteUrl] = useState("")
  const [copied, setCopied] = useState(false)
  const [updatingEmail, setUpdatingEmail] = useState<string | null>(null)
  const [removingMemberId, setRemovingMemberId] = useState<number | null>(null)

  const members = useQuery({
    queryKey: ["members", projectId],
    queryFn: () => api.listMembers(projectId),
  })

  const createInvite = useMutation({
    mutationFn: () => api.createInvite(projectId, { role: inviteRole, expires_in_hours: 24 }),
    onSuccess: (data) => {
      const generatedUrl = `${window.location.origin}/join/${data.token}`
      setInviteUrl(generatedUrl)
      setCopied(false)
      toast.success("Invite link generated successfully!")
    },
    onError: (error: Error) => {
      toast.error(`Failed to generate invite link: ${error.message || "Unknown error"}`)
    },
  })

  const removeMember = useMutation({
    mutationFn: (memberId: number) => api.removeMember(memberId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", projectId] })
      queryClient.invalidateQueries({ queryKey: ["aiSuggestions", projectId] })
      toast.success("Team member removed successfully.")
    },
    onError: (error: Error) => {
      toast.error(`Failed to remove member: ${error.message || "Unknown error"}`)
    },
    onSettled: () => {
      setRemovingMemberId(null)
    },
  })

  const addDirectMember = useMutation({
    mutationFn: (payload: { email: string; role: string }) =>
      api.addMember(projectId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", projectId] })
      setEmailInput("")
      toast.success("Member added to workspace successfully!")
    },
    onError: (error: Error) => {
      toast.error(`Failed to add member: ${error.message || "Unknown error"}`)
    },
  })

  const changeRole = useMutation({
    mutationFn: (payload: { email: string; role: string }) =>
      api.addMember(projectId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["members", projectId] })
      toast.success("User role updated successfully.")
    },
    onError: (error: Error) => {
      toast.error(`Failed to update role: ${error.message || "Unknown error"}`)
    },
    onSettled: () => {
      setUpdatingEmail(null)
    },
  })

  const handleCopy = () => {
    if (!inviteUrl) return
    navigator.clipboard.writeText(inviteUrl)
    setCopied(true)
    toast.success("Invite link copied to clipboard!")
    setTimeout(() => setCopied(false), 2000)
  }

  const handleAddDirect = (e: React.FormEvent) => {
    e.preventDefault()
    const email = emailInput.trim()
    if (!email || addDirectMember.isPending) return
    addDirectMember.mutate({ email, role: roleSelect })
  }

  const getInitials = (name: string | null, email: string) => {
    const text = name || email
    return text.charAt(0).toUpperCase()
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
      {/* Left Column: Team Directory */}
      <div className="lg:col-span-2 bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
        <div className="px-6 py-5 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="text-base font-bold text-slate-800">Team Directory</h2>
            <p className="text-xs text-slate-500 mt-0.5">List of users who currently have access to this project.</p>
          </div>
          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold bg-blue-50 text-blue-600 border border-blue-100">
            <Users className="h-3.5 w-3.5" />
            {members.data?.length || 0} {members.data?.length === 1 ? "Member" : "Members"}
          </span>
        </div>

        <div className="divide-y divide-slate-100">
          {members.isLoading && (
            <div className="p-12 text-center text-slate-500">
              <Loader2 className="h-6 w-6 animate-spin mx-auto mb-2 text-slate-400" />
              <span>Loading team members directory...</span>
            </div>
          )}

          {members.data?.map((m) => {
            const isSelf = user?.email != null && m.email.toLowerCase() === user.email.toLowerCase()
            const isRowUpdating = updatingEmail === m.email
            const isRowRemoving = removingMemberId === m.id

            return (
              <div key={m.id} className="p-4 sm:p-5 flex items-center justify-between gap-4 hover:bg-slate-50/50 transition-colors">
                <div className="min-w-0 flex-1 flex items-center gap-3">
                  <div className={`h-10 w-10 rounded-full flex items-center justify-center font-bold text-sm shrink-0 border uppercase ${
                    m.role === "admin"
                      ? "bg-blue-50 text-blue-600 border-blue-100"
                      : "bg-slate-50 text-slate-600 border-slate-200"
                  }`}>
                    {getInitials(m.display_name ?? null, m.email)}
                  </div>
                  <div className="min-w-0 flex flex-col">
                    <span className="text-sm font-semibold text-slate-800 truncate flex items-center gap-1.5">
                      {m.display_name ?? m.email}
                      {isSelf && (
                        <span className="text-[10px] bg-slate-100 text-slate-600 border border-slate-200 rounded px-1 py-0.2 capitalize font-medium">
                          You
                        </span>
                      )}
                    </span>
                    <span className="text-xs text-slate-400 truncate leading-tight mt-0.5">
                      {m.display_name ? m.email : ""}
                    </span>
                  </div>
                </div>

                <div className="flex items-center gap-3 shrink-0">
                  {/* Role Changer or static role badge */}
                  {isAdmin && !isSelf ? (
                    <div className="relative flex items-center">
                      {isRowUpdating && (
                        <Loader2 className="absolute right-8 h-3 w-3 animate-spin text-blue-500" />
                      )}
                      <select
                        value={m.role}
                        onChange={(e) => {
                          setUpdatingEmail(m.email)
                          changeRole.mutate({ email: m.email, role: e.target.value })
                        }}
                        disabled={changeRole.isPending || removeMember.isPending}
                        className="bg-white hover:bg-slate-50 text-slate-700 text-xs rounded-lg border border-slate-200 pl-2.5 pr-8 py-1.5 outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 cursor-pointer transition-colors shadow-sm disabled:opacity-50"
                      >
                        <option value="viewer">Viewer</option>
                        <option value="admin">Admin</option>
                      </select>
                    </div>
                  ) : (
                    <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-md text-xs font-semibold border capitalize ${
                      m.role === "admin"
                        ? "bg-blue-50 text-blue-700 border-blue-100"
                        : "bg-slate-50 text-slate-600 border-slate-200"
                    }`}>
                      {m.role === "admin" && <Shield className="h-3 w-3 text-blue-600" />}
                      {m.role}
                    </span>
                  )}

                  {/* Delete member */}
                  {isAdmin && !isSelf && (
                    <Button
                      size="sm"
                      variant="ghost"
                      disabled={removeMember.isPending || changeRole.isPending}
                      onClick={() => {
                        setRemovingMemberId(m.id)
                        removeMember.mutate(m.id)
                      }}
                      className="h-8 w-8 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors shrink-0 disabled:opacity-50"
                      title="Remove member"
                    >
                      {isRowRemoving ? (
                        <Loader2 className="h-4 w-4 animate-spin text-red-500" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Right Column: Invite & Add */}
      <div className="space-y-6 lg:col-span-1">
        {/* Add Direct Member Form */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-lg bg-blue-50 flex items-center justify-center">
              <Mail className="h-4 w-4 text-blue-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Add Workspace Member</h2>
              <p className="text-[11px] text-slate-400">Directly add user by their email address.</p>
            </div>
          </div>

          {isAdmin ? (
            <form onSubmit={handleAddDirect} className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Email Address
                </label>
                <Input
                  type="email"
                  value={emailInput}
                  onChange={(e) => setEmailInput(e.target.value)}
                  placeholder="name@company.com"
                  required
                  disabled={addDirectMember.isPending}
                  className="w-full h-9 bg-slate-50/50 border-slate-200 placeholder:text-slate-400 focus:border-blue-500 focus:ring-blue-500/20 rounded-lg text-sm"
                />
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Project Role
                </label>
                <select
                  value={roleSelect}
                  onChange={(e) => setRoleSelect(e.target.value)}
                  disabled={addDirectMember.isPending}
                  className="w-full h-9 rounded-lg border border-slate-200 bg-white text-slate-700 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-sm cursor-pointer"
                >
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <Button
                type="submit"
                className="w-full h-9 bg-blue-600 hover:bg-blue-700 text-white font-semibold text-xs rounded-lg transition-all shadow-md shadow-blue-600/10"
                disabled={addDirectMember.isPending || !emailInput.trim()}
              >
                {addDirectMember.isPending ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Adding Member...
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <UserPlus className="h-3.5 w-3.5" />
                    Add Member
                  </span>
                )}
              </Button>
            </form>
          ) : (
            <div className="text-xs text-slate-500 py-3 text-center bg-slate-50 rounded-lg border border-slate-100">
              Only project administrators can directly add workspace members.
            </div>
          )}
        </div>

        {/* Shareable Link Generator */}
        <div className="bg-white rounded-xl border border-slate-200 p-6 shadow-sm">
          <div className="flex items-center gap-2 mb-4">
            <div className="h-8 w-8 rounded-lg bg-indigo-50 flex items-center justify-center">
              <LinkIcon className="h-4 w-4 text-indigo-600" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-slate-800">Generate Invite Link</h2>
              <p className="text-[11px] text-slate-400">Secure shareable invite link valid for 24h.</p>
            </div>
          </div>

          {isAdmin ? (
            <div className="space-y-4">
              <div className="space-y-1.5">
                <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                  Invite Link Role
                </label>
                <select
                  disabled={createInvite.isPending}
                  className="w-full h-9 rounded-lg border border-slate-200 bg-white text-slate-700 px-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500 shadow-sm cursor-pointer"
                  value={inviteRole}
                  onChange={(e) => {
                    setInviteRole(e.target.value)
                    setInviteUrl("") // clear old URL
                  }}
                >
                  <option value="viewer">Viewer</option>
                  <option value="admin">Admin</option>
                </select>
              </div>

              <Button
                className="w-full h-9 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-lg transition-all shadow-md shadow-indigo-600/10"
                disabled={createInvite.isPending}
                onClick={() => createInvite.mutate()}
              >
                {createInvite.isPending ? (
                  <span className="flex items-center gap-1.5">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Generating link...
                  </span>
                ) : (
                  <span>Generate Link</span>
                )}
              </Button>

              {inviteUrl && (
                <div className="mt-3 flex flex-col gap-2 p-2 rounded-lg bg-slate-50 border border-slate-100">
                  <span className="text-[10px] text-slate-500 select-all font-mono leading-normal p-2 bg-slate-900 text-slate-300 rounded-md break-all">
                    {inviteUrl}
                  </span>
                  <Button
                    size="sm"
                    variant="outline"
                    className="h-8 w-full text-xs gap-1.5 border-slate-200 hover:bg-slate-100 bg-white shadow-sm"
                    onClick={handleCopy}
                  >
                    {copied ? (
                      <>
                        <Check className="h-3.5 w-3.5 text-green-500" />
                        <span>Copied!</span>
                      </>
                    ) : (
                      <>
                        <Copy className="h-3.5 w-3.5 text-slate-500" />
                        <span>Copy Link</span>
                      </>
                    )}
                  </Button>
                </div>
              )}
            </div>
          ) : (
            <div className="text-xs text-slate-500 py-3 text-center bg-slate-50 rounded-lg border border-slate-100">
              Only project administrators can create invite links.
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
