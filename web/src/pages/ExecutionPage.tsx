import { useEffect, useState, useCallback } from 'react'
import { Link, useParams } from 'react-router-dom'
import {
  ExecutionDetail,
  DAGResponse,
  ClarificationState,
  ClarificationQuestion,
  ScoreRecord,
  ClarificationStatus,
  TaskStatus,
  SCORE_THRESHOLD,
  SCORE_THRESHOLDS,
} from '../types'
import {
  fetchExecution,
  fetchDAG,
  fetchClarificationState,
  submitClarificationAnswers,
  skipClarification,
  transitionState,
  calculateScore,
  saveDraftLocal,
  loadDraftLocal,
  clearDraftLocal,
} from '../lib/api'
import NodeTimeline from '../components/NodeTimeline'
import DAGView from '../components/DAGView'

// ── Status Labels ──

const statusLabel: Record<string, { text: string; color: string }> = {
  success: { text: 'Completed', color: 'text-success' },
  running: { text: 'Running', color: 'text-running' },
  failed: { text: 'Failed', color: 'text-error' },
  interrupted: { text: 'Interrupted', color: 'text-warning' },
  clarifying: { text: 'Clarifying', color: 'text-accent' },
  paused: { text: 'Paused', color: 'text-warning' },
  // State machine statuses from design (Section 8.1)
  pending: { text: 'Pending', color: 'text-text-subtle' },
  draft: { text: 'Draft', color: 'text-text-subtle' },
  scoring: { text: 'Scoring...', color: 'text-accent' },
  scored: { text: 'Scored', color: 'text-accent' },
  confirmed: { text: 'Confirmed', color: 'text-success' },
  in_development: { text: 'In Development', color: 'text-running' },
  completed: { text: 'Completed', color: 'text-success' },
  cancelled: { text: 'Cancelled', color: 'text-error' },
  approved: { text: 'Approved', color: 'text-success' },
  rejected: { text: 'Rejected', color: 'text-error' },
  needs_clarification: { text: 'Needs Clarification', color: 'text-warning' },
}

// ── Utility Functions ──

