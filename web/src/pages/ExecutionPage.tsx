import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ExecutionDetail } from '../types'
import { fetchExecution } from '../lib/api'
import NodeTimeline from '../components/NodeTimeline'

const statusLabel: Record<string, { text: string; color: string }> = {
  success: { text: 'Completed', color: 'text-success' },
  running: { text: 'Running', color: 'text-running' },
  failed: { text: 'Failed', color: 'text-error' },
  interrupted: { text: 'Interrupted', color: 'text-warning' },
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

export default function ExecutionPage() {
  const { threadId } = useParams<{ threadId: string }>()!
  const [detail, setDetail] = useState<ExecutionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    if (!threadId) return
    try {
      setLoading(true)
      setError(null)
      const data = await fetchExecution(threadId)
      setDetail(data)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [threadId])
  useEffect(() => {
    const timer = setInterval(() => {
      if (!detail || detail.status === 'success' || detail.status === 'failed' || detail.status === 'interrupted') return
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

      {/* Timeline */}
      <div>
        <h2 className="text-sm font-medium mb-4 text-text-subtle uppercase tracking-wider">Execution Timeline</h2>
        <NodeTimeline nodes={detail.nodes} />
      </div>
    </div>
  )
}
