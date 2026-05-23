import { useEffect, useState } from 'react'
import { OverviewStats, ExecutionItem, ClarificationRecommendation } from '../types'
import { fetchOverview, fetchExecutions, createExecution } from '../lib/api'
import StatsCards from '../components/StatsCards'
import ExecutionTable from '../components/ExecutionTable'

type ClarificationMode = 'auto' | 'conservative' | 'interactive'

interface CreateTaskModalProps {
  isOpen: boolean
  onClose: () => void
  onSubmit: (task: string, mode: ClarificationMode) => Promise<void>
}

function CreateTaskModal({ isOpen, onClose, onSubmit }: CreateTaskModalProps) {
  const [task, setTask] = useState('')
  const [mode, setMode] = useState<ClarificationMode>('auto')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (!isOpen) return null

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (!task.trim()) return

    setSubmitting(true)
    setError(null)
    try {
      await onSubmit(task.trim(), mode)
      setTask('')
      setMode('auto')
      onClose()
    } catch (err: any) {
      setError(err.message || 'Failed to create execution')
    } finally {
      setSubmitting(false)
    }
  }

  const modeDescriptions: Record<ClarificationMode, { title: string; desc: string; icon: string }> = {
    auto: {
      title: 'Auto',
      desc: 'System decides based on task clarity',
      icon: '🤖',
    },
    conservative: {
      title: 'Conservative',
      desc: 'Fill assumptions for ambiguous tasks',
      icon: '🛡️',
    },
    interactive: {
      title: 'Interactive',
      desc: 'Answer clarifying questions',
      icon: '💬',
    },
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-bg border border-border rounded-xl shadow-2xl w-full max-w-lg mx-4">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-border">
          <h2 className="text-base font-semibold">Create New Task</h2>
          <button
            onClick={onClose}
            className="text-text-subtle hover:text-text transition-colors text-lg leading-none"
          >
            ×
          </button>
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} className="p-4 space-y-4">
          {/* Task Input */}
          <div>
            <label className="block text-xs font-medium text-text-subtle uppercase tracking-wider mb-1.5">
              Task Description
            </label>
            <textarea
              value={task}
              onChange={(e) => setTask(e.target.value)}
              placeholder="Describe what you want to accomplish..."
              className="w-full h-28 bg-bg-sub border border-border rounded-lg p-3 text-sm text-text placeholder:text-text-muted resize-none focus:outline-none focus:border-accent transition-colors"
              required
            />
          </div>

          {/* Mode Selection */}
          <div>
            <label className="block text-xs font-medium text-text-subtle uppercase tracking-wider mb-2">
              Clarification Mode
            </label>
            <div className="grid grid-cols-3 gap-2">
              {(Object.keys(modeDescriptions) as ClarificationMode[]).map((m) => {
                const info = modeDescriptions[m]
                const selected = mode === m
                return (
                  <button
                    key={m}
                    type="button"
                    onClick={() => setMode(m)}
                    className={`p-3 rounded-lg border text-left transition-all ${
                      selected
                        ? 'border-accent bg-accent/10'
                        : 'border-border hover:border-text-subtle'
                    }`}
                  >
                    <div className="text-lg mb-1">{info.icon}</div>
                    <div className={`text-xs font-medium ${selected ? 'text-accent' : 'text-text'}`}>
                      {info.title}
                    </div>
                    <div className="text-[10px] text-text-muted mt-0.5 leading-tight">
                      {info.desc}
                    </div>
                  </button>
                )
              })}
            </div>
          </div>

          {/* Error */}
          {error && (
            <div className="text-error text-xs bg-error/10 border border-error/20 rounded-lg p-2">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex gap-2 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="flex-1 py-2 px-4 rounded-lg border border-border text-sm text-text-subtle hover:text-text hover:border-text-subtle transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !task.trim()}
              className="flex-1 py-2 px-4 rounded-lg bg-accent text-bg text-sm font-medium hover:bg-accent/90 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Creating...' : 'Create Task'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function HomePage() {
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [items, setItems] = useState<ExecutionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [modalOpen, setModalOpen] = useState(false)

  async function load() {
    try {
      const [ov, list] = await Promise.all([fetchOverview(), fetchExecutions()])
      setStats(ov)
      setItems(list.items)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  async function handleCreateTask(task: string, mode: ClarificationMode) {
    const result = await createExecution({
      task,
      clarification_mode: mode,
    })
    // Reload to show new execution
    await load()
    // Could navigate to execution page here
    return result
  }

  useEffect(() => { load() }, [])
  useEffect(() => {
    const timer = setInterval(load, 3000)
    return () => clearInterval(timer)
  }, [])

  if (loading) {
    return <div className="text-text-subtle text-sm py-16 text-center">Loading…</div>
  }

  if (error) {
    return (
      <div className="text-error text-sm py-16 text-center">
        <p>{error}</p>
        <button onClick={load} className="text-accent text-xs mt-2 hover:underline">Retry</button>
      </div>
    )
  }

  const defaultStats: OverviewStats = { total_executions: 0, running: 0, success: 0, failed: 0, interrupted: 0 }

  return (
    <div className="space-y-6">
      {/* Header with Create Button */}
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Dashboard</h1>
        <button
          onClick={() => setModalOpen(true)}
          className="px-4 py-2 rounded-lg bg-accent text-bg text-sm font-medium hover:bg-accent/90 transition-colors"
        >
          + New Task
        </button>
      </div>

      <StatsCards stats={stats ?? defaultStats} />
      <div>
        <h2 className="text-sm font-medium mb-4 text-text-subtle uppercase tracking-wider">Executions</h2>
        <ExecutionTable items={items} />
      </div>

      {/* Create Task Modal */}
      <CreateTaskModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSubmit={handleCreateTask}
      />
    </div>
  )
}