function formatDuration(ms: number | null): string {
  if (!ms) return '—'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function formatDate(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

/**
 * Format score for display
 * Scores are 0-100 internally, displayed as percentage
 */
function formatScore(score: number | null): string {
  if (score == null) return '—'
  // Score is already in 0-100 range
  return `${score.toFixed(0)}%`
}

// ── Clarification Form Component ──

interface ClarificationFormProps {
  clarification: ClarificationState
  onSubmit: (answers: Record<string, string>) => Promise<void>
  onSkip: () => Promise<void>
  threadId: string
}

/**
 * ClarificationForm - Interactive form for answering clarifying questions
 * Implements the CLARIFYING state interaction from the state machine design (Section 8.2)
 * Supports both high-priority and additional questions with priority-based rendering
 * Includes draft auto-save for offline support (Section 8.3)
 * 
 * Auto-transition condition (Section 7.1):
 * - TotalScore >= 80 AND PendingQuestionsCount == 0 → CONFIRMED
 * 
 * Features:
 * - Priority-based question rendering (high/medium/low)
 * - Progress tracking with visual indicator
 * - Draft auto-save with debounce
 * - Score visualization with threshold indicator
 * - Round counter (max 3 rounds per design)
 * - Assumption preview for conservative fallback
 */
function ClarificationForm({ clarification, onSubmit, onSkip, threadId }: ClarificationFormProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [draftSaved, setDraftSaved] = useState(false)

  // Initialize answers from existing state
  useEffect(() => {
    if (clarification.answers) {
      setAnswers(clarification.answers)
    }
    // Load local draft if available
    const localDraft = loadDraftLocal(threadId)
    if (localDraft && localDraft.dimensions) {
      // Merge with existing answers if any - convert dimensions to string answers
      const draftAnswers: Record<string, string> = {}
      for (const [key, value] of Object.entries(localDraft.dimensions)) {
        if (value != null) {
          draftAnswers[key] = String(value)
        }
      }
      setAnswers(prev => ({ ...prev, ...draftAnswers }))
    }
  }, [clarification.answers, threadId])

  // Auto-save draft on answer changes (debounced)
  useEffect(() => {
    const timer = setTimeout(() => {
      if (Object.keys(answers).length > 0) {
        saveDraftLocal({
          taskId: threadId,
          dimensions: answers as any,
          comment: '',
          savedAt: new Date().toISOString(),
          version: clarification.version ?? 1,
        })
        setDraftSaved(true)
        setTimeout(() => setDraftSaved(false), 2000)
      }
    }, 500)
    return () => clearTimeout(timer)
  }, [answers, threadId, clarification.version])

  function handleAnswerChange(questionId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(answers)
      // Clear local draft after successful submission
      clearDraftLocal(threadId)
    } catch (err: any) {
      setError(err.message || 'Failed to submit answers')
    } finally {
      setSubmitting(false)
    }
  }

  // Separate questions by importance for better UX
  // high: High priority (blocking)
  // medium: Medium priority
  // low: Low priority (optional)
  const getQuestionImportance = (q: ClarificationQuestion): string => {
    return q.importance || (
      q.priority != null ? (
        q.priority <= 2 ? 'high' : q.priority <= 3 ? 'medium' : 'low'
      ) : 'medium'
    )
  }

  const highPriorityQuestions = clarification.questions.filter(
    (q) => getQuestionImportance(q) === 'high' && !q.is_resolved
  )
  const otherQuestions = clarification.questions.filter(
    (q) => getQuestionImportance(q) !== 'high' && !q.is_resolved
  )
  const resolvedQuestions = clarification.questions.filter((q) => q.is_resolved)

  // Calculate pending questions count for auto-transition check
  const pendingQuestionsCount = clarification.questions.filter((q) => !q.is_resolved).length
  const answeredCount = Object.keys(answers).filter((k) => answers[k].trim()).length
  const totalQuestions = clarification.questions.length
  const progressPercent = totalQuestions > 0 ? (answeredCount / totalQuestions) * 100 : 0

  // Check if auto-transition condition is met (Section 7.1)
  const currentScore = clarification.score ?? clarification.total_score ?? clarification.clarity_score ?? null
  const canAutoTransition = currentScore != null && 
    currentScore >= SCORE_THRESHOLDS.SKIP && 
    pendingQuestionsCount === 0

  // Get current round info (max 3 rounds per design)
  const currentRound = clarification.current_round ?? 1
  const maxRounds = clarification.max_rounds ?? 3
  const isLastRound = currentRound >= maxRounds

  function renderQuestion(question: ClarificationQuestion) {
    // Support both new importance field and legacy priority field
    const importance = question.importance || (
      question.priority != null ? (
        question.priority <= 2 ? 'high' : question.priority <= 3 ? 'medium' : 'low'
      ) : 'medium'
    )
    
    // Support both new question field and legacy content field
    const questionText = question.question || question.content || ''

    const importanceColors: Record<string, string> = {
      high: 'bg-error/10 text-error border-error/20',
      medium: 'bg-warning/10 text-warning border-warning/20',
      low: 'bg-text-subtle/10 text-text-subtle border-text-subtle/20',
    }

    const importanceLabels: Record<string, string> = {
      high: 'HIGH',
      medium: 'MEDIUM',
      low: 'LOW',
    }

    return (
      <div key={question.q_id} className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${importanceColors[importance] || importanceColors.medium}`}>
            {importanceLabels[importance] || 'MEDIUM'}
          </span>
          <span className="text-xs text-text-subtle font-medium uppercase tracking-wider">
            {question.dimension}
          </span>
          {question.is_resolved && (
            <span className="text-[10px] text-success">✓ Resolved</span>
          )}
        </div>
        <p className="text-sm text-text">{questionText}</p>
        {question.options && question.options.length > 0 ? (
          // Form mode with options
          <div className="space-y-1">
            {question.options.map((opt) => (
              <label
                key={opt}
                className={`flex items-center gap-2 p-2 rounded-lg border cursor-pointer transition-colors ${
                  answers[question.q_id] === opt
                    ? 'border-accent bg-accent/10'
                    : 'border-border hover:border-text-subtle'
                }`}
              >
                <input
                  type="radio"
                  name={`q-${question.q_id}`}
                  value={opt}
                  checked={answers[question.q_id] === opt}
                  onChange={(e) => handleAnswerChange(question.q_id, e.target.value)}
                  className="accent-accent"
                />
                <span className="text-sm text-text">{opt}</span>
              </label>
            ))}
          </div>
        ) : (
          // Free text mode
          <input
            type="text"
            value={answers[question.q_id] || ''}
            onChange={(e) => handleAnswerChange(question.q_id, e.target.value)}
            placeholder="Your answer..."
            className="w-full bg-bg-sub border border-border rounded-lg p-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
          />
        )}
      </div>
    )
  }

  return (
    <div className="bg-bg-sub border border-accent/30 rounded-xl p-5 space-y-4">
      {/* Header with round info */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-accent">
            Clarification Required
            {currentRound <= maxRounds && (
              <span className="ml-2 text-xs text-text-subtle font-normal">
                (Round {currentRound}/{maxRounds})
              </span>
            )}
          </h3>
          <p className="text-xs text-text-muted mt-0.5">
            {answeredCount}/{totalQuestions} answered
            {currentScore != null && ` · Clarity Score: ${formatScore(currentScore)}`}
            {draftSaved && ' · Draft saved'}
          </p>
        </div>
        <button
          onClick={onSkip}
          className="text-xs text-text-subtle hover:text-text underline transition-colors"
          title="Use conservative assumptions instead of answering questions"
        >
          Skip & Use Assumptions
        </button>
      </div>

      {/* Score threshold indicator */}
      {currentScore != null && (
        <div className="space-y-1">
          <div className="flex justify-between text-[10px] text-text-muted">
            <span>Clarity Score</span>
            <span className={currentScore >= SCORE_THRESHOLDS.SKIP ? 'text-success' : 'text-warning'}>
              {currentScore.toFixed(0)}% {currentScore >= SCORE_THRESHOLDS.SKIP ? '✓' : `(need ${SCORE_THRESHOLDS.SKIP}%)`}
            </span>
          </div>
          <div className="w-full bg-bg border border-border rounded-full h-1.5">
            <div
              className={`h-1.5 rounded-full transition-all duration-300 ${
                currentScore >= SCORE_THRESHOLDS.SKIP ? 'bg-success' :
                currentScore >= SCORE_THRESHOLDS.CONSERVATIVE_MIN ? 'bg-warning' : 'bg-error'
              }`}
              style={{ width: `${Math.min(currentScore, 100)}%` }}
            />
          </div>
        </div>
      )}

      {/* Auto-transition indicator */}
      {canAutoTransition && (
        <div className="bg-success/10 border border-success/30 rounded-lg p-3 flex items-center gap-2">
          <span className="text-success text-lg">✓</span>
          <div>
            <p className="text-xs font-medium text-success">Auto-Transition Ready</p>
            <p className="text-[10px] text-text-muted">Score ≥ {SCORE_THRESHOLDS.SKIP} and all questions resolved → CONFIRMED</p>
          </div>
        </div>
      )}

      {/* Last round warning */}
      {isLastRound && !canAutoTransition && (
        <div className="bg-warning/10 border border-warning/30 rounded-lg p-3 flex items-center gap-2">
          <span className="text-warning text-lg">⚠</span>
          <div>
            <p className="text-xs font-medium text-warning">Final Round</p>
            <p className="text-[10px] text-text-muted">This is the last clarification round. Unanswered questions will use conservative assumptions.</p>
          </div>
        </div>
      )}

      {/* Progress Bar */}
      <div className="w-full bg-bg border border-border rounded-full h-1.5">
        <div
          className="bg-accent h-1.5 rounded-full transition-all duration-300"
          style={{ width: `${progressPercent}%` }}
        />
      </div>

      {/* Resolved Questions Summary */}
      {resolvedQuestions.length > 0 && (
        <details className="text-xs">
          <summary className="text-text-subtle cursor-pointer hover:text-text transition-colors">
            View {resolvedQuestions.length} resolved question{resolvedQuestions.length !== 1 ? 's' : ''}
          </summary>
          <ul className="mt-2 space-y-1 pl-4">
            {resolvedQuestions.map((q) => (
              <li key={q.q_id} className="text-text-muted flex items-start gap-1.5">
                <span className="text-success">✓</span>
                <span>{q.content || q.question}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Assumptions Preview */}
      {clarification.assumptions.length > 0 && (
        <details className="text-xs">
          <summary className="text-text-subtle cursor-pointer hover:text-text transition-colors">
            View {clarification.assumptions.length} assumption{clarification.assumptions.length !== 1 ? 's' : ''} that will be used
          </summary>
          <ul className="mt-2 space-y-1 pl-4">
            {clarification.assumptions.map((a) => (
              <li key={a.a_id} className="text-text-muted flex items-start gap-1.5">
                <span className={`text-[10px] px-1 rounded ${
                  a.risk_level === 'high' ? 'bg-error/10 text-error' :
                  a.risk_level === 'medium' ? 'bg-warning/10 text-warning' :
                  'bg-text-subtle/10 text-text-subtle'
                }`}>
                  {a.risk_level}
                </span>
                <span>{a.content || a.assumption}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4 pt-2 border-t border-border">
        {highPriorityQuestions.length > 0 && (
          <div className="space-y-4">
            <div className="text-xs font-medium text-error uppercase tracking-wider">High Priority (Blocking)</div>
            {highPriorityQuestions.map(renderQuestion)}
          </div>
        )}

        {otherQuestions.length > 0 && (
          <div className="space-y-4">
            <div className="text-xs font-medium text-text-subtle uppercase tracking-wider">Additional Questions</div>
            {otherQuestions.map(renderQuestion)}
          </div>
        )}

        {error && (
          <div className="text-error text-xs bg-error/10 border border-error/20 rounded-lg p-2" role="alert">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={submitting || answeredCount === 0}
            className="flex-1 py-2 px-4 rounded-lg bg-accent text-bg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'Submitting...' : 'Submit Answers'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ── Score Display Component ──

interface ScoreDisplayProps {
  scoreRecord: ScoreRecord
}

function ScoreDisplay({ scoreRecord }: ScoreDisplayProps) {
  const dimensionColors: Record<string, string> = {
    functional_scope: 'text-blue-400',
    tech_constraints: 'text-green-400',
    quality_reqs: 'text-purple-400',
    target_users: 'text-yellow-400',
    timeline: 'text-red-400',
    integration: 'text-orange-400',
    success_criteria: 'text-cyan-400',
    budget: 'text-pink-400',
    context: 'text-indigo-400',
    // Legacy dimension names for backward compatibility
    Completeness: 'text-blue-400',
    Feasibility: 'text-green-400',
    Consistency: 'text-purple-400',
    Testability: 'text-yellow-400',
    Security: 'text-red-400',
    Performance: 'text-orange-400',
    Maintainability: 'text-cyan-400',
    Scalability: 'text-pink-400',
    Usability: 'text-indigo-400',
    completeness: 'text-blue-400',
    feasibility: 'text-green-400',
    consistency: 'text-purple-400',
    testability: 'text-yellow-400',
    priority: 'text-red-400',
    risk: 'text-orange-400',
    dependency: 'text-cyan-400',
    acceptanceCriteria: 'text-pink-400',
    businessValue: 'text-indigo-400',
  }

  // Determine if score meets threshold (80 = skip mode)
  const meetsThreshold = scoreRecord.total_score >= SCORE_THRESHOLD

  return (
    <div className="bg-bg-sub border border-border rounded-xl p-5 space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-text">Quality Score</h3>
        <div className="flex items-center gap-2">
          <span className={`text-2xl font-bold ${meetsThreshold ? 'text-success' : 'text-warning'}`}>
            {scoreRecord.total_score.toFixed(1)}%
          </span>
          <span className={`text-[10px] px-1.5 py-0.5 rounded ${
            meetsThreshold ? 'bg-success/10 text-success' : 'bg-warning/10 text-warning'
          }`}>
            {meetsThreshold ? '≥ Threshold' : '< Threshold'}
          </span>
        </div>
      </div>

      {/* Threshold indicator */}
      <div className="w-full bg-bg border border-border rounded-full h-2">
        <div
          className={`h-2 rounded-full transition-all duration-300 ${meetsThreshold ? 'bg-success' : 'bg-warning'}`}
          style={{ width: `${Math.min(scoreRecord.total_score, 100)}%` }}
        />
      </div>
      <div className="flex justify-between text-[10px] text-text-muted">
        <span>0%</span>
        <span>Threshold: {SCORE_THRESHOLD}%</span>
        <span>100%</span>
      </div>

      {/* Dimension Scores */}
      <div className="grid grid-cols-3 gap-2">
        {Object.entries(scoreRecord.dimensions).map(([dim, score]) => (
          <div key={dim} className="bg-bg border border-border rounded-lg p-2">
            <div className={`text-[10px] font-medium ${dimensionColors[dim] || 'text-text-subtle'}`}>
              {dim}
            </div>
            <div className="text-sm font-mono mt-0.5">{score.toFixed(0)}</div>
          </div>
        ))}
      </div>

      {/* Suggestions */}
      {scoreRecord.suggestions.length > 0 && (
        <div>
          <div className="text-xs font-medium text-text-subtle uppercase tracking-wider mb-2">Suggestions</div>
          <ul className="space-y-1">
            {scoreRecord.suggestions.map((s, i) => (
              <li key={i} className="text-xs text-text-muted flex items-start gap-1.5">
                <span className="text-accent mt-0.5">•</span>
                <span>{s}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Audit Hash */}
      <div className="text-[10px] text-text-muted font-mono break-all">
        Audit: {scoreRecord.audit_hash}
      </div>
    </div>
  )
}

// ── State Transition Controls ──

interface StateTransitionControlsProps {
  currentStatus: TaskStatus
  score: number | null
  pendingQuestions: number
  onTransition: (target: ClarificationStatus) => Promise<void>
}

/**
 * StateTransitionControls - Controls for state machine transitions
 * Implements the state machine design from Section 8.1
 * 
 * Allowed transitions:
 * - SCORED → APPROVED (approve requirements)
 * - SCORED → REJECTED (reject requirements)
 * - CLARIFYING → CONFIRMED (manual confirm or auto if score≥80 && pending=0)
 * - CONFIRMED → IN_DEVELOPMENT (handoff to development)
 * - IN_DEVELOPMENT → COMPLETED (archive)
 * - Any → CANCELLED (cancel/timeout)
 */
function StateTransitionControls({ currentStatus, score, pendingQuestions, onTransition }: StateTransitionControlsProps) {
  const [confirming, setConfirming] = useState<ClarificationStatus | null>(null)

  // Auto-transition check (Section 7.1)
  const canAutoTransition = score != null && score >= 80 && pendingQuestions === 0

  // SCORED state controls - approve or reject
  if (currentStatus === 'scored') {
    return (
      <div className="flex gap-2">
        {confirming === 'approved' ? (
          <div className="flex gap-2 items-center">
            <span className="text-xs text-text-subtle">Confirm approval?</span>
            <button
              onClick={() => onTransition('approved')}
              className="px-3 py-1.5 rounded-lg bg-success text-bg text-xs font-medium hover:bg-success/90 transition-colors"
            >
              Yes, Approve
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-subtle hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : confirming === 'rejected' ? (
          <div className="flex gap-2 items-center">
            <span className="text-xs text-text-subtle">Confirm rejection?</span>
            <button
              onClick={() => onTransition('rejected')}
              className="px-3 py-1.5 rounded-lg bg-error text-bg text-xs font-medium hover:bg-error/90 transition-colors"
            >
              Yes, Reject
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-subtle hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <>
            <button
              onClick={() => setConfirming('approved')}
              className="px-4 py-2 rounded-lg bg-success/10 border border-success/30 text-success text-sm font-medium hover:bg-success/20 transition-colors"
            >
              ✓ Approve
            </button>
            <button
              onClick={() => setConfirming('rejected')}
              className="px-4 py-2 rounded-lg bg-error/10 border border-error/30 text-error text-sm font-medium hover:bg-error/20 transition-colors"
            >
              ✗ Reject
            </button>
          </>
        )}
      </div>
    )
  }

  // CLARIFYING state controls
  if (currentStatus === 'clarifying' || currentStatus === 'needs_clarification') {
    return (
      <div className="flex gap-2 items-center">
        {canAutoTransition ? (
          <div className="flex items-center gap-2">
            <span className="text-xs text-success font-medium">Auto-Ready</span>
            <button
              onClick={() => onTransition('confirmed')}
              className="px-3 py-1.5 rounded-lg bg-success text-bg text-xs font-medium hover:bg-success/90 transition-colors"
            >
              Confirm & Proceed
            </button>
          </div>
        ) : (
          <span className="text-xs text-text-muted">
            {score != null ? `Score: ${score}%` : 'Awaiting score'}
            {pendingQuestions > 0 && ` · ${pendingQuestions} pending`}
          </span>
        )}
      </div>
    )
  }

  // CONFIRMED state controls
  if (currentStatus === 'confirmed' || currentStatus === 'approved') {
    return (
      <div className="flex gap-2">
        {confirming === 'in_development' ? (
          <div className="flex gap-2 items-center">
            <span className="text-xs text-text-subtle">Handoff to development?</span>
            <button
              onClick={() => onTransition('in_development')}
              className="px-3 py-1.5 rounded-lg bg-running text-bg text-xs font-medium hover:bg-running/90 transition-colors"
            >
              Yes, Handoff
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-subtle hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming('in_development')}
            className="px-4 py-2 rounded-lg bg-running/10 border border-running/30 text-running text-sm font-medium hover:bg-running/20 transition-colors"
          >
            → Handoff to Development
          </button>
        )}
      </div>
    )
  }

  // IN_DEVELOPMENT state controls
  if (currentStatus === 'in_development') {
    return (
      <div className="flex gap-2">
        {confirming === 'completed' ? (
          <div className="flex gap-2 items-center">
            <span className="text-xs text-text-subtle">Archive as completed?</span>
            <button
              onClick={() => onTransition('completed')}
              className="px-3 py-1.5 rounded-lg bg-success text-bg text-xs font-medium hover:bg-success/90 transition-colors"
            >
              Yes, Archive
            </button>
            <button
              onClick={() => setConfirming(null)}
              className="px-3 py-1.5 rounded-lg border border-border text-xs text-text-subtle hover:text-text transition-colors"
            >
              Cancel
            </button>
          </div>
        ) : (
          <button
            onClick={() => setConfirming('completed')}
            className="px-4 py-2 rounded-lg bg-success/10 border border-success/30 text-success text-sm font-medium hover:bg-success/20 transition-colors"
          >
            ✓ Archive
          </button>
        )}
      </div>
    )
  }

  // Default: no controls
  return null
}

// ── Main Execution Page ──

export default function ExecutionPage() {
  const { threadId: rawThreadId } = useParams<{ threadId: string }>()
  const threadId = rawThreadId ?? ''
  const [detail, setDetail] = useState<ExecutionDetail | null>(null)
  const [dag, setDag] = useState<DAGResponse | null>(null)
  const [clarification, setClarification] = useState<ClarificationState | null>(null)
  const [scoreRecord, setScoreRecord] = useState<ScoreRecord | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'graph'>('timeline')

  const load = useCallback(async () => {
    if (!threadId) return
    try {
      setLoading(true)
      setError(null)
      const [detailData, dagData] = await Promise.all([
        fetchExecution(threadId),
        fetchDAG(threadId),
      ])
      setDetail(detailData)
      setDag(dagData)

      // Load clarification state if in clarifying state
      if (detailData.status === 'clarifying' || detailData.status === 'needs_clarification') {
        try {
          const clarData = await fetchClarificationState(threadId)
          setClarification(clarData)
        } catch (e: any) {
          console.warn('Failed to load clarification state:', e.message)
        }
      }
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [threadId])

  async function handleClarificationSubmit(answers: Record<string, string>) {
    if (!threadId) return
    await submitClarificationAnswers({ thread_id: threadId, answers })
    // Reload to get updated status
    await load()
  }

  async function handleClarificationSkip() {
    if (!threadId) return
    await skipClarification(threadId)
    // Reload to get updated status
    await load()
  }

  async function handleStateTransition(target: ClarificationStatus) {
    if (!threadId) return
    await transitionState({ thread_id: threadId, target_status: target })
    await load()
  }

  async function handleCalculateScore() {
    if (!threadId) return
    const result = await calculateScore({ thread_id: threadId })
    setScoreRecord(result)
    await load()
  }

  useEffect(() => { load() }, [load])

  // Polling for non-terminal states
  useEffect(() => {
    const timer = setInterval(() => {
      if (!detail) return
      // Stop polling if terminal state or waiting for clarification
      if (['success', 'failed', 'interrupted'].includes(detail.status)) return
      if (detail.status === 'clarifying') return
      load()
    }, 2000)
    return () => clearInterval(timer)
  }, [threadId, detail, load])

  if (loading && !detail) {
    return <div className="text-text-subtle text-sm py-16 text-center">Loading…</div>
  }

  if (error && !detail) {
    return (
      <div className="text-error text-sm py-16 text-center">
        <p>{error}</p>
        <Link to="/" className="text-accent text-xs mt-2 inline-block hover:underline">← Back</Link>
      </div>
    )
  }

  if (!detail) return null

  const st = statusLabel[detail.status] || { text: detail.status, color: 'text-text-subtle' }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <Link to="/" className="text-text-subtle text-xs hover:text-text transition-colors mb-3 inline-block">
          ← Back to Dashboard
        </Link>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold tracking-tight font-mono">{detail.thread_id}</h1>
            <span className={`text-sm font-medium ${st.color}`}>{st.text}</span>
          </div>
          {/* State transition controls */}
          <StateTransitionControls
            currentStatus={detail.status as TaskStatus}
            score={clarification?.score ?? scoreRecord?.total_score ?? null}
            pendingQuestions={clarification?.questions.filter(q => !q.is_resolved).length ?? 0}
            onTransition={handleStateTransition}
          />
        </div>
      </div>

      {/* Scoring State Indicator */}
      {detail.status === 'scoring' && (
        <div className="bg-bg-sub border border-accent/30 rounded-xl p-5 flex items-center gap-3">
          <div className="animate-spin text-accent text-xl">⟳</div>
          <div>
            <h3 className="text-sm font-semibold text-accent">Evaluating Requirement...</h3>
            <p className="text-xs text-text-muted mt-0.5">ClarifierAgent is analyzing your requirement across 9 dimensions</p>
          </div>
        </div>
      )}

      {/* Clarification Form (if in clarifying state) */}
      {(detail.status === 'clarifying' || detail.status === 'needs_clarification') && clarification && (
        <ClarificationForm
          clarification={clarification}
          onSubmit={handleClarificationSubmit}
          onSkip={handleClarificationSkip}
          threadId={threadId}
        />
      )}

      {/* Score Display (if scored or confirmed) */}
      {(detail.status === 'scored' || detail.status === 'confirmed' || detail.status === 'approved') && scoreRecord && (
        <ScoreDisplay scoreRecord={scoreRecord} />
      )}

      {/* Calculate Score Button (if clarifying completed but not scored) */}
      {clarification && clarification.status === 'answered' && !scoreRecord && (
        <div className="flex justify-center">
          <button
            onClick={handleCalculateScore}
            className="px-6 py-2 rounded-lg bg-accent text-bg text-sm font-medium hover:bg-accent/90 transition-colors"
          >
            Calculate Quality Score
          </button>
        </div>
      )}

      {/* Metadata */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          ['Started', formatDate(detail.started_at)],
          ['Duration', formatDuration(detail.duration_ms)],
          ['Cost', detail.total_cost != null ? `$${detail.total_cost.toFixed(2)}` : '—'],
          ['Tokens', detail.total_tokens?.toLocaleString() ?? '—'],
        ].map(([label, value]) => (
          <div key={label} className="bg-bg-sub border border-border rounded-lg p-3">
            <div className="text-text-subtle text-[11px] font-medium uppercase tracking-wider">{label}</div>
            <div className="text-sm font-mono mt-0.5">{value}</div>
          </div>
        ))}
      </div>

      {/* Task */}
      {detail.task_input && (
        <div className="bg-bg-sub border border-border rounded-lg p-4">
          <div className="text-text-subtle text-[11px] font-medium uppercase tracking-wider mb-2">Task</div>
          <div className="text-sm text-text-muted leading-relaxed">{detail.task_input}</div>
        </div>
      )}

      {/* Tabs */}
      <div className="flex gap-4 border-b border-border">
        {(['timeline', 'graph'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`pb-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'text-accent border-b-2 border-accent'
                : 'text-text-subtle hover:text-text'
            }`}
          >
            {tab === 'timeline' ? 'Timeline' : 'Graph'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {activeTab === 'timeline' ? (
        <div>
          <h2 className="text-sm font-medium mb-4 text-text-subtle uppercase tracking-wider">Execution Timeline</h2>
          <NodeTimeline nodes={detail.nodes} />
        </div>
      ) : (
        <div>
          <h2 className="text-sm font-medium mb-4 text-text-subtle uppercase tracking-wider">Workflow DAG</h2>
          {dag ? (
            <DAGView dag={dag} />
          ) : (
            <div className="text-text-subtle text-sm py-8 text-center">Loading graph…</div>
          )}
        </div>
      )}
    </div>
  )
}
