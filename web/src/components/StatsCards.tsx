import { OverviewStats } from '../types'

const statusItems = [
  { key: 'running' as const, label: 'Running', color: 'text-running' },
  { key: 'success' as const, label: 'Success', color: 'text-success' },
  { key: 'failed' as const, label: 'Failed', color: 'text-error' },
  { key: 'interrupted' as const, label: 'Interrupted', color: 'text-warning' },
]

export default function StatsCards({ stats }: { stats: OverviewStats }) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-5 gap-4 mb-8">
      {/* Total */}
      <div className="bg-bg-sub border border-border rounded-xl p-5">
        <div className="text-text-subtle text-xs font-medium uppercase tracking-wider mb-1">Total</div>
        <div className="text-3xl font-bold tracking-tight">{stats.total_executions}</div>
      </div>
      {statusItems.map(({ key, label, color }) => (
        <div key={key} className="bg-bg-sub border border-border rounded-xl p-5">
          <div className="text-text-subtle text-xs font-medium uppercase tracking-wider mb-1">{label}</div>
          <div className={`text-3xl font-bold tracking-tight ${color}`}>{stats[key] || 0}</div>
        </div>
      ))}
    </div>
  )
}
