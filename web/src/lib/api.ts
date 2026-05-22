import type { OverviewStats, ExecutionListResponse } from '../types'

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

export async function fetchDAG(threadId: string) {
  const res = await fetch(`/api/executions/${threadId}/dag`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
