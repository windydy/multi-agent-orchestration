import { useState, useCallback, useMemo } from 'react'
import {
  ReactFlow,
  Controls,
  Background,
  Handle,
  Position,
  type Node,
  type Edge,
  type NodeTypes,
} from '@xyflow/react'
import dagre from 'dagre'
import { DAGResponse } from '../types'
import '@xyflow/react/dist/style.css'

// ── Custom node renderer ──

const statusColors: Record<string, string> = {
  success: '#22c55e',
  failed: '#ef4444',
  running: '#3b82f6',
  pending: '#6b7280',
}

function DAGCustomNode({ data }: { data: Record<string, any> }) {
  const color = statusColors[data.status as string] || statusColors.pending
  const isRunning = data.status === 'running'

  return (
    <div
      className={`px-3 py-2 rounded-lg border-2 shadow-sm bg-bg-sub min-w-[160px] ${
        isRunning ? 'animate-pulse' : ''
      }`}
      style={{ borderColor: color }}
    >
      <Handle type="target" position={Position.Top} />
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
        <span className="text-xs font-medium text-text">{data.label as string}</span>
      </div>
      {data.status === 'failed' && data.error && (
        <div className="text-[10px] text-error mt-1 truncate">{data.error as string}</div>
      )}
      {data.duration_ms != null && (
        <div className="text-[10px] text-text-subtle mt-0.5 font-mono">
          {Math.round((data.duration_ms as number) / 1000)}s
        </div>
      )}
      {data.token_usage && (
        <div className="text-[10px] text-text-subtle font-mono">
          ↑{(data.token_usage as any).input} ↓{(data.token_usage as any).output}
        </div>
      )}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

// ── Auto layout with dagre ──

function getLayoutedElements(
  nodes: Node[],
  edges: Edge[],
  direction = 'TB'
): { nodes: Node[]; edges: Edge[] } {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: direction, nodesep: 60, ranksep: 80 })

  nodes.forEach((node) => g.setNode(node.id, { width: 160, height: 80 }))
  edges.forEach((edge) => g.setEdge(edge.source, edge.target))

  dagre.layout(g)

  const layoutedNodes = nodes.map((node) => {
    const nodeWithPosition = g.node(node.id)
    return {
      ...node,
      position: { x: nodeWithPosition.x - 80, y: nodeWithPosition.y - 40 },
    }
  })

  return { nodes: layoutedNodes, edges }
}

// ── Node detail panel ──

function NodeDetailPanel({ data, onClose }: { data: Record<string, any> | null; onClose: () => void }) {
  if (!data) return null
  return (
    <div className="absolute right-0 top-0 bottom-0 w-72 bg-bg-sub border-l border-border p-4 overflow-auto z-10">
      <button
        onClick={onClose}
        className="text-text-subtle text-xs hover:text-text mb-3 block"
      >
        ✕ Close
      </button>
      <h3 className="text-sm font-semibold text-text mb-3">{data.label as string}</h3>

      <div className="space-y-3">
        <div>
          <div className="text-[11px] text-text-subtle uppercase tracking-wider">Status</div>
          <div className="text-sm font-mono" style={{ color: statusColors[data.status as string] }}>
            {data.status as string}
          </div>
        </div>

        {data.duration_ms != null && (
          <div>
            <div className="text-[11px] text-text-subtle uppercase tracking-wider">Duration</div>
            <div className="text-sm font-mono">
              {Math.round((data.duration_ms as number) / 1000)}s
            </div>
          </div>
        )}

        {data.token_usage && (
          <div>
            <div className="text-[11px] text-text-subtle uppercase tracking-wider">Token Usage</div>
            <div className="text-sm font-mono">
              Input: {(data.token_usage as any).input} · Output: {(data.token_usage as any).output}
            </div>
          </div>
        )}

        {data.cost != null && (
          <div>
            <div className="text-[11px] text-text-subtle uppercase tracking-wider">Cost</div>
            <div className="text-sm font-mono">${(data.cost as number).toFixed(4)}</div>
          </div>
        )}

        {data.output_summary && (
          <div>
            <div className="text-[11px] text-text-subtle uppercase tracking-wider">Output</div>
            <div className="text-xs text-text-muted leading-relaxed mt-1">
              {data.output_summary as string}
            </div>
          </div>
        )}

        {data.error && (
          <div>
            <div className="text-[11px] text-error uppercase tracking-wider">Error</div>
            <div className="text-xs text-error leading-relaxed mt-1">{data.error as string}</div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── Main DAG View ──

const nodeTypes: NodeTypes = { dagCustom: DAGCustomNode }

export default function DAGView({ dag }: { dag: DAGResponse }) {
  const [selectedNode, setSelectedNode] = useState<Record<string, any> | null>(null)

  const onNodeClick = useCallback(
    (_event: React.MouseEvent, node: Node) => {
      setSelectedNode(node.data as Record<string, any>)
    },
    []
  )

  const reactFlowNodes: Node[] = dag.nodes.map((n) => ({
    id: n.id,
    type: 'dagCustom',
    position: { x: 0, y: 0 },
    data: { ...n },
  }))

  // P1-2: Dynamic edge colors based on node statuses
  const nodeStatusMap = useMemo(() => {
    const map = new Map<string, string>()
    dag.nodes.forEach((n) => map.set(n.id, n.status))
    return map
  }, [dag.nodes])

  const reactFlowEdges: Edge[] = dag.edges.map((e) => {
    const targetStatus = nodeStatusMap.get(e.to_node)
    const sourceStatus = nodeStatusMap.get(e.from_node)
    let stroke = '#374151'
    if (targetStatus === 'failed') {
      stroke = '#ef4444'
    } else if (sourceStatus === 'success' && targetStatus === 'success') {
      stroke = '#22c55e'
    } else if (targetStatus === 'running') {
      stroke = '#3b82f6'
    }

    return {
      id: `${e.from_node}-${e.to_node}`,
      source: e.from_node,
      target: e.to_node,
      style: { stroke, strokeWidth: 1.5 },
    }
  })

  // P1-1: Memoize layout
  const { nodes: layoutedNodes, edges: layoutedEdges } = useMemo(
    () => getLayoutedElements(reactFlowNodes, reactFlowEdges),
    [reactFlowNodes, reactFlowEdges]
  )

  // P0-1: Empty nodes placeholder
  if (dag.nodes.length === 0) {
    return (
      <div className="h-[500px] bg-bg-sub border border-border rounded-lg flex items-center justify-center">
        <div className="text-text-subtle text-sm">No nodes recorded yet</div>
      </div>
    )
  }

  return (
    <div className="relative h-[500px] bg-bg-sub border border-border rounded-lg overflow-hidden">
      <ReactFlow
        nodes={layoutedNodes}
        edges={layoutedEdges}
        nodeTypes={nodeTypes}
        fitView
        onNodeClick={onNodeClick}
        proOptions={{ hideAttribution: true }}
      >
        <Controls showInteractive={false} />
        <Background gap={16} size={1} color="#1f2937" />
      </ReactFlow>
      <NodeDetailPanel data={selectedNode} onClose={() => setSelectedNode(null)} />
    </div>
  )
}
