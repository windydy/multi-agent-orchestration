import { useEffect, useState } from 'react'
import { OverviewStats, ExecutionItem } from '../types'
import { fetchOverview, fetchExecutions } from '../lib/api'
import StatsCards from '../components/StatsCards'
import ExecutionTable from '../components/ExecutionTable'

export default function HomePage() {
  const [stats, setStats] = useState<OverviewStats | null>(null)
  const [items, setItems] = useState<ExecutionItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

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
      <StatsCards stats={stats ?? defaultStats} />
      <div>
        <h2 className="text-sm font-medium mb-4 text-text-subtle uppercase tracking-wider">Executions</h2>
        <ExecutionTable items={items} />
      </div>
    </div>
  )
}
