import { useState } from 'react'
import { VerifierResponse } from '../types'

interface VerifierTableProps {
  rules: VerifierResponse[]
  onCreate: (rule: { name: string; condition: string; threshold: number; action: string; severity: string }) => void
  onUpdate: (id: string, updates: Partial<VerifierResponse>) => void
  onDelete: (id: string) => void
}

const severityColors: Record<string, string> = {
  low: 'text-text-subtle',
  medium: 'text-warning',
  high: 'text-error',
}

export default function VerifierTable({ rules, onCreate, onUpdate, onDelete }: VerifierTableProps) {
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    name: '',
    condition: 'token_limit',
    threshold: 10000,
    action: 'warn',
    severity: 'medium' as const,
  })

  function handleCreate() {
    if (!form.name.trim()) return
    onCreate(form)
    setShowForm(false)
    setForm({ name: '', condition: 'token_limit', threshold: 10000, action: 'warn', severity: 'medium' })
  }

  return (
    <div>
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider">Verifier Rules</h3>
        <button
          onClick={() => setShowForm(!showForm)}
          className="px-3 py-1 text-xs bg-accent text-bg rounded hover:bg-accent/90 transition-colors"
        >
          {showForm ? 'Cancel' : '+ Add Rule'}
        </button>
      </div>

      {showForm && (
        <div className="bg-bg-sub border border-border rounded-lg p-4 mb-4 space-y-2">
          <div className="grid grid-cols-2 gap-2">
            <div>
              <label className="text-[11px] text-text-subtle">Name</label>
              <input
                value={form.name}
                onChange={(e) => setForm({ ...form, name: e.target.value })}
                className="w-full bg-bg border border-border rounded px-2 py-1 text-xs font-mono text-text focus:border-accent focus:outline-none"
                placeholder="Rule name"
              />
            </div>
            <div>
              <label className="text-[11px] text-text-subtle">Condition</label>
              <select
                value={form.condition}
                onChange={(e) => setForm({ ...form, condition: e.target.value })}
                className="w-full bg-bg border border-border rounded px-2 py-1 text-xs font-mono text-text focus:border-accent focus:outline-none"
              >
                <option value="token_limit">Token Limit</option>
                <option value="cost_threshold">Cost Threshold</option>
                <option value="node_timeout">Node Timeout</option>
              </select>
            </div>
            <div>
              <label className="text-[11px] text-text-subtle">Threshold</label>
              <input
                type="number"
                value={form.threshold}
                onChange={(e) => setForm({ ...form, threshold: parseFloat(e.target.value) })}
                className="w-full bg-bg border border-border rounded px-2 py-1 text-xs font-mono text-text focus:border-accent focus:outline-none"
              />
            </div>
            <div>
              <label className="text-[11px] text-text-subtle">Action</label>
              <select
                value={form.action}
                onChange={(e) => setForm({ ...form, action: e.target.value })}
                className="w-full bg-bg border border-border rounded px-2 py-1 text-xs font-mono text-text focus:border-accent focus:outline-none"
              >
                <option value="warn">Warn</option>
                <option value="fail">Fail</option>
                <option value="retry">Retry</option>
              </select>
            </div>
          </div>
          <button
            onClick={handleCreate}
            disabled={!form.name.trim()}
            className="px-3 py-1 text-xs bg-accent text-bg rounded hover:bg-accent/90 disabled:opacity-40 transition-colors"
          >
            Create
          </button>
        </div>
      )}

      {rules.length === 0 && !showForm ? (
        <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">
          No verifier rules configured
        </div>
      ) : (
        <div className="bg-bg-sub border border-border rounded-lg overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-border text-text-subtle uppercase tracking-wider">
                <th className="text-left p-3">Name</th>
                <th className="text-left p-3">Condition</th>
                <th className="text-left p-3">Threshold</th>
                <th className="text-left p-3">Action</th>
                <th className="text-left p-3">Severity</th>
                <th className="text-left p-3">Status</th>
                <th className="p-3"></th>
              </tr>
            </thead>
            <tbody>
              {rules.map((rule) => (
                <tr key={rule.id} className="border-b border-border/50 font-mono">
                  <td className="p-3 text-text">{rule.name}</td>
                  <td className="p-3 text-text-muted">{rule.condition}</td>
                  <td className="p-3 text-text-muted">{rule.threshold}</td>
                  <td className="p-3 text-text-muted">{rule.action}</td>
                  <td className="p-3">
                    <span className={severityColors[rule.severity] || 'text-text-subtle'}>
                      {rule.severity}
                    </span>
                  </td>
                  <td className="p-3">
                    <label className="flex items-center gap-1 cursor-pointer">
                      <input
                        type="checkbox"
                        checked={rule.enabled}
                        onChange={(e) => onUpdate(rule.id, { enabled: e.target.checked })}
                        className="rounded bg-bg border-border text-accent"
                      />
                    </label>
                  </td>
                  <td className="p-3 text-right">
                    <button
                      onClick={() => onDelete(rule.id)}
                      className="text-error hover:text-error/80 transition-colors"
                    >
                      ✕
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
