import { useState, useEffect } from 'react'
import { AgentResponse, VerifierResponse, WorkflowResponse } from '../types'
import AgentCard from '../components/AgentCard'
import VerifierTable from '../components/VerifierTable'
import YAMLEditor from '../components/YAMLEditor'

export default function ConfigPage() {
  const [activeTab, setActiveTab] = useState<'workflows' | 'agents' | 'verifiers'>('workflows')
  const [agents, setAgents] = useState<AgentResponse[]>([])
  const [verifiers, setVerifiers] = useState<VerifierResponse[]>([])
  const [workflows, setWorkflows] = useState<WorkflowResponse[]>([])
  const [selectedWorkflow, setSelectedWorkflow] = useState<WorkflowResponse | null>(null)
  const [yamlContent, setYamlContent] = useState('')
  const [validationError, setValidationError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  async function loadAll() {
    setLoading(true)
    setError(null)
    try {
      const [aRes, vRes, wRes] = await Promise.all([
        fetch('/api/config/agents').then(r => r.json()),
        fetch('/api/config/verifiers').then(r => r.json()),
        fetch('/api/config/workflows').then(r => r.json()),
      ])
      setAgents(aRes.agents)
      setVerifiers(vRes.rules)
      setWorkflows(wRes.workflows)
    } catch (e: any) {
      setError(e.message || 'Failed to load configuration')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { loadAll() }, [])

  async function handleAgentToggle(id: string, enabled: boolean) {
    const res = await fetch(`/api/config/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ enabled }),
    })
    if (!res.ok) {
      alert(`Failed to update agent: ${await res.text()}`)
      return
    }
    setAgents(prev => prev.map(a => a.id === id ? { ...a, enabled } : a))
  }

  async function handleAgentModelChange(id: string, model: string) {
    const res = await fetch(`/api/config/agents/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ model }),
    })
    if (!res.ok) {
      alert(`Failed to update agent: ${await res.text()}`)
      return
    }
    setAgents(prev => prev.map(a => a.id === id ? { ...a, model } : a))
  }

  async function handleVerifierCreate(rule: any) {
    const res = await fetch('/api/config/verifiers', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(rule),
    })
    if (!res.ok) return
    const created = await res.json()
    setVerifiers(prev => [...prev, created])
  }

  async function handleVerifierUpdate(id: string, updates: any) {
    const res = await fetch(`/api/config/verifiers/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(updates),
    })
    if (!res.ok) return
    const updated = await res.json()
    setVerifiers(prev => prev.map(r => r.id === id ? updated : r))
  }

  async function handleVerifierDelete(id: string) {
    const res = await fetch(`/api/config/verifiers/${id}`, { method: 'DELETE' })
    if (!res.ok) return
    setVerifiers(prev => prev.filter(r => r.id !== id))
  }

  async function handleWorkflowSelect(name: string) {
    const res = await fetch(`/api/config/workflows/${name}`)
    const wf = await res.json()
    setSelectedWorkflow(wf)
    setYamlContent(wf.yaml_content)
    setValidationError(null)
  }

  async function handleWorkflowSave() {
    if (!selectedWorkflow) return
    setValidationError(null)
    const res = await fetch(`/api/config/workflows/${selectedWorkflow.name}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ yaml_content: yamlContent }),
    })
    if (!res.ok) {
      const error = await res.text()
      setValidationError(error)
      return
    }
    await loadAll()
    setSelectedWorkflow(null)
  }

  if (error) {
    return (
      <div className="text-error text-sm py-16 text-center">
        <p>{error}</p>
        <button onClick={loadAll} className="text-accent text-xs mt-2 hover:underline">Retry</button>
      </div>
    )
  }

  if (loading) {
    return <div className="text-text-subtle text-sm py-16 text-center">Loading…</div>
  }

  return (
    <div className="space-y-6">
      <h1 className="text-lg font-semibold tracking-tight">Configuration</h1>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-border">
        {(['workflows', 'agents', 'verifiers'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => { setActiveTab(tab); setSelectedWorkflow(null) }}
            className={`pb-2 text-sm font-medium transition-colors ${
              activeTab === tab
                ? 'text-accent border-b-2 border-accent'
                : 'text-text-subtle hover:text-text'
            }`}
          >
            {tab.charAt(0).toUpperCase() + tab.slice(1)}
          </button>
        ))}
      </div>

      {/* Workflows Tab */}
      {activeTab === 'workflows' && (
        selectedWorkflow ? (
          <div>
            <button
              onClick={() => setSelectedWorkflow(null)}
              className="text-text-subtle text-xs hover:text-text mb-3 block"
            >
              ← Back to list
            </button>
            <YAMLEditor
              value={yamlContent}
              onChange={setYamlContent}
              onSave={handleWorkflowSave}
              validationError={validationError}
            />
          </div>
        ) : (
          <div className="space-y-2">
            {workflows.length === 0 ? (
              <div className="text-text-subtle text-sm py-8 text-center bg-bg-sub border border-border rounded-lg">
                No workflows configured yet. Use PUT /api/config/workflows/{'{name}'} to add one.
              </div>
            ) : (
              workflows.map((wf) => (
                <button
                  key={wf.name}
                  onClick={() => handleWorkflowSelect(wf.name)}
                  className="w-full text-left bg-bg-sub border border-border rounded-lg p-4 hover:border-accent transition-colors"
                >
                  <div className="text-sm font-medium text-text">{wf.name}</div>
                  <div className="text-xs text-text-subtle mt-1">{wf.description || 'No description'}</div>
                </button>
              ))
            )}
          </div>
        )
      )}

      {/* Agents Tab */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {agents.map((agent) => (
            <AgentCard
              key={agent.id}
              agent={agent}
              onToggle={handleAgentToggle}
              onModelChange={handleAgentModelChange}
            />
          ))}
        </div>
      )}

      {/* Verifiers Tab */}
      {activeTab === 'verifiers' && (
        <VerifierTable
          rules={verifiers}
          onCreate={handleVerifierCreate}
          onUpdate={handleVerifierUpdate}
          onDelete={handleVerifierDelete}
        />
      )}
    </div>
  )
}
