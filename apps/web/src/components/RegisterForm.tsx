import { useState } from "react"
import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sparkles, UserPlus } from "lucide-react"

export function RegisterForm() {
  const { register } = useAuth()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { redirect?: string }
  const [email, setEmail] = useState("")
  const [displayName, setDisplayName] = useState("")
  const [password, setPassword] = useState("")
  const [confirm, setConfirm] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    if (password !== confirm) {
      setError("Passwords do not match")
      return
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters")
      return
    }
    setError(null)
    setLoading(true)
    try {
      await register(email.trim(), password, displayName.trim() || undefined)
      const redirect = search?.redirect
      navigate({ to: redirect && redirect.startsWith("/") ? redirect : "/" })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Registration failed")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="flex items-center gap-2 justify-center mb-8">
          <Sparkles className="h-7 w-7 text-blue-400" />
          <span className="text-2xl font-bold tracking-tight bg-gradient-to-r from-blue-400 to-indigo-300 bg-clip-text text-transparent">
            CPV Kanban AI
          </span>
        </div>

        <div className="bg-slate-900 rounded-2xl border border-slate-700 shadow-2xl overflow-hidden">
          <div className="bg-gradient-to-r from-indigo-600 to-purple-600 px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-white/20 flex items-center justify-center">
                <UserPlus className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-indigo-200 text-[10px] font-semibold uppercase tracking-wider">
                  Get started
                </p>
                <h2 className="text-white font-bold text-base">Create an account</h2>
              </div>
            </div>
          </div>

          <form onSubmit={handleSubmit} className="p-6 space-y-4">
            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Email
              </label>
              <Input
                type="email"
                placeholder="you@example.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-600"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Display name{" "}
                <span className="text-slate-600 normal-case font-normal">(optional)</span>
              </label>
              <Input
                type="text"
                placeholder="Your name"
                value={displayName}
                onChange={(e) => setDisplayName(e.target.value)}
                maxLength={160}
                className="border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-600"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Password
              </label>
              <Input
                type="password"
                placeholder="Min. 8 characters"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-600"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">
                Confirm password
              </label>
              <Input
                type="password"
                placeholder="••••••••"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                required
                className="border-slate-700 bg-slate-800 text-slate-100 placeholder:text-slate-600"
              />
            </div>

            {error && (
              <p className="text-xs text-red-400 bg-red-500/10 rounded-lg px-3 py-2">
                {error}
              </p>
            )}

            <Button
              type="submit"
              className="w-full h-10 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-xl"
              disabled={loading || !email.trim() || !password || !confirm}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Creating account…
                </span>
              ) : (
                "Create account"
              )}
            </Button>

            <p className="text-center text-xs text-slate-500">
              Already have an account?{" "}
              <Link
                to="/login"
                search={search?.redirect ? { redirect: search.redirect } : {}}
                className="text-blue-400 hover:text-blue-300 font-medium"
              >
                Sign in
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
