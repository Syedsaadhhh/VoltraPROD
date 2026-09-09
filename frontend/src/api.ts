/**
 * Frontend API client communicating with FastAPI backend.
 */

import { Session, EditBatch, ToolResult, SystemStatusResponse } from './types';

import { getAuthToken } from './firebase';

const BASE_URL = '';

async function getAuthHeaders(): Promise<Record<string, string>> {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  const token = await getAuthToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function fetchHealth(): Promise<{ status: string; app: string; version: string }> {
  const res = await fetch(`${BASE_URL}/health`);
  if (!res.ok) {
    throw new Error(`Health check failed with status ${res.status}`);
  }
  return res.json();
}

export async function fetchSystemStatus(): Promise<SystemStatusResponse> {
  const res = await fetch(`${BASE_URL}/api/status`);
  if (!res.ok) {
    throw new Error(`System status query failed with status ${res.status}`);
  }
  return res.json();
}

export async function createSession(session: Partial<Session>): Promise<Session> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/sessions`, {
    method: 'POST',
    headers,
    body: JSON.stringify(session),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to create session (${res.status})`);
  }
  return res.json();
}

export async function getSession(sessionId: string): Promise<Session> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/sessions/${sessionId}`, {
    headers,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to fetch session (${res.status})`);
  }
  return res.json();
}

export async function applyEditBatch(sessionId: string, batch: EditBatch): Promise<ToolResult> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/sessions/${sessionId}/edits`, {
    method: 'POST',
    headers,
    body: JSON.stringify(batch),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to apply edit batch (${res.status})`);
  }
  return res.json();
}

export async function sendDirection(
  sessionId: string,
  request: import('./types').DirectorDirectionRequest
): Promise<import('./types').DirectorDirectionResponse> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/sessions/${sessionId}/direct`, {
    method: 'POST',
    headers,
    body: JSON.stringify(request),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to run direction (${res.status})`);
  }
  return res.json();
}

export async function fetchCatalogAssets(): Promise<{ status: string; assets: import('./types').Asset[]; count: number }> {
  const res = await fetch(`${BASE_URL}/api/catalog/assets`);
  if (!res.ok) {
    throw new Error(`Failed to fetch sound assets (${res.status})`);
  }
  return res.json();
}

export async function submitAuditionFeedback(
  sessionId: string,
  feedback: import('./types').AuditionFeedback
): Promise<{ status: string }> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE_URL}/api/sessions/${sessionId}/feedback`, {
    method: 'POST',
    headers,
    body: JSON.stringify(feedback),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || `Failed to submit feedback (${res.status})`);
  }
  return res.json();
}

