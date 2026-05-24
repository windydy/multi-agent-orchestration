// ── Clarification Mode Types (Phase 9 - Technical Design) ──

/**
 * Clarification mode selection for task creation
 * Determines how the ClarifierAgent handles requirement evaluation
 */
export type ClarificationMode = 'auto' | 'conservative' | 'interactive'

/**
 * Metadata for each clarification mode
 * Used in UI for mode selection display
 */
export interface ClarificationModeInfo {
  /** Mode identifier */
  mode: ClarificationMode
  /** Display icon */
  icon: string
  /** Short title */
  title: string
  /** Brief description */
  desc: string
  /** Detailed explanation */
  detail: string
  /** State machine workflow description */
  workflow: string
}

/**
 * Clarification mode metadata map
 * Provides UI display information for each mode
 */
export const CLARIFICATION_MODE_METADATA: Record<ClarificationMode, ClarificationModeInfo> = {
  auto: {
    mode: 'auto',
    icon: '⚡',
    title: 'Auto',
    desc: 'AI decides',
    detail: 'ClarifierAgent automatically evaluates and decides whether clarification is needed based on score threshold.',
    workflow: 'DRAFT → SCORING → (auto-route) → CONFIRMED or CLARIFYING',
  },
  conservative: {
    mode: 'conservative',
    icon: '🛡️',
    title: 'Conservative',
    desc: 'Safe defaults',
    detail: 'Uses safe assumptions for ambiguous requirements without asking questions. Best for well-understood tasks.',
    workflow: 'DRAFT → SCORING → CLARIFYING → (apply assumptions) → CONFIRMED',
  },
  interactive: {
    mode: 'interactive',
    icon: '💬',
    title: 'Interactive',
    desc: 'Ask questions',
    detail: 'Generates clarification questions for low-scoring dimensions. User answers to improve requirement clarity.',
    workflow: 'DRAFT → SCORING → CLARIFYING → (answer questions) → re-evaluate → CONFIRMED',
  },
}

// ── Core Execution Types ──

export interface OverviewStats {
  total_executions: number
  running: number
  success: number
  failed: number
  interrupted: number
}

// ── ClarifierAgent State Machine Types (Phase 9 - Technical Design) ──

/**
 * Requirement status enum matching the FSM design from Section 8.1:
 * DRAFT → SCORING → CLARIFYING → CONFIRMED → IN_DEVELOPMENT → COMPLETED
 *                    ↘ NEEDS_CLARIFICATION → CLARIFYING
 * DRAFT → CANCELLED (timeout/cancel)
 */
export type RequirementStatus =
  | 'draft'
  | 'scoring'
  | 'clarifying'
  | 'confirmed'
  | 'in_development'
  | 'completed'
  | 'cancelled'
  | 'needs_clarification'

/**
 * Task status enum - unified status including legacy and new FSM statuses
 */
export type TaskStatus =
  | RequirementStatus
  // Legacy statuses for backward compatibility
  | 'pending'
  | 'running'
  | 'success'
  | 'failed'
  | 'interrupted'
  | 'paused'
  | 'approved'
  | 'rejected'
  | 'scored'

/**
 * State machine events for task transitions (Section 8.1)
 */
export type StateMachineEvent =
  | 'SUBMIT_FOR_EVALUATION'    // DRAFT → SCORING
  | 'EVALUATION_COMPLETE'      // SCORING → CLARIFYING
  | 'ANSWER_CLARIFICATION'     // CLARIFYING → (re-evaluate)
  | 'AUTO_CONFIRM'             // CLARIFYING → CONFIRMED (score≥80 && pending=0)
  | 'MANUAL_CONFIRM'           // CLARIFYING → CONFIRMED (manual)
  | 'HANDOFF_TO_DEV'           // CONFIRMED → IN_DEVELOPMENT
  | 'ARCHIVE'                  // IN_DEVELOPMENT → COMPLETED
  | 'TIMEOUT'                  // Any → CANCELLED
  | 'CANCEL'                   // Any → CANCELLED
  | 'REJECT'                   // CLARIFYING → DRAFT (needs revision)

/**
 * State transition result
 */
