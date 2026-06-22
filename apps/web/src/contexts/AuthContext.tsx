import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useRef,
  useState,
} from "react"

const TOKEN_KEY = "cpv-auth-token"

export type AuthUser = {
  id: number
  email: string
  display_name: string | null
  is_active: boolean
}

type AuthStatus = "loading" | "authenticated" | "anonymous"

type AuthContextValue = {
  user: AuthUser | null
  token: string | null
  status: AuthStatus
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string, displayName?: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  status: "loading",
  login: async () => {},
  register: async () => {},
  logout: () => {},
})

// Module-level token holder so api.ts can read it synchronously
let _token: string | null = localStorage.getItem(TOKEN_KEY)
export function getAuthToken(): string | null {
  return _token
}

let _onUnauthorized: (() => void) | null = null
export function setOnUnauthorized(fn: () => void) {
  _onUnauthorized = fn
}
export function triggerUnauthorized() {
  _onUnauthorized?.()
}

const API_BASE =
  import.meta.env.VITE_API_BASE_URL ||
  (import.meta.env.PROD ? "" : "http://127.0.0.1:8000")

async function fetchMe(token: string): Promise<AuthUser | null> {
  const r = await fetch(`${API_BASE}/api/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  })
  if (!r.ok) return null
  return r.json()
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [token, setToken] = useState<string | null>(_token)
  const [status, setStatus] = useState<AuthStatus>("loading")
  const booted = useRef(false)

  useEffect(() => {
    if (booted.current) return
    booted.current = true
    if (!_token) {
      setStatus("anonymous")
      return
    }
    fetchMe(_token).then((u) => {
      if (u) {
        setUser(u)
        setStatus("authenticated")
      } else {
        _token = null
        localStorage.removeItem(TOKEN_KEY)
        setToken(null)
        setStatus("anonymous")
      }
    })
  }, [])

  // Register a callback so api.ts can clear auth on 401
  useEffect(() => {
    setOnUnauthorized(() => {
      _token = null
      localStorage.removeItem(TOKEN_KEY)
      setToken(null)
      setUser(null)
      setStatus("anonymous")
    })
  }, [])

  const _persist = useCallback((tok: string, u: AuthUser) => {
    _token = tok
    localStorage.setItem(TOKEN_KEY, tok)
    setToken(tok)
    setUser(u)
    setStatus("authenticated")
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const r = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    })
    if (!r.ok) {
      const body = await r.json().catch(() => ({}))
      throw new Error(body.detail || "Login failed")
    }
    const data = await r.json()
    _persist(data.access_token, data.user)
  }, [_persist])

  const register = useCallback(
    async (email: string, password: string, displayName?: string) => {
      const r = await fetch(`${API_BASE}/api/auth/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password, display_name: displayName || null }),
      })
      if (!r.ok) {
        const body = await r.json().catch(() => ({}))
        throw new Error(body.detail || "Registration failed")
      }
      const data = await r.json()
      _persist(data.access_token, data.user)
    },
    [_persist]
  )

  const logout = useCallback(() => {
    _token = null
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
    setStatus("anonymous")
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, status, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  return useContext(AuthContext)
}
