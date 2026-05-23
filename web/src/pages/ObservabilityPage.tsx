import { useState, useEffect } from 'react'
import {
  LineChart, Line, AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, PieChart, Pie, Cell,
} from 'recharts'

const COLORS = ['#22c55e', '#ef4444', '#f59e0b', '#3b82f6', '#8b5cf6', '#6b7280']

interface StatsSummaryProps { data: Record<string, any> }

function StatsSummary({ data }: StatsSummaryProps) {
  const stats = [
    { label: 'Executions', value: data.total_executions ?? 0, color: 'text-accent' },
    { label: 'Cost', value: `$${(data.total_cost ?? 0).toFixed(2)}`, color: 'text-text' },
    { label: 'Success Rate', value: `${((data.success_rate ?? 0) * 100).toFixed(1)}%`, color: (data.success_rate ?? 0) > 0.9 ? 'text-success' : 'text-warning' },
    { label: 'Alerts', value: data.alert_count ?? 0, color: (data.alert_count ?? 0) > 0 ? 'text-error' : 'text-text-subtle' },
  ]

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
      {stats.map((s) => (
        <div key={s.label} className="bg-bg-sub border border-border rounded-lg p-3">
          <div className="text-text-subtle text-[11px] font-medium uppercase tracking-wider">{s.label}</div>
          <div className={`text-lg font-mono font-semibold mt-0.5 ${s.color}`}>{s.value}</div>
        </div>
      ))}
    </div>
  )
}

function CostChart({ trends }: { trends: any[] }) {
  if (trends.length === 0) {
    return <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">No cost data</div>
  }
  return (
    <div className="bg-bg-sub border border-border rounded-lg p-4">
      <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider mb-4">Daily Cost</h3>
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={trends}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 11 }} />
          <YAxis stroke="#6b7280" tick={{ fontSize: 11 }} />
          <Tooltip contentStyle={{ backgroundColor: '#1a1a1e', border: '1px solid #2d2d35', borderRadius: 8 }} />
          <Line type="monotone" dataKey="total_cost" stroke="#22c55e" strokeWidth={2} dot={{ r: 3 }} name="Cost ($)" />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}

