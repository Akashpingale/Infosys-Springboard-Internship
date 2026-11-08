/**
 * The typed fetch client (KIRO_UI_UPGRADE_SPEC.md Section 11).
 *
 * The base URL comes from VITE_API_URL and nothing else. No key, token or header secret is read
 * here, so none can reach the bundle.
 *
 * Every failure becomes an ApiError carrying the backend's own `error.code` and `error.message`,
 * which are written for the user (utils/errors.py), so a screen never has to interpret a status
 * code or show a stack trace.
 */

import { MESSAGES } from '@/lib/format';

export const API_URL = (import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000').replace(/\/+$/, '');

/** The one error shape every route returns. */
export interface ApiErrorBody {
  error: { code: string; message: string };
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;

  constructor(message: string, status: number, code: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }

  /** True when the server could not be reached at all, rather than answering with an error. */
  get isOffline(): boolean {
    return this.status === 0;
  }
}

const OFFLINE = new Set(['TypeError', 'AbortError']);

function isErrorBody(value: unknown): value is ApiErrorBody {
  if (typeof value !== 'object' || value === null || !('error' in value)) {
    return false;
  }
  const { error } = value as { error: unknown };
  return (
    typeof error === 'object' &&
    error !== null &&
    typeof (error as { code?: unknown }).code === 'string' &&
    typeof (error as { message?: unknown }).message === 'string'
  );
}

export interface RequestOptions {
  method?: 'GET' | 'POST' | 'PATCH' | 'DELETE';
  body?: unknown;
  signal?: AbortSignal;
  /** Read the reply as text, for the Markdown report. */
  as?: 'json' | 'text';
}

/**
 * One request. Returns the parsed reply, or throws ApiError.
 *
 * A 204 answer, which DELETE gives, resolves to undefined.
 */
export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', body, signal, as = 'json' } = options;
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      signal: signal ?? null,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (cause) {
    const name = cause instanceof Error ? cause.name : '';
    if (OFFLINE.has(name)) {
      throw new ApiError(MESSAGES.backendDown, 0, 'backend_unreachable');
    }
    throw new ApiError(MESSAGES.backendDown, 0, 'backend_unreachable');
  }

  if (response.status === 204) {
    return undefined as T;
  }

  if (!response.ok) {
    let parsed: unknown = null;
    try {
      parsed = await response.json();
    } catch {
      parsed = null;
    }
    if (isErrorBody(parsed)) {
      throw new ApiError(parsed.error.message, response.status, parsed.error.code);
    }
    throw new ApiError(
      `The server answered with an error (HTTP ${response.status}).`,
      response.status,
      'unexpected_error',
    );
  }

  if (as === 'text') {
    return (await response.text()) as T;
  }

  try {
    return (await response.json()) as T;
  } catch {
    throw new ApiError('The server sent a reply this page could not read.', response.status, 'bad_reply');
  }
}
