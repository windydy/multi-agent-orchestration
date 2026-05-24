/**
 * Tests for Phase 9 Clarification APIs
 * Validates API function signatures and behavior aligned with Technical Design
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  createExecution,
  fetchClarificationState,
  fetchClarifierResult,
  submitClarificationAnswers,
  skipClarification,
  transitionState,
  calculateScore,
  getAuditTrail,
  syncClarificationState,
  submitClarification,
  getRequirementStatus,
  getRequirementDetail,
  triggerReEvaluation,
  getRequirementVersions,
  diffRequirementVersions,
  submitClarificationStatus,
  pollClarificationStatus,
  analyzeClarification,
  reEvaluateClarification,
  getClarificationDimensions,
  submitClarifyRequest,
  getClarifySession,
  processClarifyAnswers,
  submitScore,
  generateIdempotencyKey,
  saveDraft,
  loadDraft,
  deleteDraft,
  saveDraftLocal,
  loadDraftLocal,
  clearDraftLocal,
  getClarificationHistory,
  transitionStateValidated,
  getClarificationStatus,
  // Clarification State APIs (Phase 9 - Section 8.2)
  submitClarificationState,
  getClarificationState,
  submitClarifyAnswers,
} from '../lib/api'
import type {
  ClarificationState,
  ClarifierResult,
  ScoreRecord,
  ClarificationStatus,
  ClarificationRecommendation,
} from '../types'

// Mock fetch globally
const mockFetch = vi.fn()
;(globalThis as any).fetch = mockFetch

describe('Clarification APIs', () => {
  beforeEach(() => {
    mockFetch.mockReset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('createExecution', () => {
    it('should POST to /api/executions with clarification mode', async () => {
      const mockResponse = { thread_id: 'thread_001', status: 'draft' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await createExecution({
        task: 'Build a feature',
        clarification_mode: 'interactive',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: 'Build a feature',
          clarification_mode: 'interactive',
        }),
      })
      expect(result).toEqual(mockResponse)
    })

    it('should throw error on failed request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve('Bad request'),
      })

      await expect(
        createExecution({ task: 'Test' })
      ).rejects.toThrow('Bad request')
    })
  })

  describe('fetchClarificationState', () => {
    it('should GET clarification state for thread', async () => {
      const mockState: ClarificationState = {
        thread_id: 'thread_001',
        status: 'clarifying',
        score: null,
        recommendation: 'interactive',
        questions: [],
        assumptions: [],
        answers: {},
        enriched_task: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockState),
      })

      const result = await fetchClarificationState('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification')
      expect(result).toEqual(mockState)
    })
  })

  describe('fetchClarifierResult', () => {
    it('should GET full clarifier result from v1 API', async () => {
      const mockResult: ClarifierResult = {
        id: 'req_001',
        requirement_text: 'Test requirement',
        structured_summary: null,
        status: 'draft',
        questions: [],
        assumptions: [],
        score_record: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await fetchClarifierResult('req_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001')
      expect(result).toEqual(mockResult)
    })
  })

  describe('submitClarificationAnswers', () => {
    it('should POST answers to clarification endpoint', async () => {
      const mockResponse = { status: 'answered' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitClarificationAnswers({
        thread_id: 'thread_001',
        answers: { q_001: 'answer1', q_002: 'answer2' },
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification/answers', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: { q_001: 'answer1', q_002: 'answer2' },
        }),
      })
      expect(result).toEqual(mockResponse)
    })
  })

  describe('skipClarification', () => {
    it('should POST to skip endpoint', async () => {
      const mockResponse = { status: 'skipped' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await skipClarification('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification/skip', {
        method: 'POST',
      })
      expect(result).toEqual(mockResponse)
    })
  })

  describe('transitionState', () => {
    it('should POST state transition to v1 API', async () => {
      const mockResponse = { status: 'approved' }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await transitionState({
        thread_id: 'thread_001',
        target_status: 'approved',
        reason: 'Requirements are clear',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/tasks/thread_001/transition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_status: 'approved',
          reason: 'Requirements are clear',
        }),
      })
      expect(result).toEqual(mockResponse)
    })

    it('should support rejection transition', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ status: 'rejected' }),
      })

      await transitionState({
        thread_id: 'thread_001',
        target_status: 'rejected',
        reason: 'Requirements too vague',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/tasks/thread_001/transition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_status: 'rejected',
          reason: 'Requirements too vague',
        }),
      })
    })
  })

  describe('calculateScore', () => {
    it('should POST to score calculation endpoint', async () => {
      const mockScore: ScoreRecord = {
        score_id: 'score_001',
        dimensions: { Completeness: 85 },
        weights: { Completeness: 0.15 },
        total_score: 85,
        audit_hash: 'hash123',
        feature_vector: [0.85],
        suggestions: [],
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockScore),
      })

      const result = await calculateScore({
        thread_id: 'thread_001',
        config_version: 'v1',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/score/calculate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: 'thread_001',
          config_version: 'v1',
        }),
      })
      expect(result).toEqual(mockScore)
    })
  })

  describe('getAuditTrail', () => {
    it('should GET audit trail for score', async () => {
      const mockTrail = { score_id: 'score_001', history: [] }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockTrail),
      })

      const result = await getAuditTrail('score_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/score/score_001/audit')
      expect(result).toEqual(mockTrail)
    })
  })

  describe('syncClarificationState', () => {
    it('should GET sync state from v1 API', async () => {
      const mockState: ClarificationState = {
        thread_id: 'thread_001',
        status: 'clarifying',
        score: null,
        recommendation: null,
        questions: [],
        assumptions: [],
        answers: {},
        enriched_task: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockState),
      })

      const result = await syncClarificationState('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/clarify/sync?thread_id=thread_001')
      expect(result).toEqual(mockState)
    })
  })

  describe('submitClarification (Section 8.2)', () => {
    it('should POST clarification answers and trigger re-evaluation', async () => {
      const mockResponse = {
        status: 'clarifying',
        version: 2,
        requires_re_evaluation: true,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitClarification({
        thread_id: 'req_001',
        answers: { q_001: 'answer1' },
        version: 1,
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001/clarify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': '1',
        },
        body: JSON.stringify({
          answers: { q_001: 'answer1' },
          version: 1,
        }),
      })
      expect(result).toEqual(mockResponse)
    })
  })

  describe('getRequirementStatus (Section 8.2)', () => {
    it('should GET current requirement status', async () => {
      const mockResponse = {
        status: 'clarifying',
        version: 2,
        pending_questions: 3,
        total_score: 75,
        last_updated: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await getRequirementStatus('req_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001/status')
      expect(result.status).toBe('clarifying')
      expect(result.pending_questions).toBe(3)
    })
  })

  describe('getRequirementDetail', () => {
    it('should GET full requirement detail', async () => {
      const mockResult: ClarifierResult = {
        id: 'req_001',
        requirement_text: 'Test requirement',
        structured_summary: null,
        status: 'clarifying',
        questions: [],
        assumptions: [],
        score_record: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await getRequirementDetail('req_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001')
      expect(result).toEqual(mockResult)
    })
  })

  describe('triggerReEvaluation', () => {
    it('should POST to trigger re-evaluation', async () => {
      const mockResponse = {
        status: 'scoring',
        evaluation_id: 'eval_001',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await triggerReEvaluation('req_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001/re-evaluate', {
        method: 'POST',
      })
      expect(result.status).toBe('scoring')
    })
  })

  describe('getRequirementVersions', () => {
    it('should GET version history', async () => {
      const mockVersions = [
        { version_no: 1, content_snapshot: 'v1 content', score_snapshot: null, created_at: '2024-01-01' },
        { version_no: 2, content_snapshot: 'v2 content', score_snapshot: { total_score: 75 }, created_at: '2024-01-02' },
      ]
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockVersions),
      })

      const result = await getRequirementVersions('req_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001/versions')
      expect(result).toHaveLength(2)
    })
  })

  describe('diffRequirementVersions', () => {
    it('should GET diff between versions', async () => {
      const mockDiff = {
        added: ['new constraint'],
        removed: ['old constraint'],
        modified: [{ field: 'scope', old: 'v1', new: 'v2' }],
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockDiff),
      })

      const result = await diffRequirementVersions('req_001', 1, 2)

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/requirements/req_001/diff?v1=1&v2=2')
      expect(result.added).toHaveLength(1)
    })
  })

  // ── New Clarification Status APIs (Phase 9 - Section 8.2) ──

  describe('submitClarificationStatus', () => {
    it('should POST clarification status update', async () => {
      const mockResponse = {
        success: true,
        status: 'clarifying' as ClarificationStatus,
        version: 2,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitClarificationStatus({
        thread_id: 'thread_001',
        status: 'clarifying',
        score: 75,
        recommendation: 'interactive',
        version: 1,
        answers: { q_001: 'answer1' },
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/clarification/status', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          thread_id: 'thread_001',
          status: 'clarifying',
          score: 75,
          recommendation: 'interactive',
          version: 1,
          answers: { q_001: 'answer1' },
        }),
      })
      expect(result.success).toBe(true)
    })
  })

  describe('pollClarificationStatus', () => {
    it('should GET polling status for clarification', async () => {
      const mockResponse = {
        status: 'scoring' as ClarificationStatus,
        version: 1,
        score: null,
        recommendation: null as ClarificationRecommendation | null,
        pending_questions: 0,
        last_updated: '2024-01-01T00:00:00Z',
        is_timeout: false,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await pollClarificationStatus('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/clarification/thread_001/status')
      expect(result.status).toBe('scoring')
      expect(result.is_timeout).toBe(false)
    })

    it('should return timeout status when applicable', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'cancelled',
          version: 1,
          score: null,
          recommendation: null,
          pending_questions: 0,
          last_updated: '2024-01-01T00:00:00Z',
          is_timeout: true,
        }),
      })

      const result = await pollClarificationStatus('thread_001')
      expect(result.is_timeout).toBe(true)
    })
  })

  describe('analyzeClarification', () => {
    it('should POST task for clarification analysis', async () => {
      const mockResponse = {
        score: 75,
        recommendation: 'interactive' as ClarificationRecommendation,
        dimensions: {
          Completeness: { score: 70, reason: 'Missing acceptance criteria' },
          Security: { score: 80, reason: 'Authentication requirements unclear' },
        },
        questions: [
          { dimension: 'Completeness', question: 'What are the acceptance criteria?', importance: 'high' },
        ],
        assumptions: [
          { dimension: 'Security', assumption: 'OAuth2 will be used', risk_level: 'medium' },
        ],
        enriched_task: 'Build a user management system with OAuth2...',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await analyzeClarification({
        task: 'Build a user management system',
        task_type: 'development',
        clarification_mode: 'interactive',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/clarification/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          task: 'Build a user management system',
          task_type: 'development',
          clarification_mode: 'interactive',
        }),
      })
      expect(result.score).toBe(75)
      expect(result.recommendation).toBe('interactive')
    })
  })

  describe('reEvaluateClarification', () => {
    it('should POST for re-evaluation with user answers', async () => {
      const mockResponse = {
        score: 85,
        recommendation: 'skip' as ClarificationRecommendation,
        dimensions: {
          Completeness: { score: 90, reason: 'All criteria met' },
        },
        questions: [],
        assumptions: [],
        enriched_task: 'Build a user management system...',
        version: 2,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await reEvaluateClarification({
        original_task: 'Build a user management system',
        user_answers: { q_001: 'OAuth2 with JWT' },
        task_type: 'development',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/clarification/re-evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          original_task: 'Build a user management system',
          user_answers: { q_001: 'OAuth2 with JWT' },
          task_type: 'development',
        }),
      })
      expect(result.score).toBe(85)
      expect(result.version).toBe(2)
    })
  })

  describe('getClarificationDimensions', () => {
    it('should GET clarification dimension definitions', async () => {
      const mockResponse = {
        dimensions: [
          {
            name: 'Completeness',
            label: 'Completeness',
            description: 'How complete is the requirement',
            weight: 0.15,
            example_question: 'What are the acceptance criteria?',
          },
        ],
        default_weights: { Completeness: 0.15 },
        task_type_weights: {
          development: { Completeness: 0.15 },
        },
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await getClarificationDimensions()

      expect(mockFetch).toHaveBeenCalledWith('/api/clarification/dimensions')
      expect(result.dimensions).toHaveLength(1)
      expect(result.default_weights.Completeness).toBe(0.15)
    })
  })

  // ── ClarifierResult APIs (Phase 9 - Section 5.3) ──

  describe('submitClarifyRequest', () => {
    it('should POST clarify request with input and context', async () => {
      const mockResult: ClarifierResult = {
        id: 'session_001',
        requirement_text: 'Build a user management system',
        structured_summary: null,
        status: 'clarifying',
        questions: [],
        assumptions: [],
        clarity_score: 75,
        confidence_score: 0.8,
        next_action: 'ask_user',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await submitClarifyRequest({
        input: 'Build a user management system',
        context: { task_type: 'development' },
        session_id: 'session_001',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/clarify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: 'Build a user management system',
          context: { task_type: 'development' },
          session_id: 'session_001',
          answers: undefined,
        }),
      })
      expect(result.id).toBe('session_001')
      expect(result.next_action).toBe('ask_user')
    })

    it('should POST with answers for re-evaluation', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          id: 'session_001',
          requirement_text: 'Build a user management system',
          structured_summary: null,
          status: 'confirmed',
          questions: [],
          assumptions: [],
          clarity_score: 90,
          confidence_score: 0.95,
          next_action: 'proceed',
          created_at: '2024-01-01T00:00:00Z',
          updated_at: '2024-01-01T00:00:00Z',
        }),
      })

      const result = await submitClarifyRequest({
        input: 'Build a user management system',
        answers: { q_001: 'OAuth2 with JWT' },
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/clarify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          input: 'Build a user management system',
          context: undefined,
          session_id: undefined,
          answers: { q_001: 'OAuth2 with JWT' },
        }),
      })
      expect(result.next_action).toBe('proceed')
    })
  })

  describe('getClarifySession', () => {
    it('should GET clarification session by ID', async () => {
      const mockResult: ClarifierResult = {
        id: 'session_001',
        requirement_text: 'Test requirement',
        structured_summary: {
          objective: 'Test objective',
          scope: ['scope1'],
          constraints: [],
          acceptance_criteria: [],
        },
        status: 'clarifying',
        questions: [],
        assumptions: [],
        clarity_score: 80,
        confidence_score: 0.85,
        next_action: 'ask_user',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await getClarifySession('session_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/clarify/session_001')
      expect(result.id).toBe('session_001')
      expect(result.structured_summary?.objective).toBe('Test objective')
    })

    it('should throw error for non-existent session', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve('Session not found'),
      })

      await expect(getClarifySession('nonexistent')).rejects.toThrow('Session not found')
    })
  })

  describe('processClarifyAnswers', () => {
    it('should POST answers and get updated ClarifierResult', async () => {
      const mockResult: ClarifierResult = {
        id: 'session_001',
        requirement_text: 'Build a user management system',
        structured_summary: null,
        status: 'confirmed',
        questions: [],
        assumptions: [],
        clarity_score: 92,
        confidence_score: 0.95,
        next_action: 'proceed',
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await processClarifyAnswers({
        session_id: 'session_001',
        answers: {
          q_001: 'OAuth2 with JWT',
          q_002: '1000-10000 users',
        },
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/clarify/session_001/answer', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: {
            q_001: 'OAuth2 with JWT',
            q_002: '1000-10000 users',
          },
        }),
      })
      expect(result.status).toBe('confirmed')
      expect(result.next_action).toBe('proceed')
    })
  })

  // ── Score Submission APIs ──

  describe('submitScore', () => {
    it('should POST score with idempotency key', async () => {
      const mockResponse = {
        score_id: 'score_001',
        total_score: 85,
        status: 'confirmed' as ClarificationStatus,
        version: 1,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitScore({
        thread_id: 'thread_001',
        dimensions: {
          completeness: 4,
          consistency: 4,
          feasibility: 5,
          testability: 3,
          priority: 4,
          risk: 3,
          dependency: 4,
          acceptanceCriteria: 4,
          businessValue: 5,
        },
        comment: 'Good requirements',
        idempotency_key: 'ik_test_123',
        version: 1,
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/score/submit', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Idempotency-Key': 'ik_test_123',
        },
        body: JSON.stringify({
          thread_id: 'thread_001',
          dimensions: {
            completeness: 4,
            consistency: 4,
            feasibility: 5,
            testability: 3,
            priority: 4,
            risk: 3,
            dependency: 4,
            acceptanceCriteria: 4,
            businessValue: 5,
          },
          comment: 'Good requirements',
          version: 1,
        }),
      })
      expect(result.score_id).toBe('score_001')
    })
  })

  describe('generateIdempotencyKey', () => {
    it('should generate unique keys', () => {
      const key1 = generateIdempotencyKey()
      const key2 = generateIdempotencyKey()
      expect(key1).toMatch(/^ik_\d+_[a-z0-9]+$/)
      expect(key2).toMatch(/^ik_\d+_[a-z0-9]+$/)
      expect(key1).not.toBe(key2)
    })
  })

  // ── Draft Management APIs ──

  describe('saveDraft', () => {
    it('should PUT draft to server', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({ saved: true, version: 2 }),
      })

      const result = await saveDraft('thread_001', { completeness: 4, feasibility: 5 })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/draft/thread_001', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ dimensions: { completeness: 4, feasibility: 5 } }),
      })
      expect(result.saved).toBe(true)
    })
  })

  describe('loadDraft', () => {
    it('should GET draft from server', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          taskId: 'thread_001',
          dimensions: { completeness: 4 },
          comment: '',
          savedAt: '2024-01-01T00:00:00Z',
          version: 1,
        }),
      })

      const result = await loadDraft('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/draft/thread_001')
      expect(result?.taskId).toBe('thread_001')
    })

    it('should return null for 404', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 404,
        text: () => Promise.resolve('Not found'),
      })

      const result = await loadDraft('nonexistent')
      expect(result).toBeNull()
    })
  })

  describe('deleteDraft', () => {
    it('should DELETE draft', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({}),
      })

      await deleteDraft('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/draft/thread_001', { method: 'DELETE' })
    })
  })

  // ── Local Storage Draft Helpers ──

  describe('saveDraftLocal', () => {
    it('should handle localStorage unavailability gracefully', () => {
      // In Node.js environment, localStorage is not available
      // The function should catch the error and log a warning
      const mockDraft = {
        taskId: 'thread_001',
        dimensions: { completeness: 4 },
        comment: 'Test',
        savedAt: '2024-01-01T00:00:00Z',
        version: 1,
      }
      // Should not throw, just warn
      expect(() => saveDraftLocal(mockDraft)).not.toThrow()
    })
  })

  describe('loadDraftLocal', () => {
    it('should return null when localStorage is unavailable', () => {
      const result = loadDraftLocal('nonexistent')
      expect(result).toBeNull()
    })
  })

  describe('clearDraftLocal', () => {
    it('should handle localStorage unavailability gracefully', () => {
      // Should not throw, just warn
      expect(() => clearDraftLocal('thread_002')).not.toThrow()
    })
  })

  // ── Additional APIs ──

  describe('getClarificationHistory', () => {
    it('should GET clarification history', async () => {
      const mockHistory = [
        {
          id: 'h1',
          task_id: 'thread_001',
          action: 'question_generated' as const,
          details: { question_count: 3 },
          operator_id: 'system',
          created_at: '2024-01-01T00:00:00Z',
        },
      ]
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockHistory),
      })

      const result = await getClarificationHistory('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/tasks/thread_001/clarification/history')
      expect(result).toHaveLength(1)
      expect(result[0].action).toBe('question_generated')
    })
  })

  describe('transitionStateValidated', () => {
    it('should POST validated state transition', async () => {
      const mockResult = {
        success: true,
        from_status: 'clarifying',
        to_status: 'confirmed',
        event: 'MANUAL_CONFIRM' as const,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResult),
      })

      const result = await transitionStateValidated({
        thread_id: 'thread_001',
        target_status: 'confirmed',
        reason: 'All questions answered',
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/tasks/thread_001/transition', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          target_status: 'confirmed',
          reason: 'All questions answered',
        }),
      })
      expect(result.success).toBe(true)
    })
  })

  describe('getClarificationStatus', () => {
    it('should GET current clarification status', async () => {
      const mockResponse = {
        status: 'clarifying',
        version: 2,
        last_updated: '2024-01-01T00:00:00Z',
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await getClarificationStatus('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/v1/tasks/thread_001/status')
      expect(result.status).toBe('clarifying')
      expect(result.version).toBe(2)
    })
  })

  // ── Clarification State Submission & Retrieval APIs (Phase 9 - Section 8.2) ──

  describe('submitClarificationState', () => {
    it('should POST clarification state update to execution', async () => {
      const mockResponse = {
        success: true,
        status: 'clarifying' as ClarificationStatus,
        version: 2,
        current_score: 75,
        current_round: 1,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitClarificationState({
        thread_id: 'thread_001',
        status: 'clarifying',
        score: 75,
        answers: { q_001: 'answer1' },
        current_round: 1,
        version: 1,
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': '1',
        },
        body: JSON.stringify({
          status: 'clarifying',
          score: 75,
          answers: { q_001: 'answer1' },
          current_round: 1,
          version: 1,
        }),
      })
      expect(result.success).toBe(true)
      expect(result.status).toBe('clarifying')
      expect(result.version).toBe(2)
    })

    it('should submit without version header when version is not provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          success: true,
          status: 'confirmed',
          version: 1,
          current_score: 85,
          current_round: 1,
        }),
      })

      await submitClarificationState({
        thread_id: 'thread_001',
        status: 'confirmed',
        score: 85,
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          status: 'confirmed',
          score: 85,
          answers: undefined,
          current_round: undefined,
          version: undefined,
        }),
      })
    })

    it('should throw error on failed request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve('Version conflict'),
      })

      await expect(
        submitClarificationState({
          thread_id: 'thread_001',
          status: 'clarifying',
          version: 1,
        })
      ).rejects.toThrow('Version conflict')
    })
  })

  describe('getClarificationState', () => {
    it('should GET full clarification state for execution', async () => {
      const mockState: ClarificationState = {
        thread_id: 'thread_001',
        status: 'clarifying',
        score: 72.5,
        recommendation: 'interactive',
        questions: [
          {
            q_id: 'q_001',
            dimension: 'functional_scope',
            question: 'What is the expected user capacity?',
            importance: 'high',
            is_resolved: false,
          },
        ],
        assumptions: [
          {
            a_id: 'a_001',
            dimension: 'tech_constraints',
            assumption: 'Default database will be PostgreSQL',
            risk_level: 'medium',
          },
        ],
        answers: {},
        enriched_task: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
        version: 1,
        max_rounds: 3,
        current_round: 1,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockState),
      })

      const result = await getClarificationState('thread_001')

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarification')
      expect(result.thread_id).toBe('thread_001')
      expect(result.status).toBe('clarifying')
      expect(result.score).toBe(72.5)
      expect(result.questions).toHaveLength(1)
      expect(result.assumptions).toHaveLength(1)
      expect(result.version).toBe(1)
      expect(result.max_rounds).toBe(3)
      expect(result.current_round).toBe(1)
    })

    it('should throw error for non-existent execution', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve('Execution not found'),
      })

      await expect(getClarificationState('nonexistent')).rejects.toThrow('Execution not found')
    })
  })

  describe('submitClarifyAnswers', () => {
    it('should POST answers and trigger re-evaluation', async () => {
      const mockResponse = {
        status: 'clarifying' as ClarificationStatus,
        score: 78,
        recommendation: 'interactive' as ClarificationRecommendation,
        questions: [
          {
            q_id: 'q_002',
            dimension: 'tech_constraints',
            question: 'What authentication method?',
            importance: 'medium',
            is_resolved: false,
          },
        ],
        assumptions: [],
        current_round: 2,
        version: 2,
        requires_re_evaluation: true,
      }
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve(mockResponse),
      })

      const result = await submitClarifyAnswers({
        thread_id: 'thread_001',
        answers: { q_001: '1000-10000 users' },
        version: 1,
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'If-Match': '1',
        },
        body: JSON.stringify({
          answers: { q_001: '1000-10000 users' },
          version: 1,
        }),
      })
      expect(result.status).toBe('clarifying')
      expect(result.score).toBe(78)
      expect(result.current_round).toBe(2)
      expect(result.version).toBe(2)
      expect(result.requires_re_evaluation).toBe(true)
    })

    it('should return confirmed status when score meets threshold', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'confirmed',
          score: 85,
          recommendation: 'skip',
          questions: [],
          assumptions: [],
          current_round: 1,
          version: 2,
          requires_re_evaluation: false,
        }),
      })

      const result = await submitClarifyAnswers({
        thread_id: 'thread_001',
        answers: { q_001: 'complete answer' },
        version: 1,
      })

      expect(result.status).toBe('confirmed')
      expect(result.score).toBe(85)
      expect(result.requires_re_evaluation).toBe(false)
    })

    it('should submit without version header when version is not provided', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: true,
        json: () => Promise.resolve({
          status: 'clarifying',
          score: 70,
          recommendation: 'interactive',
          questions: [],
          assumptions: [],
          current_round: 1,
          version: 1,
          requires_re_evaluation: true,
        }),
      })

      await submitClarifyAnswers({
        thread_id: 'thread_001',
        answers: { q_001: 'answer' },
      })

      expect(mockFetch).toHaveBeenCalledWith('/api/executions/thread_001/clarify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          answers: { q_001: 'answer' },
          version: undefined,
        }),
      })
    })

    it('should throw error on failed request', async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        text: () => Promise.resolve('Invalid answers'),
      })

      await expect(
        submitClarifyAnswers({
          thread_id: 'thread_001',
          answers: { q_001: 'answer' },
        })
      ).rejects.toThrow('Invalid answers')
    })
  })
})