function SuccessRateChart({ rates }: { rates: any[] }) {
  if (rates.length === 0) {
    return <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">No success rate data</div>
  }
  return (
    <div className="bg-bg-sub border border-border rounded-lg p-4">
      <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider mb-4">Success Rate</h3>
      <ResponsiveContainer width="100%" height={250}>
        <AreaChart data={rates}>
          <CartesianGrid strokeDasharray="3 3" stroke="#1f2937" />
          <XAxis dataKey="date" stroke="#6b7280" tick={{ fontSize: 11 }} />
          <YAxis domain={[0, 1]} stroke="#6b7280" tick={{ fontSize: 11 }} tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`} />
          <Tooltip contentStyle={{ backgroundColor: '#1a1a1e', border: '1px solid #2d2d35', borderRadius: 8 }} />
          <Area type="monotone" dataKey="rate" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.2} strokeWidth={2} dot={{ r: 3 }} name="Rate" />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  )
}

function PerformanceTable({ nodes }: { nodes: any[] }) {
  if (nodes.length === 0) {
    return <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">No performance data</div>
  }
  return (
    <div className="bg-bg-sub border border-border rounded-lg overflow-hidden">
      <div className="p-4">
        <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider">Node Performance</h3>
      </div>
      <table className="w-full text-xs">
        <thead>
          <tr className="border-t border-border text-text-subtle uppercase tracking-wider">
            <th className="text-left p-3">Node</th>
            <th className="text-right p-3">Count</th>
            <th className="text-right p-3">Avg</th>
            <th className="text-right p-3">P50</th>
            <th className="text-right p-3">P95</th>
            <th className="text-right p-3">P99</th>
          </tr>
        </thead>
        <tbody>
          {nodes.map((n) => (
            <tr key={n.node} className="border-t border-border/50 font-mono">
              <td className="p-3 text-text">{n.node}</td>
              <td className="p-3 text-right text-text-muted">{n.count}</td>
              <td className="p-3 text-right text-text-muted">{n.avg_ms}ms</td>
              <td className="p-3 text-right text-text-muted">{n.p50_ms}ms</td>
              <td className="p-3 text-right text-warning">{n.p95_ms}ms</td>
              <td className="p-3 text-right text-error">{n.p99_ms}ms</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function FailurePieChart({ reasons }: { reasons: any[] }) {
  if (reasons.length === 0) {
    return <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">No failure data</div>
  }
  return (
    <div className="bg-bg-sub border border-border rounded-lg p-4">
      <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider mb-4">Failure Reasons</h3>
      <ResponsiveContainer width="100%" height={250}>
        <PieChart>
          <Pie data={reasons} dataKey="count" nameKey="reason" cx="50%" cy="50%" outerRadius={80} label={({ name, percentage }: any) => `${name} ${percentage}%`}>
            {reasons.map((_, i) => (
              <Cell key={i} fill={COLORS[i % COLORS.length]} />
            ))}
          </Pie>
          <Tooltip contentStyle={{ backgroundColor: '#1a1a1e', border: '1px solid #2d2d35', borderRadius: 8 }} />
        </PieChart>
      </ResponsiveContainer>
    </div>
  )
}

function AlertList({ alerts }: { alerts: any[] }) {
  if (alerts.length === 0) {
    return <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">No alerts</div>
  }
  const severityColors: Record<string, string> = { high: 'text-error', medium: 'text-warning', low: 'text-text-subtle' }

  return (
    <div className="bg-bg-sub border border-border rounded-lg overflow-hidden">
      <div className="p-4">
        <h3 className="text-sm font-medium text-text-subtle uppercase tracking-wider">Recent Alerts</h3>
      </div>
      <div className="divide-y divide-border/50">
        {alerts.slice(0, 20).map((a: any) => (
          <div key={a.id} className="p-3 flex items-center gap-3">
            <div className={`w-2 h-2 rounded-full ${a.acknowledged ? 'bg-text-subtle' : 'bg-current ' + (severityColors[a.severity] || 'text-text-subtle')}`} />
            <div className="flex-1">
              <div className="text-xs text-text font-medium">{a.rule_name}</div>
              <div className="text-[11px] text-text-subtle">{a.message}</div>
            </div>
            <div className="text-[10px] text-text-subtle font-mono">{new Date(a.triggered_at * 1000).toLocaleString()}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function ObservabilityPage() {
  const [period, setPeriod] = useState<'24h' | '7d' | '30d'>('7d')
  const [overview, setOverview] = useState<any>(null)
  const [costTrend, setCostTrend] = useState<any[]>([])
  const [successRates, setSuccessRates] = useState<any[]>([])
  const [performance, setPerformance] = useState<any[]>([])
  const [failureReasons, setFailureReasons] = useState<any[]>([])
  const [alerts, setAlerts] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const days = period === '24h' ? 1 : period === '7d' ? 7 : 30
      const [ovRes, costRes, rateRes, perfRes, failRes, alertRes] = await Promise.all([
        fetch(`/api/observability/overview?period=${period}`).then(r => r.json()),
        fetch(`/api/observability/cost/daily?days=${days}`).then(r => r.json()),
        fetch(`/api/observability/success-rate?days=${days}`).then(r => r.json()),
        fetch('/api/observability/performance').then(r => r.json()),
        fetch('/api/observability/failure-reasons').then(r => r.json()),
        fetch('/api/observability/alerts').then(r => r.json()),
      ])
      setOverview(ovRes)
      setCostTrend(costRes.trends)
      setSuccessRates(rateRes.rates)
      setPerformance(perfRes.nodes)
      setFailureReasons(failRes.reasons)
      setAlerts(alertRes.alerts)
    } catch (e: any) {
      setError(e.message || 'Failed to load observability data')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { load() }, [period])

  if (error) {
    return (
      <div className="text-error text-sm py-16 text-center">
        <p>{error}</p>
        <button onClick={load} className="text-accent text-xs mt-2 hover:underline">Retry</button>
      </div>
    )
  }

  if (loading) {
    return <div className="text-text-subtle text-sm py-16 text-center">Loading…</div>
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-semibold tracking-tight">Observability</h1>
        <div className="flex gap-2">
          {(['24h', '7d', '30d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-3 py-1 text-xs rounded-md transition-colors ${
                period === p ? 'bg-accent text-bg' : 'bg-bg-sub text-text-subtle hover:text-text'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      <StatsSummary data={overview} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <CostChart trends={costTrend} />
        <SuccessRateChart rates={successRates} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <PerformanceTable nodes={performance} />
        <FailurePieChart reasons={failureReasons} />
      </div>

      <AlertList alerts={alerts} />
    </div>
  )
}
