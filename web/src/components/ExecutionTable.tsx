import type { ExecutionItem } from '../types'
import { Link } from 'react-router-dom'
import StatusBadge from './StatusBadge'

function truncate(id: string) {
  return id.length > 32 ? id.slice(0, 12) + '…' + id.slice(-12) : id
}

function formatDuration(ms: number | null): string {
  if (!ms) return '—'
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  return `${Math.floor(s / 60)}m ${s % 60}s`
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleString([], {
    month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

export default function ExecutionTable({ items }: { items: ExecutionItem[] }) {
  if (!items.length) {
    return (
      <div className="border border-border rounded-xl p-16 text-center bg-bg-sub">
        <div className="text-text-subtle text-sm">No executions yet</div>
        <div className="text-text-subtle text-xs mt-2">Run a workflow from the CLI to see results here</div>
      </div>
    )
  }

  return (
    <div className="border border-border rounded-xl overflow-hidden bg-bg-sub">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border text-text-subtle text-[11px] font-medium uppercase tracking-wider">
            <th className="text-left px-5 py-3">Thread</th>
            <th className="text-left px-5 py-3">Status</th>
            <th className="text-left px-5 py-3 hidden sm:table-cell">Started</th>
            <th className="text-right px-5 py-3">Duration</th>
            <th className="text-right px-5 py-3 hidden md:table-cell">Progress</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-border/50">
          {items.map((item) => (
            <tr key={item.thread_id} className="hover:bg-bg-elevated/40 transition-colors group">
              <td className="px-5 py-3.5">
                <Link
                  to={`/executions/${item.thread_id}`}
                  className="font-mono text-xs text-accent hover:text-accent-hover transition-colors"
                >
                  {truncate(item.thread_id)}
                </Link>
              </td>
              <td className="px-5 py-3.5">
                <StatusBadge status={item.status} />
              </td>
              <td className="px-5 py-3.5 text-text-subtle text-xs font-mono hidden sm:table-cell">
                {formatDate(item.started_at)}
              </td>
              <td className="px-5 py-3.5 text-right text-text-subtle text-xs font-mono">
                {formatDuration(item.duration_ms)}
              </td>
              <td className="px-5 py-3.5 text-right text-text-subtle text-xs font-mono hidden md:table-cell">
                {item.completed_nodes}/{item.node_count}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
