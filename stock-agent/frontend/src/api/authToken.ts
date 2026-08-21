/**
 * Bearer-token storage. The single place `client.ts` reads a token from
 * and `AuthContext` writes one to -- keeps `localStorage` access from
 * being scattered across the app.
 */

const STORAGE_KEY = 'stock-agent.auth-token'

export function getAuthToken(): string | null {
  try {
    return localStorage.getItem(STORAGE_KEY)
  } catch {
    return null
  }
}

export function setAuthToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(STORAGE_KEY, token)
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    // localStorage unavailable (e.g. private browsing) -- the session
    // just won't persist across reloads, which is not worth failing over.
  }
}
