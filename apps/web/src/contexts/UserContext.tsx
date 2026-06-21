import { createContext, useCallback, useContext, useState } from "react"

const LOCAL_USER_EMAIL = "local-user@example.com"
const STORAGE_KEY = "cpv-identity"
const SELECT_IDENTITY_KEY = "cpv-identity-select"

type UserContextValue = {
  currentEmail: string
  setIdentity: (email: string) => void
  clearIdentity: () => void
  isLocalUser: boolean
}

export const UserContext = createContext<UserContextValue>({
  currentEmail: LOCAL_USER_EMAIL,
  setIdentity: () => {},
  clearIdentity: () => {},
  isLocalUser: true,
})

export function UserProvider({ children }: { children: React.ReactNode }) {
  const [currentEmail, setCurrentEmail] = useState<string>(() => {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (stored) return stored
    if (!localStorage.getItem(SELECT_IDENTITY_KEY)) {
      localStorage.setItem(STORAGE_KEY, LOCAL_USER_EMAIL)
    }
    return LOCAL_USER_EMAIL
  })

  const setIdentity = useCallback((email: string) => {
    localStorage.setItem(STORAGE_KEY, email)
    localStorage.removeItem(SELECT_IDENTITY_KEY)
    setCurrentEmail(email)
  }, [])

  const clearIdentity = useCallback(() => {
    localStorage.removeItem(STORAGE_KEY)
    localStorage.setItem(SELECT_IDENTITY_KEY, "1")
    setCurrentEmail(LOCAL_USER_EMAIL)
  }, [])

  return (
    <UserContext.Provider
      value={{
        currentEmail,
        setIdentity,
        clearIdentity,
        isLocalUser: currentEmail === LOCAL_USER_EMAIL,
      }}
    >
      {children}
    </UserContext.Provider>
  )
}

export function useUser() {
  return useContext(UserContext)
}
