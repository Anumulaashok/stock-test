import { postJson, getJson } from './client'
import type { TokenResponse, UserPublic } from '../types/backend'

export async function signup(email: string, password: string): Promise<TokenResponse> {
  return postJson<TokenResponse>('/api/v1/auth/signup', { email, password })
}

export async function login(email: string, password: string): Promise<TokenResponse> {
  return postJson<TokenResponse>('/api/v1/auth/login', { email, password })
}

export async function fetchCurrentUser(): Promise<UserPublic> {
  return getJson<UserPublic>('/api/v1/auth/me')
}

export async function logout(): Promise<void> {
  await postJson<void>('/api/v1/auth/logout', undefined)
}
