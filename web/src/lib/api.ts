import type {
  OverviewStats,
  ExecutionListResponse,
  DAGResponse,
  ClarificationState,
  ClarifierResult,
  ScoreRecord,
  CreateExecutionRequest,
  SubmitClarificationAnswersRequest,
  TransitionStateRequest,
  CalculateScoreRequest,
  DimensionScore,
  SubmitScoreRequest,
  SubmitScoreResponse,
  DraftData,
  ClarificationHistoryEntry,
  StateTransitionResult,
  ClarificationStatus,
  ClarificationRecommendation,
  ClarificationMode,
  ClarificationQuestion,
  Assumption,
} from '../types'

const API_BASE = '/api'
const API_V1 = '/api/v1'

// ── Overview & Execution APIs ──

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
  const res = await fetch(`${API_BASE}/executions/${threadId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export async function fetchDAG(threadId: string): Promise<DAGResponse> {
  const res = await fetch(`${API_BASE}/executions/${threadId}/dag`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Clarification APIs (Phase 9 - Aligned with Technical Design) ──

/**
 * Create a new execution with optional clarification mode
 * Maps to: POST /v1/requirements (DRAFT state)
 */
export async function createExecution(req: CreateExecutionRequest) {
  const res = await fetch(`${API_BASE}/executions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Fetch current clarification state for a task
 * Maps to: GET /v1/clarify/sync (for breakpoint resume)
 */
export async function fetchClarificationState(threadId: string): Promise<ClarificationState> {
  const res = await fetch(`${API_BASE}/executions/${threadId}/clarification`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Fetch full ClarifierResult with all details
 * Maps to: GET /v1/requirements/{id}
 */
export async function fetchClarifierResult(threadId: string): Promise<ClarifierResult> {
  const res = await fetch(`${API_V1}/requirements/${threadId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Submit answers to clarification questions
 * Maps to: POST /v1/clarify/next
 */
export async function submitClarificationAnswers(req: SubmitClarificationAnswersRequest) {
  const res = await fetch(`${API_BASE}/executions/${req.thread_id}/clarification/answers`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers: req.answers }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Skip clarification and use conservative assumptions
 * Maps to: POST /v1/clarify/skip
 */
export async function skipClarification(threadId: string) {
  const res = await fetch(`${API_BASE}/executions/${threadId}/clarification/skip`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Transition task state (approve/reject)
 * Maps to: POST /v1/tasks/{id}/transition
 */
export async function transitionState(req: TransitionStateRequest) {
  const res = await fetch(`${API_V1}/tasks/${req.thread_id}/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_status: req.target_status,
      reason: req.reason,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Calculate score for a clarified requirement
 * Maps to: POST /v1/score/calculate
 */
export async function calculateScore(req: CalculateScoreRequest) {
  const res = await fetch(`${API_V1}/score/calculate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: req.thread_id,
      config_version: req.config_version,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json() as Promise<ScoreRecord>
}

/**
 * Get audit trail for a score record
 * Maps to: GET /v1/score/{score_id}/audit
 */
export async function getAuditTrail(scoreId: string) {
  const res = await fetch(`${API_V1}/score/${scoreId}/audit`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Sync clarification state from server (for breakpoint resume)
 * Maps to: GET /v1/clarify/sync
 */
export async function syncClarificationState(threadId: string): Promise<ClarificationState> {
  const res = await fetch(`${API_V1}/clarify/sync?thread_id=${threadId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Score Submission APIs (Phase 9 - Technical Design Section 7 & 8) ──

/**
 * Submit score with idempotency support
 * Maps to: POST /v1/score/submit
 * Uses Idempotency-Key header to prevent duplicate submissions
 */
export async function submitScore(req: SubmitScoreRequest): Promise<SubmitScoreResponse> {
  const res = await fetch(`${API_V1}/score/submit`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': req.idempotency_key,
    },
    body: JSON.stringify({
      thread_id: req.thread_id,
      dimensions: req.dimensions,
      comment: req.comment,
      version: req.version,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get current clarification status for a task
 * Maps to: GET /v1/tasks/{id}/status
 */
export async function getClarificationStatus(threadId: string): Promise<{
  status: string
  version: number
  last_updated: string
}> {
  const res = await fetch(`${API_V1}/tasks/${threadId}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get clarification history/audit trail for a task
 * Maps to: GET /v1/tasks/{id}/clarification/history
 */
export async function getClarificationHistory(threadId: string): Promise<ClarificationHistoryEntry[]> {
  const res = await fetch(`${API_V1}/tasks/${threadId}/clarification/history`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Transition task state with validation
 * Maps to: POST /v1/tasks/{id}/transition
 * Returns transition result with success/failure status
 */
export async function transitionStateValidated(req: TransitionStateRequest): Promise<StateTransitionResult> {
  const res = await fetch(`${API_V1}/tasks/${req.thread_id}/transition`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      target_status: req.target_status,
      reason: req.reason,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Draft Management APIs (Phase 9 - Technical Design Section 8.3) ──

/**
 * Save draft to server
 * Maps to: PUT /v1/draft/{thread_id}
 */
export async function saveDraft(threadId: string, data: Partial<DimensionScore>): Promise<{ saved: boolean; version: number }> {
  const res = await fetch(`${API_V1}/draft/${threadId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ dimensions: data }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Load draft from server
 * Maps to: GET /v1/draft/{thread_id}
 */
export async function loadDraft(threadId: string): Promise<DraftData | null> {
  const res = await fetch(`${API_V1}/draft/${threadId}`)
  if (res.status === 404) return null
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Delete draft
 * Maps to: DELETE /v1/draft/{thread_id}
 */
export async function deleteDraft(threadId: string): Promise<void> {
  const res = await fetch(`${API_V1}/draft/${threadId}`, { method: 'DELETE' })
  if (!res.ok) throw new Error(await res.text())
}

// ── Local Storage Draft Helpers (Offline Support) ──

const DRAFT_STORAGE_KEY = 'clarifier_drafts'

/**
 * Save draft to localStorage for offline support
 */
export function saveDraftLocal(data: DraftData): void {
  try {
    const drafts = JSON.parse(localStorage.getItem(DRAFT_STORAGE_KEY) || '{}')
    drafts[data.taskId] = data
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(drafts))
  } catch (e) {
    console.warn('Failed to save draft to localStorage:', e)
  }
}

/**
 * Load draft from localStorage
 */
export function loadDraftLocal(taskId: string): DraftData | null {
  try {
    const drafts = JSON.parse(localStorage.getItem(DRAFT_STORAGE_KEY) || '{}')
    return drafts[taskId] || null
  } catch (e) {
    console.warn('Failed to load draft from localStorage:', e)
    return null
  }
}

/**
 * Clear draft from localStorage
 */
export function clearDraftLocal(taskId: string): void {
  try {
    const drafts = JSON.parse(localStorage.getItem(DRAFT_STORAGE_KEY) || '{}')
    delete drafts[taskId]
    localStorage.setItem(DRAFT_STORAGE_KEY, JSON.stringify(drafts))
  } catch (e) {
    console.warn('Failed to clear draft from localStorage:', e)
  }
}

/**
 * Generate unique idempotency key
 */
export function generateIdempotencyKey(): string {
  return `ik_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
}

// ── Clarification Status APIs (Phase 9 - Technical Design Section 8.2) ──

/**
 * Submit clarification answers and trigger re-evaluation
 * Maps to: POST /v1/requirements/{id}/clarify
 * This updates the requirement version and triggers the ClarifierAgent to re-evaluate
 * 
 * Implements optimistic lock with If-Match header (Section 8.2):
 * - Carries version number for concurrent update detection
 * - Returns 409 Conflict if version mismatch
 * - Frontend should handle rollback on conflict
 */
export async function submitClarification(req: {
  thread_id: string
  answers: Record<string, string>
  version?: number
}): Promise<{
  status: ClarificationStatus
  version: number
  requires_re_evaluation: boolean
}> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (req.version != null) {
    headers['If-Match'] = String(req.version)
  }
  
  const res = await fetch(`${API_V1}/requirements/${req.thread_id}/clarify`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      answers: req.answers,
      version: req.version,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get current clarification status for a requirement
 * Maps to: GET /v1/requirements/{id}/status
 * Returns current status, version, and pending question count
 */
export async function getRequirementStatus(threadId: string): Promise<{
  status: ClarificationStatus
  version: number
  pending_questions: number
  total_score: number | null
  last_updated: string
}> {
  const res = await fetch(`${API_V1}/requirements/${threadId}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get full ClarifierResult with all evaluation details
 * Maps to: GET /v1/requirements/{id}
 * Returns complete clarification state including questions, assumptions, and scores
 */
export async function getRequirementDetail(threadId: string): Promise<ClarifierResult> {
  const res = await fetch(`${API_V1}/requirements/${threadId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Trigger manual re-evaluation of a requirement
 * Maps to: POST /v1/requirements/{id}/re-evaluate
 * Used when user modifies requirement content or answers questions
 */
export async function triggerReEvaluation(threadId: string): Promise<{
  status: ClarificationStatus
  evaluation_id: string
}> {
  const res = await fetch(`${API_V1}/requirements/${threadId}/re-evaluate`, {
    method: 'POST',
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get version history for a requirement
 * Maps to: GET /v1/requirements/{id}/versions
 * Returns all version snapshots with scores
 */
export async function getRequirementVersions(threadId: string): Promise<{
  version_no: number
  content_snapshot: string
  score_snapshot: ScoreRecord | null
  created_at: string
}[]> {
  const res = await fetch(`${API_V1}/requirements/${threadId}/versions`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Compare two versions of a requirement
 * Maps to: GET /v1/requirements/{id}/diff?v1={v1}&v2={v2}
 * Returns change set between versions
 */
export async function diffRequirementVersions(
  threadId: string,
  v1: number,
  v2: number
): Promise<{
  added: string[]
  removed: string[]
  modified: { field: string; old: string; new: string }[]
}> {
  const res = await fetch(`${API_V1}/requirements/${threadId}/diff?v1=${v1}&v2=${v2}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Clarification Status Submission & Polling APIs (Phase 9 - Technical Design Section 8.2) ──

/**
 * Submit clarification status update
 * Maps to: POST /api/clarification/status
 * Used to update the clarification state during interactive mode
 */
export async function submitClarificationStatus(req: {
  thread_id: string
  status: ClarificationStatus
  score?: number
  recommendation?: ClarificationRecommendation
  version?: number
  answers?: Record<string, string>
}): Promise<{
  success: boolean
  status: ClarificationStatus
  version: number
}> {
  const res = await fetch(`${API_BASE}/clarification/status`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      thread_id: req.thread_id,
      status: req.status,
      score: req.score,
      recommendation: req.recommendation,
      version: req.version,
      answers: req.answers,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Poll clarification status for a task
 * Maps to: GET /api/clarification/{thread_id}/status
 * Used for polling during SCORING and CLARIFYING states
 * Returns current status with version and last updated timestamp
 */
export async function pollClarificationStatus(threadId: string): Promise<{
  status: ClarificationStatus
  version: number
  score: number | null
  recommendation: ClarificationRecommendation | null
  pending_questions: number
  last_updated: string
  is_timeout: boolean
}> {
  const res = await fetch(`${API_BASE}/clarification/${threadId}/status`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Analyze task description with ClarifierAgent
 * Maps to: POST /api/clarification/analyze
 * Triggers the ClarifierAgent to evaluate task completeness
 * 
 * Request body aligned with technical design Section 3.3 API contract
 */
export async function analyzeClarification(req: {
  task: string
  task_type?: string
  clarification_mode?: ClarificationMode
}): Promise<{
  score: number
  recommendation: ClarificationRecommendation
  dimensions: Record<string, { score: number; reason: string; question?: string }>
  questions: Array<{ dimension: string; question: string; importance: string }>
  assumptions: Array<{ dimension: string; assumption: string; risk_level: string }>
  enriched_task: string
}> {
  const res = await fetch(`${API_BASE}/clarification/analyze`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      task: req.task,
      task_type: req.task_type || 'development',
      clarification_mode: req.clarification_mode || 'auto',
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Re-evaluate clarification based on user answers
 * Maps to: POST /api/clarification/re-evaluate
 * Triggers re-scoring after user provides answers to clarification questions
 */
export async function reEvaluateClarification(req: {
  original_task: string
  user_answers: Record<string, string>
  task_type?: string
}): Promise<{
  score: number
  recommendation: ClarificationRecommendation
  dimensions: Record<string, { score: number; reason: string; question?: string }>
  questions: Array<{ dimension: string; question: string; importance: string; user_answer?: string }>
  assumptions: Array<{ dimension: string; assumption: string; risk_level: string }>
  enriched_task: string
  version: number
}> {
  const res = await fetch(`${API_BASE}/clarification/re-evaluate`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      original_task: req.original_task,
      user_answers: req.user_answers,
      task_type: req.task_type || 'development',
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get clarification dimension definitions and weights
 * Maps to: GET /api/clarification/dimensions
 * Returns all 9 clarification dimensions with labels, descriptions, and weights
 */
export async function getClarificationDimensions(): Promise<{
  dimensions: Array<{
    name: string
    label: string
    description: string
    weight: number
    example_question: string
  }>
  default_weights: Record<string, number>
  task_type_weights: Record<string, Record<string, number>>
}> {
  const res = await fetch(`${API_BASE}/clarification/dimensions`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── ClarifierResult APIs (Phase 9 - Technical Design Section 5.3) ──

/**
 * Submit clarification status with full ClarifierResult
 * Maps to: POST /api/v1/clarify
 * Returns updated ClarifierResult with next_action
 */
export async function submitClarifyRequest(req: {
  input: string
  context?: Record<string, any>
  session_id?: string
  answers?: Record<string, string>
}): Promise<ClarifierResult> {
  const res = await fetch(`${API_V1}/clarify`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      input: req.input,
      context: req.context,
      session_id: req.session_id,
      answers: req.answers,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get clarification status by session ID
 * Maps to: GET /api/v1/clarify/{session_id}
 * Returns current ClarifierResult for the session
 */
export async function getClarifySession(sessionId: string): Promise<ClarifierResult> {
  const res = await fetch(`${API_V1}/clarify/${sessionId}`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Process answers and get updated ClarifierResult
 * Maps to: POST /api/v1/clarify/{session_id}/answer
 * Merges answers with context and re-evaluates
 */
export async function processClarifyAnswers(req: {
  session_id: string
  answers: Record<string, string>
}): Promise<ClarifierResult> {
  const res = await fetch(`${API_V1}/clarify/${req.session_id}/answer`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      answers: req.answers,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

// ── Clarification State Submission & Retrieval APIs (Phase 9 - Technical Design Section 8.2) ──

/**
 * Submit clarification state update for an execution
 * Maps to: POST /api/executions/{id}/clarification
 * Updates the clarification JSON in execution_handles with new state
 * 
 * Request body aligned with technical design Section 5.2 database structure:
 * {
 *   "status": "clarifying | clarified | conservative | skipped",
 *   "current_score": 72.5,
 *   "current_round": 1,
 *   "answers": {...},
 *   "version": 1
 * }
 */
export async function submitClarificationState(req: {
  thread_id: string
  status: ClarificationStatus
  score?: number
  answers?: Record<string, string>
  current_round?: number
  version?: number
}): Promise<{
  success: boolean
  status: ClarificationStatus
  version: number
  current_score: number | null
  current_round: number
}> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (req.version != null) {
    headers['If-Match'] = String(req.version)
  }
  
  const res = await fetch(`${API_BASE}/executions/${req.thread_id}/clarification`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      status: req.status,
      score: req.score,
      answers: req.answers,
      current_round: req.current_round,
      version: req.version,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Get clarification state for an execution
 * Maps to: GET /api/executions/{id}/clarification
 * Returns the full clarification JSON from execution_handles
 * 
 * Response aligned with technical design Section 5.2:
 * {
 *   "status": "clarifying",
 *   "current_score": 72.5,
 *   "max_rounds": 3,
 *   "current_round": 1,
 *   "history": [...],
 *   "questions": [...],
 *   "assumptions": [...]
 * }
 */
export async function getClarificationState(threadId: string): Promise<ClarificationState> {
  const res = await fetch(`${API_BASE}/executions/${threadId}/clarification`)
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

/**
 * Submit clarification answers and trigger re-evaluation
 * Maps to: POST /api/executions/{id}/clarify
 * This is the main endpoint for the interactive clarification loop
 * 
 * Implements the state machine transition from Section 8.1:
 * - If score >= 80 after re-evaluation: status → "clarified"
 * - If score < 80 and round < 3: status → "clarifying" (continue)
 * - If round >= 3: status → "conservative" (fallback)
 */
export async function submitClarifyAnswers(req: {
  thread_id: string
  answers: Record<string, string>
  version?: number
}): Promise<{
  status: ClarificationStatus
  score: number
  recommendation: ClarificationRecommendation
  questions: ClarificationQuestion[]
  assumptions: Assumption[]
  current_round: number
  version: number
  requires_re_evaluation: boolean
}> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (req.version != null) {
    headers['If-Match'] = String(req.version)
  }
  
  const res = await fetch(`${API_BASE}/executions/${req.thread_id}/clarify`, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      answers: req.answers,
      version: req.version,
    }),
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}
