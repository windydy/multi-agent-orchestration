/**
 * Tests for Phase 9 Clarification Types
 * Validates type definitions and interfaces aligned with Technical Design
 */
import { describe, it, expect } from 'vitest'
import type {
  ClarificationStatus,
  ClarificationRecommendation,
  ScoringDimension,
  ClarificationQuestion,
  Assumption,
  ScoreRecord,
  ClarifierResult,
  ClarificationState,
  CreateExecutionRequest,
  SubmitClarificationAnswersRequest,
  RequirementStatus,
  StateMachineEvent,
  TaskStatus,
  ClarificationMode,
  ClarificationModeInfo,
  ClarifierUIState,
  ClarifierQuestion,
  ClarifierAssumption,
  ClarifierResultV2,
  ClarifierStoreState,
} from '../types'
import {
  CLARIFICATION_MODE_METADATA,
  DEFAULT_WEIGHTS,
  SCORE_THRESHOLD,
} from '../types'

describe('Clarification Types', () => {
  describe('RequirementStatus (Section 8.1 State Machine)', () => {
    it('should accept all valid FSM status values', () => {
      const validStatuses: RequirementStatus[] = [
        'draft',
        'scoring',
        'clarifying',
        'confirmed',
        'in_development',
        'completed',
        'cancelled',
        'needs_clarification',
      ]
      expect(validStatuses).toHaveLength(8)
    })

    it('should follow state machine transitions', () => {
      // DRAFT → SCORING → CLARIFYING → CONFIRMED → IN_DEVELOPMENT → COMPLETED
      const transition: RequirementStatus[] = [
        'draft',
        'scoring',
        'clarifying',
        'confirmed',
        'in_development',
        'completed',
      ]
      expect(transition).toHaveLength(6)
    })
  })

  describe('TaskStatus', () => {
    it('should include both FSM and legacy statuses', () => {
      const statuses: TaskStatus[] = [
        'draft',
        'scoring',
        'clarifying',
        'confirmed',
        'pending',
        'running',
        'success',
        'failed',
      ]
      expect(statuses.length).toBeGreaterThan(0)
    })
  })

  describe('StateMachineEvent (Section 8.1)', () => {
    it('should accept all valid event values', () => {
      const validEvents: StateMachineEvent[] = [
        'SUBMIT_FOR_EVALUATION',
        'EVALUATION_COMPLETE',
        'ANSWER_CLARIFICATION',
        'AUTO_CONFIRM',
        'MANUAL_CONFIRM',
        'HANDOFF_TO_DEV',
        'ARCHIVE',
        'TIMEOUT',
        'CANCEL',
        'REJECT',
      ]
      expect(validEvents).toHaveLength(10)
    })
  })

  describe('ClarificationStatus', () => {
    it('should accept all valid status values including legacy', () => {
      const validStatuses: ClarificationStatus[] = [
        'draft',
        'scoring',
        'clarifying',
        'confirmed',
        'in_development',
        'completed',
        'cancelled',
        'needs_clarification',
        // Legacy
        'scored',
        'approved',
        'rejected',
        'pending',
        'analyzing',
        'questions_ready',
        'answered',
        'skipped',
        'conservative',
      ]
      expect(validStatuses.length).toBeGreaterThanOrEqual(17)
    })
  })

  describe('ClarificationRecommendation', () => {
    it('should accept all valid recommendation values', () => {
      const validRecommendations: ClarificationRecommendation[] = [
        'skip',
        'conservative',
        'interactive',
      ]
      expect(validRecommendations).toHaveLength(3)
    })
  })

  describe('ScoringDimension', () => {
    it('should include all 9 dimensions from technical design', () => {
      const dimensions: ScoringDimension[] = [
        'functional_scope',
        'tech_constraints',
        'quality_reqs',
        'target_users',
        'timeline',
        'integration',
        'success_criteria',
        'budget',
        'context',
      ]
      expect(dimensions).toHaveLength(9)
    })
  })

  describe('ClarificationQuestion', () => {
    it('should create valid question object with new fields', () => {
      const question: ClarificationQuestion = {
        q_id: 'q_001',
        dimension: 'functional_scope',
        question: 'What is the expected user capacity?',
        importance: 'high',
        options: ['100-1000', '1000-10000', '10000+'],
        user_answer: '1000-10000',
        is_resolved: false,
      }
      expect(question.q_id).toBe('q_001')
      expect(question.importance).toBe('high')
      expect(question.is_resolved).toBe(false)
    })

    it('should support free-text questions without options', () => {
      const question: ClarificationQuestion = {
        q_id: 'q_002',
        dimension: 'tech_constraints',
        question: 'Describe authentication requirements',
        importance: 'medium',
        is_resolved: false,
      }
      expect(question.options).toBeUndefined()
    })

    it('should support legacy priority field for backward compatibility', () => {
      const question: ClarificationQuestion = {
        q_id: 'q_003',
        dimension: 'quality_reqs',
        content: 'Legacy question text',
        priority: 1,
        is_resolved: false,
      }
      expect(question.content).toBe('Legacy question text')
      expect(question.priority).toBe(1)
    })
  })

  describe('Assumption', () => {
    it('should create valid assumption object with new fields', () => {
      const assumption: Assumption = {
        a_id: 'a_001',
        dimension: 'tech_constraints',
        assumption: 'Default database will be PostgreSQL',
        risk_level: 'medium',
        source: 'system_inferred',
        confirmed: false,
      }
      expect(assumption.a_id).toBe('a_001')
      expect(assumption.dimension).toBe('tech_constraints')
      expect(assumption.risk_level).toBe('medium')
    })

    it('should support user_confirmed source', () => {
      const assumption: Assumption = {
        a_id: 'a_002',
        dimension: 'timeline',
        assumption: 'API rate limit is 1000 req/min',
        risk_level: 'low',
        source: 'user_confirmed',
        confirmed: true,
      }
      expect(assumption.confirmed).toBe(true)
    })

    it('should support legacy fields for backward compatibility', () => {
      const assumption: Assumption = {
        a_id: 'a_003',
        dimension: 'budget',
        text: 'Legacy assumption text',
        content: 'Legacy content',
        impact_level: 'medium',
        risk_level: 'medium',
        confirmed: false,
      }
      expect(assumption.text).toBe('Legacy assumption text')
      expect(assumption.impact_level).toBe('medium')
    })
  })

  describe('ScoreRecord', () => {
    it('should create valid score record with new dimensions', () => {
      const scoreRecord: ScoreRecord = {
        score_id: 'score_001',
        dimensions: {
          functional_scope: 85,
          tech_constraints: 90,
          quality_reqs: 80,
          target_users: 75,
          timeline: 70,
          integration: 80,
          success_criteria: 85,
          budget: 75,
          context: 90,
        },
        weights: {
          functional_scope: 1.5,
          tech_constraints: 1.5,
          quality_reqs: 1.2,
          target_users: 1.0,
          timeline: 1.0,
          integration: 1.0,
          success_criteria: 1.0,
          budget: 0.8,
          context: 0.8,
        },
        total_score: 81.5,
        audit_hash: 'abc123def456',
        feature_vector: [0.85, 0.9, 0.8, 0.75, 0.7, 0.8, 0.85, 0.75, 0.9],
        suggestions: ['Add more test coverage', 'Consider caching strategy'],
      }
      expect(scoreRecord.total_score).toBe(81.5)
      expect(Object.keys(scoreRecord.dimensions)).toHaveLength(9)
    })
  })

  describe('ClarifierResult', () => {
    it('should create full clarification result', () => {
      const result: ClarifierResult = {
        id: 'req_001',
        requirement_text: 'Build a user management system',
        structured_summary: {
          objective: 'Create CRUD operations for users',
          scope: ['user registration', 'login', 'profile management'],
          constraints: ['Must use OAuth2', 'GDPR compliant'],
          acceptance_criteria: ['All endpoints tested', '99.9% uptime'],
        },
        status: 'clarifying',
        questions: [],
        assumptions: [],
        score_record: null,
        created_at: '2024-01-01T00:00:00Z',
        updated_at: '2024-01-01T00:00:00Z',
      }
      expect(result.id).toBe('req_001')
      expect(result.status).toBe('clarifying')
      expect(result.structured_summary?.objective).toBe('Create CRUD operations for users')
    })
  })

  describe('ClarificationState', () => {
    it('should create valid clarification state', () => {
      const state: ClarificationState = {
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
      expect(state.thread_id).toBe('thread_001')
      expect(state.status).toBe('clarifying')
    })

    it('should support legacy status values', () => {
      const legacyStatuses: ClarificationState['status'][] = [
        'pending',
        'analyzing',
        'questions_ready',
        'answered',
        'skipped',
        'conservative',
      ]
      expect(legacyStatuses).toHaveLength(6)
    })
  })

  describe('CreateExecutionRequest', () => {
    it('should create valid request with clarification mode', () => {
      const request: CreateExecutionRequest = {
        task: 'Build a REST API',
        workflow: 'default',
        clarification_mode: 'interactive',
        max_iterations: 10,
      }
      expect(request.task).toBe('Build a REST API')
      expect(request.clarification_mode).toBe('interactive')
    })

    it('should support all clarification modes', () => {
      const modes: CreateExecutionRequest['clarification_mode'][] = [
        'auto',
        'conservative',
        'interactive',
      ]
      expect(modes).toHaveLength(3)
    })
  })

  describe('SubmitClarificationAnswersRequest', () => {
    it('should create valid answers request', () => {
      const request: SubmitClarificationAnswersRequest = {
        thread_id: 'thread_001',
        answers: {
          q_001: '1000-10000',
          q_002: 'OAuth2 with JWT',
        },
      }
      expect(Object.keys(request.answers)).toHaveLength(2)
    })
  })

  // ── Clarification Mode Metadata Tests ──

  describe('ClarificationMode', () => {
    it('should accept all valid mode values', () => {
      const modes: ClarificationMode[] = ['auto', 'conservative', 'interactive']
      expect(modes).toHaveLength(3)
    })
  })

  describe('CLARIFICATION_MODE_METADATA', () => {
    it('should have metadata for all three modes', () => {
      expect(Object.keys(CLARIFICATION_MODE_METADATA)).toHaveLength(3)
      expect(CLARIFICATION_MODE_METADATA.auto).toBeDefined()
      expect(CLARIFICATION_MODE_METADATA.conservative).toBeDefined()
      expect(CLARIFICATION_MODE_METADATA.interactive).toBeDefined()
    })

    it('should have correct structure for each mode', () => {
      const modes: ClarificationMode[] = ['auto', 'conservative', 'interactive']
      for (const mode of modes) {
        const info: ClarificationModeInfo = CLARIFICATION_MODE_METADATA[mode]
        expect(info.mode).toBe(mode)
        expect(info.icon).toBeDefined()
        expect(info.title).toBeDefined()
        expect(info.desc).toBeDefined()
        expect(info.detail).toBeDefined()
        expect(info.workflow).toBeDefined()
      }
    })

    it('should have correct auto mode metadata', () => {
      const auto = CLARIFICATION_MODE_METADATA.auto
      expect(auto.icon).toBe('⚡')
      expect(auto.title).toBe('Auto')
      expect(auto.desc).toBe('AI decides')
      expect(auto.workflow).toContain('DRAFT')
      expect(auto.workflow).toContain('SCORING')
    })

    it('should have correct conservative mode metadata', () => {
      const conservative = CLARIFICATION_MODE_METADATA.conservative
      expect(conservative.icon).toBe('🛡️')
      expect(conservative.title).toBe('Conservative')
      expect(conservative.desc).toBe('Safe defaults')
      expect(conservative.workflow).toContain('apply assumptions')
    })

    it('should have correct interactive mode metadata', () => {
      const interactive = CLARIFICATION_MODE_METADATA.interactive
      expect(interactive.icon).toBe('💬')
      expect(interactive.title).toBe('Interactive')
      expect(interactive.desc).toBe('Ask questions')
      expect(interactive.workflow).toContain('answer questions')
    })
  })

  describe('DEFAULT_WEIGHTS', () => {
    it('should have all 9 dimensions from technical design Section 5.5', () => {
      expect(Object.keys(DEFAULT_WEIGHTS)).toHaveLength(9)
    })

    it('should have weights that sum to 9.8 (Section 5.5)', () => {
      const sum = Object.values(DEFAULT_WEIGHTS).reduce((a, b) => a + b, 0)
      expect(sum).toBeCloseTo(9.8, 2)
    })

    it('should have correct weight values from technical design', () => {
      expect(DEFAULT_WEIGHTS.functional_scope).toBe(1.5)
      expect(DEFAULT_WEIGHTS.tech_constraints).toBe(1.5)
      expect(DEFAULT_WEIGHTS.quality_reqs).toBe(1.2)
      expect(DEFAULT_WEIGHTS.target_users).toBe(1.0)
      expect(DEFAULT_WEIGHTS.timeline).toBe(1.0)
      expect(DEFAULT_WEIGHTS.integration).toBe(1.0)
      expect(DEFAULT_WEIGHTS.success_criteria).toBe(1.0)
      expect(DEFAULT_WEIGHTS.budget).toBe(0.8)
      expect(DEFAULT_WEIGHTS.context).toBe(0.8)
    })
  })

  describe('SCORE_THRESHOLD', () => {
    it('should be 80 (Section 7.2 - skip mode threshold)', () => {
      expect(SCORE_THRESHOLD).toBe(80)
    })
  })
})
