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

// ── Clarification Types (Phase 9) ──

export type ClarificationRecommendation = 'skip' | 'conservative' | 'interactive'

export interface ClarificationQuestion {
  id: string
  dimension: string
  question: string
  context: string
  priority: 'high' | 'medium' | 'low'
}

export interface Assumption {
  id: string
  dimension: string
  assumption: string
  risk: 'high' | 'medium' | 'low'
}

export interface ClarificationState {
  thread_id: string
  status: 'pending' | 'analyzing' | 'questions_ready' | 'answered' | 'skipped' | 'conservative'
  score: number | null
  recommendation: ClarificationRecommendation | null
  questions: ClarificationQuestion[]
  assumptions: Assumption[]
  answers: Record<string, string>
  enriched_task: string | null
  created_at: string
  updated_at: string
}

export interface CreateExecutionRequest {
  task: string
  workflow?: string
  project_path?: string
  models?: Record<string, string>
  max_iterations?: number
  clarification_mode?: 'auto' | 'conservative' | 'interactive'
}

export interface CreateExecutionResponse {
  thread_id: string
  status: string
  started_at: number
  workflow: string
  clarification?: ClarificationState
}

export interface SubmitClarificationAnswersRequest {
  thread_id: string
  answers: Record<string, string>
}
