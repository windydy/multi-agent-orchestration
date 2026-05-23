import { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { ExecutionDetail, DAGResponse, ClarificationState, ClarificationQuestion } from '../types'
import { fetchExecution, fetchDAG, fetchClarificationState, submitClarificationAnswers, skipClarification } from '../lib/api'
import NodeTimeline from '../components/NodeTimeline'
import DAGView from '../components/DAGView'

const statusLabel: Record<string, { text: string; color: string }> = {
  success: { text: 'Completed', color: 'text-success' },
  running: { text: 'Running', color: 'text-running' },
  failed: { text: 'Failed', color: 'text-error' },
  interrupted: { text: 'Interrupted', color: 'text-warning' },
  clarifying: { text: 'Clarifying', color: 'text-accent' },
  paused: { text: 'Paused', color: 'text-warning' },
}

function formatDuration(ms: number | null): string {
  if (!ms) return '—'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString()
}

// ── Clarification Form Component ──

interface ClarificationFormProps {
  clarification: ClarificationState
  onSubmit: (answers: Record<string, string>) => Promise<void>
  onSkip: () => Promise<void>
}

function ClarificationForm({ clarification, onSubmit, onSkip }: ClarificationFormProps) {
  const [answers, setAnswers] = useState<Record<string, string>>({})
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Initialize answers from existing state
  useEffect(() => {
    if (clarification.answers) {
      setAnswers(clarification.answers)
    }
  }, [clarification.answers])

  function handleAnswerChange(questionId: string, value: string) {
    setAnswers((prev) => ({ ...prev, [questionId]: value }))
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(answers)
    } catch (err: any) {
      setError(err.message || 'Failed to submit answers')
    } finally {
      setSubmitting(false)
    }
  }

  const highPriorityQuestions = clarification.questions.filter((q) => q.priority === 'high')
  const otherQuestions = clarification.questions.filter((q) => q.priority !== 'high')

  function renderQuestion(question: ClarificationQuestion) {
    const priorityColors: Record<string, string> = {
      high: 'bg-error/10 text-error border-error/20',
      medium: 'bg-warning/10 text-warning border-warning/20',
      low: 'bg-text-subtle/10 text-text-subtle border-text-subtle/20',
    }

    return (
      <div key={question.id} className="space-y-2">
        <div className="flex items-center gap-2">
          <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${priorityColors[question.priority]}`}>
            {question.priority.toUpperCase()}
          </span>
          <span className="text-xs text-text-subtle font-medium uppercase tracking-wider">
            {question.dimension}
          </span>
        </div>
        <p className="text-sm text-text">{question.question}</p>
        {question.context && (
          <p className="text-xs text-text-muted italic">{question.context}</p>
        )}
        <input
          type="text"
          value={answers[question.id] || ''}
          onChange={(e) => handleAnswerChange(question.id, e.target.value)}
          placeholder="Your answer..."
          className="w-full bg-bg-sub border border-border rounded-lg p-2.5 text-sm text-text placeholder:text-text-muted focus:outline-none focus:border-accent transition-colors"
        />
      </div>
    )
  }

  return (
    <div className="bg-bg-sub border border-accent/30 rounded-xl p-5 space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold text-accent">Clarification Required</h3>
          <p className="text-xs text-text-muted mt-0.5">
            {clarification.questions.length} question{clarification.questions.length !== 1 ? 's' : ''} to answer
            {clarification.score != null && ` (Clarity Score: ${(clarification.score * 100).toFixed(0)}%)`}
          </p>
        </div>
        <button
          onClick={onSkip}
          className="text-xs text-text-subtle hover:text-text underline transition-colors"
        >
          Skip & Use Assumptions
        </button>
      </div>

      {/* Assumptions Preview */}
      {clarification.assumptions.length > 0 && (
        <details className="text-xs">
          <summary className="text-text-subtle cursor-pointer hover:text-text transition-colors">
            View {clarification.assumptions.length} assumption{clarification.assumptions.length !== 1 ? 's' : ''} that will be used
          </summary>
          <ul className="mt-2 space-y-1 pl-4">
            {clarification.assumptions.map((a) => (
              <li key={a.id} className="text-text-muted flex items-start gap-1.5">
                <span className={`text-[10px] px-1 rounded ${
                  a.risk === 'high' ? 'bg-error/10 text-error' :
                  a.risk === 'medium' ? 'bg-warning/10 text-warning' :
                  'bg-text-subtle/10 text-text-subtle'
                }`}>
                  {a.risk}
                </span>
                <span>{a.assumption}</span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {/* Form */}
      <form onSubmit={handleSubmit} className="space-y-4 pt-2 border-t border-border">
        {highPriorityQuestions.length > 0 && (
          <div className="space-y-4">
            <div className="text-xs font-medium text-error uppercase tracking-wider">High Priority</div>
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
          <div className="text-error text-xs bg-error/10 border border-error/20 rounded-lg p-2">
            {error}
          </div>
        )}

        <div className="flex gap-2 pt-2">
          <button
            type="submit"
            disabled={submitting}
            className="flex-1 py-2 px-4 rounded-lg bg-accent text-bg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            {submitting ? 'Submitting...' : 'Submit Answers'}
          </button>
        </div>
      </form>
    </div>
  )
}

// ── Main Execution Page ──

export default function ExecutionPage() {
  const { threadId } = useParams<{ threadId: string }>()!
  const navigate = useNavigate()
  const [detail, setDetail] = useState<ExecutionDetail | null>(null)
  const [dag, setDag] = useState<DAGResponse | null>(null)
  const [clarification, setClarification] = useState<ClarificationState | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'timeline' | 'graph'>('timeline')

  async function load() {
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

      // Load clarification state if status is clarifying
      if (detailData.status === 'clarifying') {
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
  }

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

  useEffect(() => { load() }, [threadId])
  useEffect(() => {
    const timer = setInterval(() => {
      if (!detail) return
      // Stop polling if terminal state or waiting for clarification
      if (['success', 'failed', 'interrupted'].includes(detail.status)) return
      if (detail.status === 'clarifying') return
      load()
    }, 2000)
    return () => clearInterval(timer)
  }, [threadId, detail])

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
        </div>
      </div>

      {/* Clarification Form (if in clarifying state) */}
      {detail.status === 'clarifying' && clarification && (
        <ClarificationForm
          clarification={clarification}
          onSubmit={handleClarificationSubmit}
          onSkip={handleClarificationSkip}
        />
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
