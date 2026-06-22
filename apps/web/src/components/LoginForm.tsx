import { useState } from "react"
import { Link, useNavigate, useSearch } from "@tanstack/react-router"
import { useAuth } from "@/contexts/AuthContext"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Sparkles, LogIn } from "lucide-react"

export function LoginForm() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const search = useSearch({ strict: false }) as { redirect?: string }
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (loading) return
    setError(null)
    setLoading(true)
    try {
      await login(email.trim(), password)
      const redirect = search?.redirect
      navigate({ to: redirect && redirect.startsWith("/") ? redirect : "/" })
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed")
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
          <div className="bg-gradient-to-r from-blue-600 to-indigo-600 px-6 py-5">
            <div className="flex items-center gap-3">
              <div className="h-9 w-9 rounded-xl bg-white/20 flex items-center justify-center">
                <LogIn className="h-4 w-4 text-white" />
              </div>
              <div>
                <p className="text-blue-200 text-[10px] font-semibold uppercase tracking-wider">
                  Welcome back
                </p>
                <h2 className="text-white font-bold text-base">Sign in to your account</h2>
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
                Password
              </label>
              <Input
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
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
              className="w-full h-10 bg-blue-600 hover:bg-blue-500 text-white font-semibold rounded-xl"
              disabled={loading || !email.trim() || !password}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  Signing in…
                </span>
              ) : (
                "Sign in"
              )}
            </Button>

            <p className="text-center text-xs text-slate-500">
              Don't have an account?{" "}
              <Link
                to="/register"
                search={search?.redirect ? { redirect: search.redirect } : {}}
                className="text-blue-400 hover:text-blue-300 font-medium"
              >
                Register
              </Link>
            </p>
          </form>
        </div>
      </div>
    </div>
  )
}
