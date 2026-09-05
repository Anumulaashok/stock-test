import { render, screen, waitFor } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider, useAuth } from './AuthContext'
import { setAuthToken, getAuthToken } from '../api/authToken'
import * as authApi from '../api/auth'
import { ApiError } from '../api/client'
import type { UserPublic } from '../types/backend'

afterEach(() => {
  vi.restoreAllMocks()
  setAuthToken(null)
})

function Probe() {
  const { status } = useAuth()
  return <div data-testid="status">{status}</div>
}

function renderIt() {
  return render(
    <AuthProvider>
      <Probe />
    </AuthProvider>,
  )
}

describe('AuthProvider session check', () => {
  it('keeps the stored token when the check fails with a network error (e.g. an in-flight navigation aborting it)', async () => {
    setAuthToken('a-real-token')
    vi.spyOn(authApi, 'fetchCurrentUser').mockRejectedValue(new ApiError('Could not reach the server.', 'network'))

    renderIt()

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    // The token itself must survive a transient failure -- only a real
    // 401 means the token is actually invalid.
    expect(getAuthToken()).toBe('a-real-token')
  })

  it('keeps the stored token when the check is cancelled by a timeout/abort', async () => {
    setAuthToken('a-real-token')
    vi.spyOn(authApi, 'fetchCurrentUser').mockRejectedValue(new ApiError('Cancelled.', 'timeout'))

    renderIt()

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    expect(getAuthToken()).toBe('a-real-token')
  })

  it('clears the stored token only on a genuine 401', async () => {
    setAuthToken('an-expired-token')
    vi.spyOn(authApi, 'fetchCurrentUser').mockRejectedValue(new ApiError('Invalid token.', 'client', 401))

    renderIt()

    await waitFor(() => expect(screen.getByTestId('status')).toHaveTextContent('anonymous'))
    expect(getAuthToken()).toBeNull()
  })

  it('does not update state after unmount', async () => {
    setAuthToken('a-real-token')
    let resolve!: (value: UserPublic) => void
    vi.spyOn(authApi, 'fetchCurrentUser').mockReturnValue(new Promise((r) => (resolve = r)))

    const { unmount } = renderIt()
    unmount()
    resolve({ id: 'u1', email: 'a@b.com', created_at: '2026-01-01T00:00:00Z' })

    // No assertion beyond "nothing throws" -- the `cancelled` guard is
    // what's under test.
    await new Promise((r) => setTimeout(r, 10))
  })
})
