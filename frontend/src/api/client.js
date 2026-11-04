import { readStore, writeStore, removeStore } from '../lib/storage.js';
import { readEventStream } from './sse.js';

const API_BASE_URL = (
  import.meta.env.VITE_API_BASE_URL || ''
).replace(/\/$/, '');

const TOKEN_KEY = 'documind.token';

export const tokenStore = {
  get: () => readStore('local', TOKEN_KEY),
  set: (token) => writeStore('local', TOKEN_KEY, token),
  clear: () => removeStore('local', TOKEN_KEY),
};

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

let unauthorizedHandler = () => {};

/** The auth provider registers how the app reacts to an expired session. */
export function setUnauthorizedHandler(handler) {
  unauthorizedHandler = handler;
}

const FALLBACK_MESSAGES = {
  401: 'Your session has expired. Sign in again to continue.',
  403: 'You do not have access to this item.',
  404: 'This item no longer exists. Reload the page to refresh the list.',
  409: 'This conflicts with an existing item. Change the details and try again.',
  422: 'Some of the details are not valid. Check them and try again.',
  429: 'Too many requests. Wait a moment and try again.',
  503: 'A service this feature depends on is unavailable. Try again in a minute.',
};

function networkError() {
  return new ApiError(0, 'network_error', 'Cannot reach the server. Check your connection and try again.');
}

async function toApiError(response, { auth }) {
  let code = 'internal_error';
  let message = FALLBACK_MESSAGES[response.status] || `The server returned an error (${response.status}). Try again.`;
  try {
    const payload = await response.json();
    if (payload && payload.error) {
      code = payload.error.code || code;
      message = payload.error.message || message;
    }
  } catch {
    /* body was not JSON; keep the fallback message */
  }
  if (response.status === 401 && auth) {
    tokenStore.clear();
    unauthorizedHandler();
    code = 'unauthorized';
  }
  return new ApiError(response.status, code, message);
}

function headers(auth, extra = {}) {
  const result = { ...extra };
  const token = auth ? tokenStore.get() : null;
  if (token) result.Authorization = `Bearer ${token}`;
  return result;
}

async function request(path, { method = 'GET', json, form, signal, auth = true } = {}) {
  const init = { method, signal, headers: headers(auth) };
  if (json !== undefined) {
    init.headers['Content-Type'] = 'application/json';
    init.body = JSON.stringify(json);
  } else if (form) {
    init.body = form;
  }
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, init);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw networkError();
  }
  if (!response.ok) throw await toApiError(response, { auth });
  if (response.status === 204) return null;
  try {
    return await response.json();
  } catch {
    throw new ApiError(response.status, 'internal_error', 'The server sent an unreadable response. Try again.');
  }
}

/**
 * POST /api/sessions/{id}/ask. Resolves when the stream closes; the caller
 * decides from the events it saw whether the answer completed.
 */
export async function askStream(sessionId, body, signal, onEvent) {
  let response;
  try {
    response = await fetch(`${API_BASE_URL}/api/sessions/${encodeURIComponent(sessionId)}/ask`, {
      method: 'POST',
      signal,
      headers: headers(true, { 'Content-Type': 'application/json', Accept: 'text/event-stream' }),
      body: JSON.stringify(body),
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw networkError();
  }
  if (!response.ok) throw await toApiError(response, { auth: true });
  if (!response.body) {
    throw new ApiError(0, 'network_error', 'The browser could not read the streamed answer. Try another browser.');
  }
  try {
    await readEventStream(response.body, onEvent);
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new ApiError(0, 'network_error', 'The connection dropped while the answer was streaming. Ask again to retry.');
  }
}

export const api = {
  login: (email, password) => request('/api/auth/login', { method: 'POST', json: { email, password }, auth: false }),
  register: (email, password) => request('/api/auth/register', { method: 'POST', json: { email, password }, auth: false }),
  me: (signal) => request('/api/auth/me', { signal }),

  listDocuments: (signal) => request('/api/documents', { signal }),
  uploadDocuments: (files) => {
    const form = new FormData();
    for (const file of files) form.append('files', file, file.name);
    return request('/api/documents', { method: 'POST', form });
  },
  deleteDocument: (id) => request(`/api/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  reindexDocument: (id) => request(`/api/documents/${encodeURIComponent(id)}/reindex`, { method: 'POST' }),
  loadSampleDocuments: () => request('/api/documents/sample', { method: 'POST' }),

  listSessions: (signal) => request('/api/sessions', { signal }),
  searchSessions: (q, signal) => request(`/api/sessions/search?q=${encodeURIComponent(q)}&limit=25`, { signal }),
  submitFeedback: (id, rating, reason) => request(`/api/messages/${encodeURIComponent(id)}/feedback`, { method: 'POST', json: { rating, reason } }),
  exportSession: (id) => request(`/api/sessions/${encodeURIComponent(id)}/export`),
  createSession: (title) => request('/api/sessions', { method: 'POST', json: title ? { title } : {} }),
  renameSession: (id, title) => request(`/api/sessions/${encodeURIComponent(id)}`, { method: 'PATCH', json: { title } }),
  deleteSession: (id) => request(`/api/sessions/${encodeURIComponent(id)}`, { method: 'DELETE' }),
  listMessages: (id, signal) => request(`/api/sessions/${encodeURIComponent(id)}/messages`, { signal }),

  stats: (signal) => request('/api/stats', { signal }),
  latestEval: (signal) => request('/api/eval/latest', { signal }),
};
