/**
 * Tests for HomePage component
 * Validates CreateTaskModal and clarification mode selection
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import HomePage from '../pages/HomePage'
import * as api from '../lib/api'

// Mock API functions
vi.mock('../lib/api', () => ({
  fetchOverview: vi.fn(),
  fetchExecutions: vi.fn(),
  createExecution: vi.fn(),
}))

// Mock child components
vi.mock('../components/StatsCards', () => ({
  default: ({ stats }: any) => <div data-testid="stats-cards">{stats?.total_executions}</div>,
}))

vi.mock('../components/ExecutionTable', () => ({
  default: ({ items }: any) => <div data-testid="execution-table">{items?.length} items</div>,
}))

describe('HomePage', () => {
  const mockStats = {
    total_executions: 5,
    running: 1,
    success: 3,
    failed: 1,
    interrupted: 0,
  }

  const mockExecutions = {
    total: 5,
    items: [
      { thread_id: 't1', status: 'success', started_at: '2024-01-01', ended_at: '2024-01-01', duration_ms: 1000, node_count: 3, completed_nodes: 3 },
    ],
  }

  beforeEach(() => {
    vi.mocked(api.fetchOverview).mockResolvedValue(mockStats)
    vi.mocked(api.fetchExecutions).mockResolvedValue(mockExecutions)
    vi.mocked(api.createExecution).mockResolvedValue({ thread_id: 'new_thread' })
  })

  it('should render dashboard header and stats', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Dashboard')).toBeInTheDocument()
      expect(screen.getByTestId('stats-cards')).toBeInTheDocument()
    })
  })

  it('should show New Task button', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('+ New Task')).toBeInTheDocument()
    })
  })

  it('should open create task modal when New Task is clicked', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      const newTaskButton = screen.getByText('+ New Task')
      fireEvent.click(newTaskButton)
    })

    await waitFor(() => {
      expect(screen.getByText('Create New Task')).toBeInTheDocument()
    })
  })

  it('should display all three clarification modes', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    // Open modal
    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      expect(screen.getByText('Auto')).toBeInTheDocument()
      expect(screen.getByText('Conservative')).toBeInTheDocument()
      expect(screen.getByText('Interactive')).toBeInTheDocument()
    })
  })

  it('should show mode descriptions', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      // Auto mode description
      expect(screen.getByText(/ClarifierAgent automatically evaluates/)).toBeInTheDocument()
      // Conservative mode description (shown when selected)
      const conservativeButton = screen.getByText('Conservative').closest('button')
      if (conservativeButton) fireEvent.click(conservativeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/Uses safe assumptions/)).toBeInTheDocument()
    })
  })

  it('should allow mode selection', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    // Click Conservative mode
    await waitFor(() => {
      const conservativeButton = screen.getByText('Conservative').closest('button')
      if (conservativeButton) fireEvent.click(conservativeButton)
    })

    // Verify mode detail updates - shows conservative workflow
    await waitFor(() => {
      expect(screen.getByText(/Uses safe assumptions/)).toBeInTheDocument()
      expect(screen.getByText(/DRAFT → SCORING → CLARIFYING → \(apply assumptions\) → CONFIRMED/)).toBeInTheDocument()
    })
  })

  it('should submit task with selected mode', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    // Fill task description
    const textarea = screen.getByPlaceholderText('Describe what you want to accomplish...')
    fireEvent.change(textarea, { target: { value: 'Build a new feature' } })

    // Submit
    await waitFor(() => {
      const submitButton = screen.getByText('Create Task')
      fireEvent.click(submitButton)
    })

    await waitFor(() => {
      expect(api.createExecution).toHaveBeenCalledWith({
        task: 'Build a new feature',
        clarification_mode: 'auto', // default mode
      })
    })
  })

  it('should close modal on cancel', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      const cancelButton = screen.getByText('Cancel')
      fireEvent.click(cancelButton)
    })

    await waitFor(() => {
      expect(screen.queryByText('Create New Task')).not.toBeInTheDocument()
    })
  })

  it('should close modal on X button', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      const closeButton = screen.getByLabelText('Close modal')
      fireEvent.click(closeButton)
    })

    await waitFor(() => {
      expect(screen.queryByText('Create New Task')).not.toBeInTheDocument()
    })
  })

  it('should disable submit when task is empty', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      const submitButton = screen.getByText('Create Task')
      expect(submitButton).toBeDisabled()
    })
  })

  it('should show error on failed submission', async () => {
    vi.mocked(api.createExecution).mockRejectedValueOnce(new Error('API Error'))

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    const textarea = screen.getByPlaceholderText('Describe what you want to accomplish...')
    fireEvent.change(textarea, { target: { value: 'Test task' } })

    await waitFor(() => {
      const submitButton = screen.getByText('Create Task')
      fireEvent.click(submitButton)
    })

    await waitFor(() => {
      expect(screen.getByText('API Error')).toBeInTheDocument()
    })
  })

  it('should submit with conservative mode when selected', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    // Fill task
    const textarea = screen.getByPlaceholderText('Describe what you want to accomplish...')
    fireEvent.change(textarea, { target: { value: 'Build API' } })

    // Select conservative mode
    await waitFor(() => {
      const conservativeButton = screen.getByText('Conservative').closest('button')
      if (conservativeButton) fireEvent.click(conservativeButton)
    })

    // Submit
    await waitFor(() => {
      const submitButton = screen.getByText('Create Task')
      fireEvent.click(submitButton)
    })

    await waitFor(() => {
      expect(api.createExecution).toHaveBeenCalledWith({
        task: 'Build API',
        clarification_mode: 'conservative',
      })
    })
  })

  it('should submit with interactive mode when selected', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    // Fill task
    const textarea = screen.getByPlaceholderText('Describe what you want to accomplish...')
    fireEvent.change(textarea, { target: { value: 'Build API' } })

    // Select interactive mode
    await waitFor(() => {
      const interactiveButton = screen.getByText('Interactive').closest('button')
      if (interactiveButton) fireEvent.click(interactiveButton)
    })

    // Submit
    await waitFor(() => {
      const submitButton = screen.getByText('Create Task')
      fireEvent.click(submitButton)
    })

    await waitFor(() => {
      expect(api.createExecution).toHaveBeenCalledWith({
        task: 'Build API',
        clarification_mode: 'interactive',
      })
    })
  })

  it('should show workflow description for selected mode', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    // Check default auto workflow
    await waitFor(() => {
      expect(screen.getByText(/Workflow:.*DRAFT.*SCORING.*auto-route.*CONFIRMED or CLARIFYING/)).toBeInTheDocument()
    })

    // Switch to conservative and check workflow
    await waitFor(() => {
      const conservativeButton = screen.getByText('Conservative').closest('button')
      if (conservativeButton) fireEvent.click(conservativeButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/Workflow:.*DRAFT.*SCORING.*CLARIFYING.*apply assumptions.*CONFIRMED/)).toBeInTheDocument()
    })

    // Switch to interactive and check workflow
    await waitFor(() => {
      const interactiveButton = screen.getByText('Interactive').closest('button')
      if (interactiveButton) fireEvent.click(interactiveButton)
    })

    await waitFor(() => {
      expect(screen.getByText(/Workflow:.*DRAFT.*SCORING.*CLARIFYING.*answer questions.*re-evaluate.*CONFIRMED/)).toBeInTheDocument()
    })
  })

  it('should show mode icons', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    )

    await waitFor(() => {
      fireEvent.click(screen.getByText('+ New Task'))
    })

    await waitFor(() => {
      // Check for mode icons (using text content since they're emoji)
      expect(screen.getByText('⚡')).toBeInTheDocument()
      expect(screen.getByText('🛡️')).toBeInTheDocument()
      expect(screen.getByText('💬')).toBeInTheDocument()
    })
  })
})
