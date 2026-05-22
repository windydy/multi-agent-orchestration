import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import ExecutionPage from './pages/ExecutionPage'

export default function App() {
  return (
    <div className="min-h-screen bg-bg">
      {/* Header */}
      <header className="border-b border-border sticky top-0 bg-bg/80 backdrop-blur-xl z-10">
        <div className="max-w-7xl mx-auto px-6 h-14 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-7 h-7 rounded-lg bg-accent flex items-center justify-center">
              <svg className="w-4 h-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                <path strokeLinecap="round" strokeLinejoin="round" d="M13 10V3L4 14h7v7l9-11h-7z" />
              </svg>
            </div>
            <span className="font-semibold text-sm tracking-tight">Multi-Agent Dashboard</span>
          </div>
          <button
            onClick={() => window.location.reload()}
            className="text-xs text-text-muted hover:text-text transition-colors px-3 py-1.5 rounded-md hover:bg-bg-sub"
          >
            ↻ Refresh
          </button>
        </div>
      </header>

      {/* Content */}
      <main className="max-w-7xl mx-auto px-6 py-8">
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/executions/:threadId" element={<ExecutionPage />} />
        </Routes>
      </main>
    </div>
  )
}
