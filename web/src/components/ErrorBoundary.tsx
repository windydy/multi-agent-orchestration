import { Component, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
  error: Error | null
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error }
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-bg flex items-center justify-center">
          <div className="text-center max-w-md px-6">
            <h1 className="text-lg font-semibold text-error mb-2">Something went wrong</h1>
            <p className="text-text-muted text-sm mb-4 font-mono break-all">
              {this.state.error?.message ?? 'Unknown error'}
            </p>
            <button
              onClick={() => window.location.reload()}
              className="text-xs text-accent hover:text-accent-hover transition-colors px-3 py-1.5 rounded-md hover:bg-bg-sub"
            >
              ↻ Reload
            </button>
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
