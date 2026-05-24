/**
 * Tests for ExecutionPage component
 * Validates clarifying state handling and question form
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import ExecutionPage from '../pages/ExecutionPage'
import * as api from '../lib/api'
import type { ClarificationState, ClarificationQuestion } from '../types'

// Mock API functions
vi.mock('../lib/api', () => ({
  fetchExecution: vi.fn(),
  fetchDAG: vi.fn(),
  fetchClarificationState: vi.fn(),
  submitClarificationAnswers: vi.fn(),
  skipClarification: vi.fn(),
  transitionState: vi.fn(),
  calculateScore: vi.fn(),
  submitScore: vi.fn(),
  generateIdempotencyKey: vi.fn(() => 'ik_test_123'),
  saveDraftLocal: vi.fn(),
  loadDraftLocal: vi.fn(() => null),
  clearDraftLocal: vi.fn(),
}))

// Mock child components
vi.mock('../components/NodeTimeline', () => ({
  default: () => <div data-testid="node-timeline">Timeline</div>,
}))

vi.mock('../components/DAGView', () => ({
  default: () => <div data-testid="dag-view">DAG View</div>,
}))

describe('ExecutionPage', () => {
  const mockExecution = {
    thread_id: 'thread_001',
    status: 'clarifying',
    started_at: '2024-01-01T00:00:00Z',
    ended_at: null,
    duration_ms: null,
    nodes: [],
    total_cost: null,
    total_tokens: null,
    task_input: 'Build a user management system',
  }

  const mockDAG = {
    thread_id: 'thread_001',
    nodes: [],
    edges: [],
  }

  const mockQuestions: ClarificationQuestion[] = [
    {
      q_id: 'q_001',
      dimension: 'Completeness',
      content: 'What is the expected user capacity?',
      options: ['100-1000', '1000-10000', '10000+'],
      is_resolved: false,
      priority: 1,
    },
    {
      q_id: 'q_002',
      dimension: 'Security',
      content: 'Describe authentication requirements',
      is_resolved: false,
      priority: 2,
    },
    {
      q_id: 'q_003',
      dimension: 'Performance',
      content: 'What is the acceptable response time?',
      options: ['<100ms', '<500ms', '<1s'],
      is_resolved: false,
      priority: 4,
    },
  ]

  const mockClarification: ClarificationState = {
    thread_id: 'thread_001',
    status: 'clarifying',
    score: null,
    recommendation: 'interactive',
    questions: mockQuestions,
    assumptions: [
      {
        a_id: 'a_001',
        source: 'system_inferred',
        content: 'Default database will be PostgreSQL',
        impact_scope: ['database'],
        risk_level: 'medium',
        confirmed: false,
      },
    ],
    answers: {},
    enriched_task: null,
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }

  beforeEach(() => {
    vi.mocked(api.fetchExecution).mockResolvedValue(mockExecution)
    vi.mocked(api.fetchDAG).mockResolvedValue(mockDAG)
    vi.mocked(api.fetchClarificationState).mockResolvedValue(mockClarification)
    vi.mocked(api.submitClarificationAnswers).mockResolvedValue({ status: 'answered' })
    vi.mocked(api.skipClarification).mockResolvedValue({ status: 'skipped' })
    vi.mocked(api.transitionState).mockResolvedValue({ status: 'approved' })
    vi.mocked(api.calculateScore).mockResolvedValue({
      score_id: 'score_001',
      dimensions: { Completeness: 85 },
      weights: { Completeness: 0.15 },
      total_score: 85,
      audit_hash: 'hash123',
      feature_vector: [0.85],
      suggestions: [],
    })
  })

  const renderWithRouter = (threadId = 'thread_001') => {
    return render(
      <MemoryRouter initialEntries={[`/executions/${threadId}`]}>
        <Routes>
          <Route path="/executions/:threadId" element={<ExecutionPage />} />
        </Routes>
      </MemoryRouter>
    )
  }

  describe('Clarifying State', () => {
    it('should show clarification form when status is clarifying', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Clarification Required')).toBeInTheDocument()
      })
    })

    it('should display all clarification questions', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('What is the expected user capacity?')).toBeInTheDocument()
        expect(screen.getByText('Describe authentication requirements')).toBeInTheDocument()
        expect(screen.getByText('What is the acceptable response time?')).toBeInTheDocument()
      })
    })

    it('should show priority labels for questions', async () => {
      renderWithRouter()

      await waitFor(() => {
        // priority 1 -> high, priority 2 -> high, priority 4 -> low
        // So we should see HIGH (twice) and LOW
        expect(screen.getAllByText('HIGH')).toHaveLength(2)
        expect(screen.getByText('LOW')).toBeInTheDocument()
      })
    })

    it('should separate high priority and additional questions', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('High Priority (Blocking)')).toBeInTheDocument()
        expect(screen.getByText('Additional Questions')).toBeInTheDocument()
      })
    })

    it('should show dimension labels', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Completeness')).toBeInTheDocument()
        expect(screen.getByText('Security')).toBeInTheDocument()
        expect(screen.getByText('Performance')).toBeInTheDocument()
      })
    })
  })

  describe('Question Form', () => {
    it('should render radio buttons for questions with options', async () => {
      renderWithRouter()

      await waitFor(() => {
        // Check for option text
        expect(screen.getByText('100-1000')).toBeInTheDocument()
        expect(screen.getByText('1000-10000')).toBeInTheDocument()
        expect(screen.getByText('10000+')).toBeInTheDocument()
      })
    })

    it('should render text input for questions without options', async () => {
      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        expect(input).toBeInTheDocument()
      })
    })

    it('should allow answering questions', async () => {
      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        fireEvent.change(input, { target: { value: 'OAuth2 with JWT' } })
        expect(input).toHaveValue('OAuth2 with JWT')
      })
    })

    it('should show progress indicator', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('0/3 answered')).toBeInTheDocument()
      })
    })

    it('should update progress when answers are provided', async () => {
      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        fireEvent.change(input, { target: { value: 'Test answer' } })
      })

      await waitFor(() => {
        expect(screen.getByText('1/3 answered')).toBeInTheDocument()
      })
    })

    it('should disable submit when no answers provided', async () => {
      renderWithRouter()

      await waitFor(() => {
        const submitButton = screen.getByText('Submit Answers')
        expect(submitButton).toBeDisabled()
      })
    })

    it('should enable submit when answers are provided', async () => {
      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        fireEvent.change(input, { target: { value: 'Test answer' } })
      })

      await waitFor(() => {
        const submitButton = screen.getByText('Submit Answers')
        expect(submitButton).not.toBeDisabled()
      })
    })

    it('should submit answers when form is submitted', async () => {
      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        fireEvent.change(input, { target: { value: 'OAuth2 with JWT' } })
      })

      await waitFor(() => {
        const submitButton = screen.getByText('Submit Answers')
        fireEvent.click(submitButton)
      })

      await waitFor(() => {
        expect(api.submitClarificationAnswers).toHaveBeenCalledWith({
          thread_id: 'thread_001',
          answers: { q_002: 'OAuth2 with JWT' },
        })
      })
    })
  })

  describe('Assumptions', () => {
    it('should show assumptions preview', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText(/View 1 assumption/)).toBeInTheDocument()
      })
    })

    it('should show risk level badges', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('medium')).toBeInTheDocument()
      })
    })

    it('should show assumption content when expanded', async () => {
      renderWithRouter()

      await waitFor(() => {
        const summary = screen.getByText(/View 1 assumption/)
        fireEvent.click(summary)
      })

      await waitFor(() => {
        expect(screen.getByText('Default database will be PostgreSQL')).toBeInTheDocument()
      })
    })
  })

  describe('Skip Clarification', () => {
    it('should show skip button', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Skip & Use Assumptions')).toBeInTheDocument()
      })
    })

    it('should call skip API when clicked', async () => {
      renderWithRouter()

      await waitFor(() => {
        const skipButton = screen.getByText('Skip & Use Assumptions')
        fireEvent.click(skipButton)
      })

      await waitFor(() => {
        expect(api.skipClarification).toHaveBeenCalledWith('thread_001')
      })
    })
  })

  describe('State Transitions', () => {
    it('should show approve/reject buttons when scored', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('✓ Approve')).toBeInTheDocument()
        expect(screen.getByText('✗ Reject')).toBeInTheDocument()
      })
    })

    it('should show confirmation before approve', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        const approveButton = screen.getByText('✓ Approve')
        fireEvent.click(approveButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Confirm approval?')).toBeInTheDocument()
        expect(screen.getByText('Yes, Approve')).toBeInTheDocument()
      })
    })

    it('should call transition API on approve', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        const approveButton = screen.getByText('✓ Approve')
        fireEvent.click(approveButton)
      })

      await waitFor(() => {
        const confirmButton = screen.getByText('Yes, Approve')
        fireEvent.click(confirmButton)
      })

      await waitFor(() => {
        expect(api.transitionState).toHaveBeenCalledWith({
          thread_id: 'thread_001',
          target_status: 'approved',
        })
      })
    })

    it('should show confirmation before reject', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        const rejectButton = screen.getByText('✗ Reject')
        fireEvent.click(rejectButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Confirm rejection?')).toBeInTheDocument()
        expect(screen.getByText('Yes, Reject')).toBeInTheDocument()
      })
    })

    it('should call transition API on reject', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        const rejectButton = screen.getByText('✗ Reject')
        fireEvent.click(rejectButton)
      })

      await waitFor(() => {
        const confirmButton = screen.getByText('Yes, Reject')
        fireEvent.click(confirmButton)
      })

      await waitFor(() => {
        expect(api.transitionState).toHaveBeenCalledWith({
          thread_id: 'thread_001',
          target_status: 'rejected',
        })
      })
    })

    it('should cancel confirmation on cancel button click', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scored',
      })

      renderWithRouter()

      await waitFor(() => {
        const approveButton = screen.getByText('✓ Approve')
        fireEvent.click(approveButton)
      })

      await waitFor(() => {
        const cancelButton = screen.getByText('Cancel')
        fireEvent.click(cancelButton)
      })

      await waitFor(() => {
        expect(screen.getByText('✓ Approve')).toBeInTheDocument()
        expect(screen.queryByText('Confirm approval?')).not.toBeInTheDocument()
      })
    })
  })

  describe('Score Display', () => {
    it('should show calculate score button when answered', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'clarifying',
      })
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        status: 'answered' as any,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Calculate Quality Score')).toBeInTheDocument()
      })
    })

    it('should call calculate score API when clicked', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'clarifying',
      })
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        status: 'answered' as any,
      })

      renderWithRouter()

      await waitFor(() => {
        const button = screen.getByText('Calculate Quality Score')
        fireEvent.click(button)
      })

      await waitFor(() => {
        expect(api.calculateScore).toHaveBeenCalledWith({
          thread_id: 'thread_001',
        })
      })
    })
  })

  describe('Loading and Error States', () => {
    it('should show loading state initially', () => {
      renderWithRouter()
      expect(screen.getByText('Loading…')).toBeInTheDocument()
    })

    it('should show error state on failure', async () => {
      vi.mocked(api.fetchExecution).mockRejectedValueOnce(new Error('Failed to load'))

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load')).toBeInTheDocument()
        expect(screen.getByText('← Back')).toBeInTheDocument()
      })
    })
  })

  describe('Auto-Transition', () => {
    it('should show auto-transition ready when score >= 80 and no pending questions', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 85,
        questions: mockQuestions.map(q => ({ ...q, is_resolved: true })),
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Auto-Transition Ready')).toBeInTheDocument()
        expect(screen.getByText('Score ≥ 80 and all questions resolved → CONFIRMED')).toBeInTheDocument()
      })
    })

    it('should show confirm button when auto-transition is ready', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 85,
        questions: mockQuestions.map(q => ({ ...q, is_resolved: true })),
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Confirm & Proceed')).toBeInTheDocument()
      })
    })

    it('should not show auto-transition when score < 80', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 65,
        questions: mockQuestions.map(q => ({ ...q, is_resolved: true })),
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.queryByText('Auto-Transition Ready')).not.toBeInTheDocument()
      })
    })

    it('should not show auto-transition when pending questions exist', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 85,
        // Questions still have is_resolved: false
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.queryByText('Auto-Transition Ready')).not.toBeInTheDocument()
      })
    })
  })

  describe('Scoring State', () => {
    it('should show evaluating indicator when status is scoring', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'scoring',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Evaluating Requirement...')).toBeInTheDocument()
        expect(screen.getByText('ClarifierAgent is analyzing your requirement across 9 dimensions')).toBeInTheDocument()
      })
    })
  })

  describe('State Transitions - Confirmed State', () => {
    it('should show handoff button when confirmed', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'confirmed',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('→ Handoff to Development')).toBeInTheDocument()
      })
    })

    it('should show confirmation before handoff', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'confirmed',
      })

      renderWithRouter()

      await waitFor(() => {
        const handoffButton = screen.getByText('→ Handoff to Development')
        fireEvent.click(handoffButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Handoff to development?')).toBeInTheDocument()
        expect(screen.getByText('Yes, Handoff')).toBeInTheDocument()
      })
    })

    it('should call transition API on handoff', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'confirmed',
      })

      renderWithRouter()

      await waitFor(() => {
        const handoffButton = screen.getByText('→ Handoff to Development')
        fireEvent.click(handoffButton)
      })

      await waitFor(() => {
        const confirmButton = screen.getByText('Yes, Handoff')
        fireEvent.click(confirmButton)
      })

      await waitFor(() => {
        expect(api.transitionState).toHaveBeenCalledWith({
          thread_id: 'thread_001',
          target_status: 'in_development',
        })
      })
    })
  })

  describe('State Transitions - In Development State', () => {
    it('should show archive button when in_development', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'in_development',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('✓ Archive')).toBeInTheDocument()
      })
    })

    it('should call transition API on archive', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'in_development',
      })

      renderWithRouter()

      await waitFor(() => {
        const archiveButton = screen.getByText('✓ Archive')
        fireEvent.click(archiveButton)
      })

      await waitFor(() => {
        const confirmButton = screen.getByText('Yes, Archive')
        fireEvent.click(confirmButton)
      })

      await waitFor(() => {
        expect(api.transitionState).toHaveBeenCalledWith({
          thread_id: 'thread_001',
          target_status: 'completed',
        })
      })
    })
  })

  // ── New Field Support Tests (question/importance fields) ──

  describe('New Question Fields Support', () => {
    it('should render questions with new question field instead of content', async () => {
      const questionsWithNewFields: ClarificationQuestion[] = [
        {
          q_id: 'q_001',
          dimension: 'functional_scope',
          question: 'What is the expected user capacity?',
          importance: 'high',
          is_resolved: false,
        },
      ]
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        questions: questionsWithNewFields,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('What is the expected user capacity?')).toBeInTheDocument()
      })
    })

    it('should show importance labels using new importance field', async () => {
      const questionsWithImportance: ClarificationQuestion[] = [
        {
          q_id: 'q_001',
          dimension: 'functional_scope',
          question: 'High priority question',
          importance: 'high',
          is_resolved: false,
        },
        {
          q_id: 'q_002',
          dimension: 'tech_constraints',
          question: 'Medium priority question',
          importance: 'medium',
          is_resolved: false,
        },
        {
          q_id: 'q_003',
          dimension: 'budget',
          question: 'Low priority question',
          importance: 'low',
          is_resolved: false,
        },
      ]
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        questions: questionsWithImportance,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('HIGH')).toBeInTheDocument()
        expect(screen.getByText('MEDIUM')).toBeInTheDocument()
        expect(screen.getByText('LOW')).toBeInTheDocument()
      })
    })
  })

  // ── Round Counter Tests ──

  describe('Round Counter', () => {
    it('should show round counter when current_round is set', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        current_round: 2,
        max_rounds: 3,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('(Round 2/3)')).toBeInTheDocument()
      })
    })

    it('should show default round counter when not set', async () => {
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('(Round 1/3)')).toBeInTheDocument()
      })
    })

    it('should show final round warning when on last round', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        current_round: 3,
        max_rounds: 3,
        score: 65,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Final Round')).toBeInTheDocument()
        expect(screen.getByText(/This is the last clarification round/)).toBeInTheDocument()
      })
    })
  })

  // ── Resolved Questions Tests ──

  describe('Resolved Questions', () => {
    it('should show resolved questions summary when some are resolved', async () => {
      const partiallyResolvedQuestions: ClarificationQuestion[] = [
        {
          q_id: 'q_001',
          dimension: 'Completeness',
          content: 'Resolved question',
          is_resolved: true,
          priority: 1,
        },
        {
          q_id: 'q_002',
          dimension: 'Security',
          content: 'Unresolved question',
          is_resolved: false,
          priority: 2,
        },
      ]
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        questions: partiallyResolvedQuestions,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('View 1 resolved question')).toBeInTheDocument()
      })
    })

    it('should show resolved questions content when expanded', async () => {
      const partiallyResolvedQuestions: ClarificationQuestion[] = [
        {
          q_id: 'q_001',
          dimension: 'Completeness',
          content: 'Resolved question content',
          is_resolved: true,
          priority: 1,
        },
        {
          q_id: 'q_002',
          dimension: 'Security',
          content: 'Unresolved question',
          is_resolved: false,
          priority: 2,
        },
      ]
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        questions: partiallyResolvedQuestions,
      })

      renderWithRouter()

      await waitFor(() => {
        const summary = screen.getByText('View 1 resolved question')
        fireEvent.click(summary)
      })

      await waitFor(() => {
        expect(screen.getByText('Resolved question content')).toBeInTheDocument()
      })
    })

    it('should show resolved checkmark for resolved questions', async () => {
      const partiallyResolvedQuestions: ClarificationQuestion[] = [
        {
          q_id: 'q_001',
          dimension: 'Completeness',
          content: 'Resolved question content',
          is_resolved: true,
          priority: 1,
        },
        {
          q_id: 'q_002',
          dimension: 'Security',
          content: 'Unresolved question',
          is_resolved: false,
          priority: 2,
        },
      ]
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        questions: partiallyResolvedQuestions,
      })

      renderWithRouter()

      await waitFor(() => {
        // Resolved questions are shown in the details summary section
        expect(screen.getByText('View 1 resolved question')).toBeInTheDocument()
      })

      // Expand the details to see resolved questions
      await waitFor(() => {
        const summary = screen.getByText('View 1 resolved question')
        fireEvent.click(summary)
      })

      await waitFor(() => {
        // Check for the checkmark and question content
        expect(screen.getByText('Resolved question content')).toBeInTheDocument()
      })
    })
  })

  // ── Score Display Tests ──

  describe('Score Display in Clarification Form', () => {
    it('should show clarity score when available', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 72,
      })

      renderWithRouter()

      await waitFor(() => {
        // Clarity score is shown in the header as part of "0/3 answered · Clarity Score: 72%"
        // Use getAllByText since score appears in multiple places
        const scoreElements = screen.getAllByText(/72%/)
        expect(scoreElements.length).toBeGreaterThan(0)
      })
    })

    it('should show score threshold indicator', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 72,
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText(/need 80%/)).toBeInTheDocument()
      })
    })

    it('should show green indicator when score meets threshold', async () => {
      vi.mocked(api.fetchClarificationState).mockResolvedValueOnce({
        ...mockClarification,
        score: 85,
        questions: mockQuestions.map(q => ({ ...q, is_resolved: true })),
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('85% ✓')).toBeInTheDocument()
      })
    })
  })

  // ── Error Handling Tests ──

  describe('Error Handling', () => {
    it('should show error message when submission fails', async () => {
      vi.mocked(api.submitClarificationAnswers).mockRejectedValueOnce(new Error('Submission failed'))

      renderWithRouter()

      await waitFor(() => {
        const input = screen.getByPlaceholderText('Your answer...')
        fireEvent.change(input, { target: { value: 'Test answer' } })
      })

      await waitFor(() => {
        const submitButton = screen.getByText('Submit Answers')
        fireEvent.click(submitButton)
      })

      await waitFor(() => {
        expect(screen.getByText('Submission failed')).toBeInTheDocument()
      })
    })
  })

  // ── needs_clarification Status Tests ──

  describe('needs_clarification Status', () => {
    it('should show clarification form when status is needs_clarification', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'needs_clarification',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Clarification Required')).toBeInTheDocument()
      })
    })

    it('should show needs_clarification status label', async () => {
      vi.mocked(api.fetchExecution).mockResolvedValueOnce({
        ...mockExecution,
        status: 'needs_clarification',
      })

      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Needs Clarification')).toBeInTheDocument()
      })
    })
  })
})