export interface StateTransitionResult {
  success: boolean
  from_status: TaskStatus
  to_status: TaskStatus
  event: StateMachineEvent
  error?: string
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

// ── Clarification Types (Phase 9 - Aligned with Technical Design) ──

/**
 * Clarification status enum matching the state machine design (Section 8.1):
 * DRAFT → SCORING → CLARIFYING → CONFIRMED → IN_DEVELOPMENT → COMPLETED
 */
export type ClarificationStatus =
  | 'draft'
  | 'scoring'
  | 'clarifying'
  | 'confirmed'
  | 'in_development'
  | 'completed'
  | 'cancelled'
  | 'needs_clarification'
  // Legacy statuses for backward compatibility
  | 'scored'
  | 'approved'
  | 'rejected'
  | 'pending'
  | 'analyzing'
  | 'questions_ready'
  | 'answered'
  | 'skipped'
  | 'conservative'

/**
 * Clarification recommendation from the agent
 */
export type ClarificationRecommendation = 'skip' | 'conservative' | 'interactive'

/**
 * Scoring dimensions (9 dimensions from technical design Section 5.5)
 * Aligned with ClarifierAgent evaluation model
 */
export type ScoringDimension =
  | 'functional_scope'
  | 'tech_constraints'
  | 'quality_reqs'
  | 'target_users'
  | 'timeline'
  | 'integration'
  | 'success_criteria'
  | 'budget'
  | 'context'

/**
 * Human-readable labels for scoring dimensions
 */
export const SCORING_DIMENSION_LABELS: Record<ScoringDimension, string> = {
  functional_scope: 'Functional Scope',
  tech_constraints: 'Technical Constraints',
  quality_reqs: 'Quality Requirements',
  target_users: 'Target Users',
  timeline: 'Timeline',
  integration: 'Integration Needs',
  success_criteria: 'Success Criteria',
  budget: 'Budget',
  context: 'Project Context',
}

/**
 * Human-readable descriptions for scoring dimensions
 */
export const SCORING_DIMENSION_DESCRIPTIONS: Record<ScoringDimension, string> = {
  functional_scope: '功能范围是否明确（需要哪些核心功能？）',
  tech_constraints: '技术约束是否明确（技术栈偏好或限制？）',
  quality_reqs: '质量要求是否明确（性能、安全、可用性？）',
  target_users: '目标用户是否明确（面向什么用户群体？）',
  timeline: '时间要求是否明确（交付时间？）',
  integration: '集成需求是否明确（对接现有系统？）',
  success_criteria: '成功标准是否明确（怎么判断成功？）',
  budget: '预算范围是否明确（成本限制？）',
  context: '项目背景是否充分（业务场景？）',
}

/**
 * Question importance level matching the technical design (Section 6.2)
 */
export type QuestionImportance = 'high' | 'medium' | 'low'

/**
 * Clarification question matching the technical design Question model (Section 5.3)
 * Aligned with ClarifierAgent output format
 */
export interface ClarificationQuestion {
  /** Unique question identifier (q_id) */
  q_id: string
  /** Associated scoring dimension */
  dimension: ScoringDimension | string
  /** Question text */
  question: string
  /** Legacy field for backward compatibility - maps to question */
  content?: string
  /** Importance level for prioritization */
  importance: QuestionImportance
  /** Legacy field for backward compatibility - maps to importance */
  priority?: number
  /** Optional answer options for form mode (only for multiple_choice) */
  options?: string[]
  /** Whether this question is required to proceed */
  required?: boolean
  /** Optional hint or example for the user */
  hint?: string
  /** User's answer */
  user_answer?: string
  /** Whether this question has been resolved */
  is_resolved: boolean
}

/**
 * Assumption risk level matching the technical design (Section 5.4)
 */
export type AssumptionRiskLevel = 'low' | 'medium' | 'high'

/**
 * Assumption impact level (legacy, maps to risk_level)
 */
export type AssumptionImpactLevel = 'low' | 'medium' | 'high'

/**
 * Assumption model matching the technical design (Section 5.4)
 * Aligned with ClarifierAgent conservative mode output
 */
export interface Assumption {
  /** Unique assumption identifier (a_id) */
  a_id: string
  /** Associated scoring dimension */
  dimension: ScoringDimension | string
  /** Assumption content/description */
  assumption: string
  /** Legacy field for backward compatibility - maps to assumption */
  text?: string
  /** Legacy field for backward compatibility - maps to assumption */
  content?: string
  /** Risk level on final result (low, medium, high) */
  risk_level: AssumptionRiskLevel
  /** Legacy field for backward compatibility - maps to risk_level */
  impact_level?: AssumptionImpactLevel
  /** Fallback value if assumption is overturned */
  fallback_value?: any
  /** LLM confidence in this assumption (0.0~1.0) */
  confidence?: number
  /** Source of the assumption */
  source?: 'system_inferred' | 'user_confirmed'
  /** Impact scope (modules/interfaces/processes) */
  impact_scope?: string[]
  /** Whether user has confirmed acceptance */
  confirmed?: boolean
}

/**
 * Score record matching the design document ScoreRecord model
 */
export interface ScoreRecord {
  /** Score record ID */
  score_id: string
  /** 9-dimension scores {dimension: 0-100} */
  dimensions: Record<string, number>
  /** Current effective weights */
  weights: Record<string, number>
  /** Weighted total score */
  total_score: number
  /** SHA256 hash of input+prompt+weights for audit */
  audit_hash: string
  /** Intermediate feature vector for audit/debug */
  feature_vector: number[]
  /** Improvement suggestions */
  suggestions: string[]
}

/**
 * Structured summary of the requirement
 */
export interface StructuredSummary {
  /** Task objective */
  objective: string
  /** Scope boundaries */
  scope: string[]
  /** Constraints */
  constraints: string[]
  /** Acceptance criteria */
  acceptance_criteria: string[]
}

/**
 * Next action enum matching the design document (Section 5.3)
 */
export type NextAction = 'proceed' | 'ask_user' | 'retry' | 'abort'

/**
 * ClarifierResult - Main clarification result matching the technical design (Section 5.1)
 * Represents the full clarification evaluation output from ClarifierAgent
 * 
 * Aligned with Technical Design Section 5.1 Data Model:
 * - score: float (0-100)
 * - dimensions: dict[str, DimensionScore]
 * - questions: list[ClarificationQuestion]
 * - assumptions: list[Assumption]
 * - recommendation: str (skip/conservative/interactive)
 * - enriched_task: str
 * - raw_input: str
 * - task_type: str
 */
export interface ClarifierResult {
  /** Global unique identifier (session_id / requirement_id) */
  id: string
  /** Associated task ID (FK) */
  task_id?: string
  /** Session tracking ID */
  session_id?: string
  /** Original user input (1-10000 characters) */
  raw_input: string
  /** Legacy field for backward compatibility - maps to raw_input */
  requirement_text?: string
  /** Task type: development / design / analysis */
  task_type: 'development' | 'design' | 'analysis' | string
  /** Overall weighted score (0-100) */
  score: number
  /** Legacy field for backward compatibility - maps to score */
  clarity_score?: number
  /** Legacy field for backward compatibility - maps to score */
  overall_score?: number
  /** Each dimension's score (1-5) with reason */
  dimensions: Record<string, { score: number; reason: string; question?: string }>
  /** Clarification questions (max 5) */
  questions: ClarificationQuestion[]
  /** Conservative assumptions */
  assumptions: Assumption[]
  /** Routing recommendation from ClarifierAgent */
  recommendation: ClarificationRecommendation
  /** Enhanced task description with assumptions filled in (conservative mode) */
  enriched_task: string
  /** Current status in state machine */
  status: ClarificationStatus
  /** Structured summary (optional) */
  structured_summary?: StructuredSummary | null
  /** Score record (optional, for legacy compatibility) */
  score_record?: ScoreRecord | null
  /** Overall context confidence (0~1) */
  confidence_score?: number
  /** Next action to take */
  next_action?: NextAction
  /** Creation timestamp */
  created_at: string
  /** Last update timestamp */
  updated_at: string
  /** Re-evaluation round number (starts at 1) - Optimistic lock version */
  version?: number
  /** SHA256 hash of scoring snapshot for audit trail */
  audit_hash?: string
  /** Whether the total score meets the threshold */
  threshold_met?: boolean
  /** Dimensions that scored below the low-dimension threshold */
  low_dimensions?: string[]
  /** Extended metadata (token usage, model version, latency, etc.) */
  metadata?: Record<string, any>
}

/**
 * Clarification history entry for tracking interaction rounds
 * Matches technical design Section 5.2 database persistence structure
 */
export interface ClarificationHistoryEntry {
  /** Round number (1, 2, 3...) */
  round: number
  /** Questions asked in this round */
  questions: Array<{
    dimension: string
    text: string
    answer?: string
  }>
  /** Score after this round */
  score_after: number
  /** Timestamp */
  created_at?: string
}

/**
 * ClarificationState - Full state matching technical design Section 5.2
 * Represents the complete clarification state stored in execution_handles.clarification JSON
 * 
 * Database persistence structure:
 * {
 *   "status": "clarifying | clarified | conservative | skipped",
 *   "current_score": 72.5,
 *   "max_rounds": 3,
 *   "current_round": 1,
 *   "history": [...],
 *   "final_assumptions": [],
 *   "created_at": "...",
 *   "updated_at": "..."
 * }
 */
export interface ClarificationState {
  thread_id: string
  status: ClarificationStatus | 'pending' | 'analyzing' | 'questions_ready' | 'answered' | 'skipped' | 'conservative'
  score: number | null
  recommendation: ClarificationRecommendation | null
  questions: ClarificationQuestion[]
  assumptions: Assumption[]
  answers: Record<string, string>
  enriched_task: string | null
  created_at: string
  updated_at: string
  /** Full ClarifierResult if available */
  clarifier_result?: ClarifierResult | null
  /** Re-evaluation version number (optimistic lock) */
  version: number
  /** Last activity timestamp for timeout detection */
  last_activity?: string
  /** Clarity score from ClarifierResult (0~100) */
  clarity_score?: number
  /** Confidence score from ClarifierResult (0~1) */
  confidence_score?: number
  /** Next action from ClarifierResult */
  next_action?: NextAction
  /** Whether the score meets the threshold (Section 5.1) */
  threshold_met?: boolean
  /** Dimensions that scored below threshold (Section 5.1) */
  low_dimensions?: string[]
  /** Total weighted score (1.0-5.0) from design document */
  total_score?: number
  /** Maximum allowed clarification rounds (default: 3) */
  max_rounds?: number
  /** Current interaction round number */
  current_round?: number
  /** History of clarification rounds */
  history?: ClarificationHistoryEntry[]
  /** Final assumptions used when skipping clarification */
  final_assumptions?: Assumption[]
}

/**
 * Request to create a new execution/task
 */
export interface CreateExecutionRequest {
  /** Task description/requirement text */
  task: string
  /** Optional workflow name */
  workflow?: string
  /** Optional project path */
  project_path?: string
  /** Model overrides per agent */
  models?: Record<string, string>
  /** Maximum iteration count */
  max_iterations?: number
  /** Clarification mode selection */
  clarification_mode?: 'auto' | 'conservative' | 'interactive'
}

/**
 * Response from creating an execution
 */
export interface CreateExecutionResponse {
  thread_id: string
  status: string
  started_at: number
  workflow: string
  clarification?: ClarificationState
}

/**
 * Request to submit clarification answers
 */
export interface SubmitClarificationAnswersRequest {
  thread_id: string
  answers: Record<string, string>
}

/**
 * Request to transition task state
 */
export interface TransitionStateRequest {
  thread_id: string
  target_status: ClarificationStatus
  reason?: string
}

/**
 * Request to calculate score
 */
export interface CalculateScoreRequest {
  thread_id: string
  config_version?: string
}

// ── Scoring Engine Types (Phase 9 - Technical Design Section 7) ──

/**
 * 9-dimension score interface from technical design Section 5.2
 * Each dimension scored 1-5
 * Aligned with ClarifierAgent evaluation model
 */
export interface DimensionScore {
  /** 功能范围是否明确 */
  functional_scope: number
  /** 技术约束是否明确 */
  tech_constraints: number
  /** 质量要求是否明确 */
  quality_reqs: number
  /** 目标用户是否明确 */
  target_users: number
  /** 时间要求是否明确 */
  timeline: number
  /** 集成需求是否明确 */
  integration: number
  /** 成功标准是否明确 */
  success_criteria: number
  /** 预算范围是否明确 */
  budget: number
  /** 项目背景是否充分 */
  context: number
}

/**
 * Weight configuration for scoring dimensions
 * Weights from technical design Section 5.5 (development task type)
 */
export interface WeightConfig {
  functional_scope: number
  tech_constraints: number
  quality_reqs: number
  target_users: number
  timeline: number
  integration: number
  success_criteria: number
  budget: number
  context: number
}

/**
 * Default weights from technical design Section 5.5
 * Total weight = 9.8
 * Score formula: (weighted_avg - 1) / 4 * 100
 */
export const DEFAULT_WEIGHTS: WeightConfig = {
  functional_scope: 1.5,
  tech_constraints: 1.5,
  quality_reqs: 1.2,
  target_users: 1.0,
  timeline: 1.0,
  integration: 1.0,
  success_criteria: 1.0,
  budget: 0.8,
  context: 0.8,
}

/**
 * Default threshold for score approval (80 = skip mode)
 * From technical design Section 7.2
 */
export const SCORE_THRESHOLD = 80

/**
 * Score recommendation thresholds
 */
export const SCORE_THRESHOLDS = {
  /** Score >= 80: skip mode, direct pass */
  SKIP: 80,
  /** Score 50-79: conservative mode, use assumptions */
  CONSERVATIVE_MIN: 50,
  /** Score < 50: interactive mode, generate questions */
  INTERACTIVE_MAX: 49,
} as const

/**
 * Scoring result with validation
 */
export interface ScoringResult {
  totalScore: number
  isBelowThreshold: boolean
  conflicts: string[]
  dimensions: DimensionScore
}

/**
 * Draft data for offline/local storage
 */
export interface DraftData {
  taskId: string
  dimensions: Partial<DimensionScore>
  comment: string
  savedAt: string
  version: number
}

/**
 * Frontend ClarifierState - Zustand store interface for frontend state management
 * Matches the design document Section 8.3
 * 
 * Note: This is different from ClarificationState which represents the backend state.
 * This interface is for the frontend store that manages the UI state.
 */
export interface ClarifierStoreState {
  task: ExecutionDetail | null
  status: TaskStatus
  draft: Partial<DimensionScore> | null
  score: number | null
  isLoading: boolean
  error: string | null
  clarification: ClarificationState | null
  scoreRecord: ScoreRecord | null

