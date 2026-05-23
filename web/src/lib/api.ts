import type { OverviewStats, ExecutionListResponse, DAGResponse, ClarificationState, CreateExecutionRequest, SubmitClarificationAnswersRequest } from '../types'

const API_BASE = '/api'

export async function fetchOverview(): Promise<OverviewStats> {
  const res = await fetch(`${API_BASE}/overview`)
  if (!res.ok) throw new Error(`Failed to fetch overview: ${res.status}`)
  return res.json()
}

export async function fetchExecutions(
  limit = 20,
  offset = 0,
  status?: string,
): Promise<ExecutionListResponse> {
  const params = new URLSearchParams({
    limit: String(limit),
    offset: String(offset),
    ...(status && { status }),
  })
  const res = await fetch(`${API_BASE}/executions?${params}`)
  if (!res.ok) throw new Error(`Failed to fetch executions: ${res.status}`)
  return res.json()
}

export async function fetchExecution(threadId: string) {
  const res = await fetch(`/api/executions/${threadId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchDAG(threadId: string): Promise<DAGResponse> {
  const res = await fetch(`/api/executions/${threadId}/dag`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Clarification APIs (Phase 9) ──

export async function createExecution(req: CreateExecutionRequest) {
  const res = await fetch(`${API_BASE}/executions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchClarificationState(threadId: string): Promise<ClarificationState> {
  const res = await fetch(`${API_BASE}/executions/${threadId}/clarification`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function submitClarificationAnswers(req: SubmitClarificationAnswersRequest) {
  const res = await fetch(`${API_BASE}/executions/${req.thread_id}/clarification/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers: req.answers }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function skipClarification(threadId: string) {
  const res = await fetch(`${API_BASE}/executions/${threadId}/clarification/skip`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
