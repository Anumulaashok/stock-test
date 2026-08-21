import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react'
import { fetchCurrentUser, login as loginRequest, logout as logoutRequest, signup as signupRequest } from '../api/auth'
import { getAuthToken, setAuthToken } from '../api/authToken'
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
    fetchCurrentUser()
      .then((current) => {
        setUser(current)
        setStatus('authenticated')
      })
      .catch(() => {
        // Stored token is expired/invalid -- drop it silently rather than
        // surfacing an error the user never asked to see.
        setAuthToken(null)
        setStatus('anonymous')
      })
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
