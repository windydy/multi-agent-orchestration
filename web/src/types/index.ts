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
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  node_count: number
  completed_nodes: number
}

export interface NodeEvent {
  node: string
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  output_summary: string | null
  error: string | null
  token_usage: { input: number; output: number } | null
}

export interface ExecutionDetail {
  thread_id: string
  status: string
  started_at: string
  ended_at: string | null
  duration_ms: number | null
  nodes: NodeEvent[]
  total_cost: number | null
  total_tokens: number | null
  task_input: string | null
}

export interface ExecutionListResponse {
  total: number
  items: ExecutionItem[]
}

export interface WorkflowResponse {
  name: string
  description: string
  yaml_content: string
  created_at: number
  updated_at: number
}

export interface AgentResponse {
  id: string
  name: string
  description: string
  capabilities: string[]
  model: string
  enabled: boolean
  created_at: number
  updated_at: number
}

export interface VerifierResponse {
  id: string
  name: string
  condition: string
  threshold: number
  action: string
  severity: string
  enabled: boolean
  created_at: number
  updated_at: number
}
