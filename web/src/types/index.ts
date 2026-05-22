export interface OverviewStats {
  total_executions: number
  running: number
  success: number
  failed: number
  interrupted: number
}

export interface DAGNode {
  id: string
  label: string
  status: string
  started_at: number | null
  ended_at: number | null
  duration_ms: number | null
  token_usage: { input: number; output: number } | null
  output_summary: string | null
  cost: number | null
}

export interface DAGEdge {
  from_node: string
  to_node: string
}

export interface DAGResponse {
  thread_id: string
  nodes: DAGNode[]
  edges: DAGEdge[]
}

export interface ExecutionItem {
  thread_id: string
  workflow_name: string
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  node_count: number
  completed_nodes: number
}

export interface ExecutionListResponse {
  total: number
  items: ExecutionItem[]
}

export interface NodeEvent {
  node: string
  status: 'pending' | 'running' | 'success' | 'failed' | 'skipped'
  started_at: string | null
  ended_at: string | null
  duration_ms: number | null
  output_summary: string | null
  error: string | null
  token_usage: { input: number; output: number } | null
}

export interface ExecutionDetail {
  thread_id: string
  workflow_name: string
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  nodes: NodeEvent[]
  total_cost: number | null
  total_tokens: number | null
  task_input: string | null
}
