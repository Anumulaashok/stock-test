import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest, signup as signupRequest } from '../api/auth'
import { getAuthToken, setAuthToken } from '../api/authToken'
import { ApiError } from '../api/client'
import type { UserPublic } from '../types/backend'

interface AuthContextValue {
  user: UserPublic | null
  status: 'checking' | 'authenticated' | 'anonymous'
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserPublic | null>(null)
  const [status, setStatus] = useState<AuthContextValue['status']>('checking')

  useEffect(() => {
    if (!getAuthToken()) {
      setStatus('anonymous')
      return
    }
    let cancelled = false
    fetchCurrentUser()
      .then((current) => {
        if (cancelled) return
        setUser(current)
        setStatus('authenticated')
      })
      .catch((error: unknown) => {
        if (cancelled) return
        // Only a genuine auth rejection (401 -- the token really is
        // expired/invalid) clears the stored token. A network/timeout
        // failure -- notably the browser aborting this exact request
        // because the page is navigating away, which happens on every
        // link click during the brief window before this check resolves
        // -- must NOT be treated the same way, or an in-flight
        // navigation silently logs the user out even though their token
        // was fine. Falls back to 'anonymous' for the UI either way
        // (never leaves the app stuck on "checking"), but a transient
        // failure leaves the token in place for the next check to
        // recover from.
        if (error instanceof ApiError && error.status === 401) {
          setAuthToken(null)
        }
        setStatus('anonymous')
      })
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const { access_token, user: loggedInUser } = await loginRequest(email, password)
    setAuthToken(access_token)
    setUser(loggedInUser)
    setStatus('authenticated')
  }, [])

  const signup = useCallback(async (email: string, password: string) => {
    const { access_token, user: newUser } = await signupRequest(email, password)
    setAuthToken(access_token)
    setUser(newUser)
    setStatus('authenticated')
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      setAuthToken(null)
      setUser(null)
      setStatus('anonymous')
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, status, login, signup, logout }}>{children}</AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used within an AuthProvider')
  return context
}