  // Actions
  loadTask: (id: string) => Promise<void>
  updateDimension: (dim: keyof DimensionScore, value: number) => void
  submitScore: () => Promise<void>
  saveDraft: () => void
  syncFromServer: () => void
  clearError: () => void
}

/**
 * Frontend Clarifier UI State Machine (Technical Design Section 8)
 * Represents the UI state for the clarification flow
 * Used by Zustand store for frontend state management
 */
export type ClarifierUIState =
  | { status: 'idle' }
  | { status: 'loading' }
  | { status: 'needs_clarification'; questions: ClarificationQuestion[]; assumptions: Assumption[] }
  | { status: 'assumed'; assumptions: Assumption[]; proceedUrl: string }
  | { status: 'clear'; proceedUrl: string }
  | { status: 'error'; message: string }

/**
 * Question type aligned with Technical Design Section 5.1
 * Represents a clarification question from the ClarifierAgent
 */
export interface ClarifierQuestion {
  /** UUID v4, unique identifier */
  id: string
  /** Natural language question for the user */
  text: string
  /** Interaction control type */
  type: 'single_choice' | 'multi_choice' | 'text' | 'confirm'
  /** Option list (only valid for choice types) */
  options?: string[] | null
  /** Whether must be answered to proceed */
  required: boolean
  /** Associated original input fragment or business field */
  context_ref?: string | null
}

/**
 * Assumption type aligned with Technical Design Section 5.2
 * Represents a reasonable assumption from the ClarifierAgent
 */
export interface ClarifierAssumption {
  /** UUID v4, unique identifier */
  id: string
  /** Assumption description (e.g., "Default to Beijing time") */
  text: string
  /** LLM original confidence [0.0, 1.0] */
  confidence: number
  /** Impact level on downstream tasks */
  impact_level: 'low' | 'medium' | 'high'
  /** Degradation strategy if assumption is overturned */
  fallback_action?: string | null
}

/**
 * ClarifierResult aligned with Technical Design Section 5.3
 * Final output from the ClarifierAgent
 */
export interface ClarifierResultV2 {
  /** Session identifier */
  session_id: string
  /** Processing status */
  status: 'clear' | 'needs_clarification' | 'assumed' | 'failed'
  /** Pending clarification questions */
  questions: ClarifierQuestion[]
  /** Adopted assumptions */
  assumptions: ClarifierAssumption[]
  /** Comprehensive score [0, 100] */
  overall_score: number
  /** LLM reasoning process summary (can be desensitized) */
  reasoning?: string | null
  /** Metadata: latency, model version, token consumption, etc. */
  metadata: Record<string, any>
}

/**
 * Score submission request with idempotency support
 */
export interface SubmitScoreRequest {
  thread_id: string
  dimensions: DimensionScore
  comment?: string
  idempotency_key: string
  version?: number
}

/**
 * Score submission response
 */
export interface SubmitScoreResponse {
  score_id: string
  total_score: number
  status: ClarificationStatus
  version: number
}

/**
 * Clarification audit entry for audit trail
 */
export interface ClarificationAuditEntry {
  id: string
  task_id: string
  action: 'question_generated' | 'answer_submitted' | 'score_calculated' | 'state_transition'
  details: Record<string, any>
  operator_id: string
  created_at: string
}

/**
 * Prompt context for AI-assisted clarification
 * Matches design document Section 6.2
 */
export interface PromptContext {
  taskDescription: string
  lowScoreDimensions: { name: string; score: number; weight: number }[]
  historicalContext: string
  threshold: number
}

/**
 * AI-generated clarification question
 */
export interface AIClarificationQuestion {
  dimension: string
  question: string
  suggestion: string
}
