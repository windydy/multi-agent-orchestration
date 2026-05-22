const statusDot: Record<string, string> = {
  success: 'bg-success',
  running: 'bg-running animate-pulse',
  failed: 'bg-error',
  interrupted: 'bg-warning',
  unknown: 'bg-text-subtle',
}

const statusLabel: Record<string, string> = {
  success: 'Done',
  running: 'Running',
  failed: 'Failed',
  interrupted: 'Interrupted',
}

export default function StatusBadge({ status }: { status: string }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className={`w-1.5 h-1.5 rounded-full ${statusDot[status] || 'bg-text-subtle'}`} />
      <span className="text-text-muted text-xs">{statusLabel[status] || status}</span>
    </span>
  )
}
