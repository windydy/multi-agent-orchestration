import { NodeEvent } from '../types'

const nodeLabels: Record<string, string> = {
  requirements: '需求分析',
  design: '技术设计',
  develop: '开发实现',
  review: '代码审查',
  test: '测试验证',
  fix: 'Bug修复',
}

const statusConfig: Record<string, { icon: string; color: string }> = {
  success: { icon: '✓', color: 'text-success' },
  running: { icon: '◌', color: 'text-running animate-pulse' },
  failed: { icon: '✗', color: 'text-error' },
  pending: { icon: '○', color: 'text-text-subtle' },
  skipped: { icon: '—', color: 'text-text-subtle' },
}

function formatDuration(ms: number | null): string {
  if (!ms) return ''
  const s = Math.floor(ms / 1000)
  if (s < 60) return `${s}s`
  const m = Math.floor(s / 60)
  const rem = s % 60
  return `${m}m ${rem}s`
}

export default function NodeTimeline({ nodes }: { nodes: NodeEvent[] }) {
  return (
    <div className="space-y-1">
      {nodes.map((node, i) => {
        const sc = statusConfig[node.status] || statusConfig.pending
        const label = nodeLabels[node.node] || node.node
        return (
          <div
            key={`${node.node}-${i}`}
            className={`rounded-lg border transition-colors ${
              node.status === 'running'
                ? 'border-running/30 bg-running/5'
                : node.status === 'failed'
                ? 'border-error/30 bg-error/5'
                : 'border-border bg-bg-sub'
            }`}
          >
            {/* Connector line */}
            {i > 0 && <div className="ml-6 border-l border-border h-3" />}

            <div className="px-4 py-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <span className={`text-sm font-medium ${sc.color}`}>{sc.icon}</span>
                  <div>
                    <span className="font-mono text-sm font-medium">{node.node}</span>
                    <span className="text-text-subtle text-xs ml-2">{label}</span>
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs font-mono text-text-subtle">
                  {node.duration_ms && <span>{formatDuration(node.duration_ms)}</span>}
                  {node.token_usage && (
                    <span>
                      {node.token_usage.input}→{node.token_usage.output}
                    </span>
                  )}
                </div>
              </div>

              {/* Expandable output */}
              {node.output_summary && (
                <div className="mt-2 ml-8 text-xs text-text-muted leading-relaxed font-mono bg-bg/50 rounded px-3 py-2 border border-border/50">
                  {node.output_summary}
                </div>
              )}
              {node.error && (
                <div className="mt-2 ml-8 text-xs text-error leading-relaxed font-mono bg-error/5 rounded px-3 py-2 border border-error/20">
                  {node.error}
                </div>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
