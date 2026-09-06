/**
 * Authenticated fetch wrapper.
 *
 * Attaches the Supabase JWT access token to every API request
 * as a Bearer token in the Authorization header.
 *
 * Usage:
 *   import { apiFetch } from '../lib/api';
 *   const data = await apiFetch('/api/accounts/');
 */

import { API } from '../config';
import { supabase } from './supabase';

/**
 * Drop-in replacement for window.fetch that adds Supabase auth headers.
 *
 * Use this when migrating existing code — just replace `fetch(` with `authFetch(`.
 * The URL and options work exactly like the standard Fetch API.
 */
export async function authFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
  let { data: { session } } = await supabase.auth.getSession();

  // If session is expired or expiring within 30 seconds, refresh before sending request
  if (session?.expires_at && session.expires_at * 1000 < Date.now() + 30000) {
    const { data } = await supabase.auth.refreshSession();
    if (data.session) {
      session = data.session;
    }
  }

  const token = session?.access_token;

  const headers = new Headers(init?.headers);
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  return fetch(input, {
    ...init,
    headers,
  });
}

/**
 * Fetch wrapper that adds auth headers automatically.
 *
 * @param path - API path starting with `/` (e.g. `/api/accounts/`)
 * @param init - Standard fetch RequestInit options
 * @returns Response from the API
 */
export async function apiFetch(path: string, init?: RequestInit): Promise<Response> {
  return authFetch(`${API}${path}`, init);
}

/**
 * Convenience for JSON GET requests.
 */
export async function apiGet<T = unknown>(path: string): Promise<T> {
  const res = await apiFetch(path);
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * Convenience for JSON POST requests.
 */
export async function apiPost<T = unknown>(path: string, body?: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `API error: ${res.status}`);
  }
  return res.json();
}

/**
 * Convenience for JSON PATCH requests.
 */
export async function apiPatch<T = unknown>(path: string, body: unknown): Promise<T> {
  const res = await apiFetch(path, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => null);
    throw new Error(err?.detail || `API error: ${res.status}`);
  }
  return res.json();
}
