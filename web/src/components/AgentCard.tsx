import { AgentResponse } from '../types'

interface AgentCardProps {
  agent: AgentResponse
  onToggle: (id: string, enabled: boolean) => void
  onModelChange: (id: string, model: string) => void
}

export default function AgentCard({ agent, onToggle, onModelChange }: AgentCardProps) {
  return (
    <div className={`bg-bg-sub border rounded-lg p-4 transition-colors ${agent.enabled ? 'border-border' : 'border-border/50 opacity-60'}`}>
      <div className="flex items-start justify-between mb-2">
        <div>
          <h3 className="text-sm font-medium text-text">{agent.name}</h3>
          <p className="text-xs text-text-subtle mt-0.5">{agent.description}</p>
        </div>
        <label className="flex items-center gap-1.5 cursor-pointer">
          <input
            type="checkbox"
            checked={agent.enabled}
            onChange={(e) => onToggle(agent.id, e.target.checked)}
            className="rounded bg-bg border-border text-accent focus:ring-accent"
          />
          <span className="text-[10px] text-text-subtle uppercase">{agent.enabled ? 'ON' : 'OFF'}</span>
        </label>
      </div>

      <div className="mt-3">
        <label className="text-[11px] text-text-subtle uppercase tracking-wider">Model</label>
        <input
          type="text"
          value={agent.model}
          onChange={(e) => onModelChange(agent.id, e.target.value)}
          className="w-full mt-1 bg-bg border border-border rounded px-2 py-1 text-xs font-mono text-text focus:border-accent focus:outline-none"
        />
      </div>

      <div className="mt-2 flex flex-wrap gap-1">
        {agent.capabilities.map((cap) => (
          <span key={cap} className="text-[10px] px-1.5 py-0.5 bg-accent/10 text-accent rounded">
            {cap}
          </span>
        ))}
      </div>
    </div>
  )
}
