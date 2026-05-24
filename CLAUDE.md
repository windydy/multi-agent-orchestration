# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Multi-Agent Orchestration — a Python + LangGraph runtime that decomposes software-engineering tasks into a DAG, matches nodes to Agent executors, and runs them through a FastAPI backend with a Vite/React dashboard. This is not a single chat agent; it is a "development pipeline runtime" (Planner → PlanGraph → DynamicWorkflowBuilder → ExecutorRegistry → Agents/Tools).

## Common Commands

### Backend (Python ≥ 3.11)

```bash
# Install (creates .venv, installs Python + web deps)
scripts/install.sh --build-web
source .venv/bin/activate

# Production install (no dev deps)
scripts/install.sh --prod --build-web

# Backend-only (skip web)
scripts/install.sh --no-web
```

### Running

```bash
# CLI
python -m src.cli.main run "<task>" --path ./demo_project --no-review
python -m src.cli.main status <thread_id>
python -m src.cli.main resume <thread_id> --approve --comment "ok"
# CLI writes last thread id to .pipeline_thread_YYYYMMDD.txt

# API + Dashboard (mounts web/dist if built)
python -m uvicorn src.api.server:app --reload --host 0.0.0.0 --port 8000
```

### Tests / Lint

```bash
# Canonical test command (skips UI + knowledge — they need extra deps/services)
.venv/bin/python -m pytest tests/ --ignore=tests/ui/ --ignore=tests/knowledge/

# Subsets
pytest tests/api -v
pytest tests/knowledge -v
pytest tests/test_phase9_clarifier.py::TestClarifier::test_name -v   # single test
pytest --cov=src --cov-report=term-missing

# Lint / types
ruff check src tests
mypy src
```

Pytest is configured with `asyncio_mode = "auto"` — async tests do not need explicit `@pytest.mark.asyncio`.

### Frontend

```bash
cd web
npm install
npm run dev          # Vite dev server
npm run build        # tsc -b && vite build → web/dist (served by FastAPI)
npm run test         # vitest run
```

### Packaging

```bash
scripts/package.sh --version local
# → dist/packages/multi-agent-orchestration-local.tar.gz(.sha256)
```

Docker (`docker compose --profile dev up dev`) is not currently working out-of-the-box — the Dockerfile expects `requirements.txt` but the source of truth is `pyproject.toml`. Use the local venv path until that is reconciled.

## Model Credentials

The Planner prefers DashScope's Anthropic-compatible API, falling back to native Anthropic:

```bash
export DASHSCOPE_API_KEY="..."   # preferred
export ANTHROPIC_API_KEY="..."   # fallback
```

`PlannerAgent` also probes `~/.hermes/config.yaml` for compatible API settings.

## Architecture

The pipeline composes five layers — changes should slot into one of them rather than reach across:

```
PlanGraph(DAG) → DynamicWorkflowBuilder(LangGraph) → ExecutorRegistry → Agent/Tool → Checkpoint+Memory+Observability
```

1. **`src/plan/`** — `PlannerAgent` turns a user task into `PlanGraph`/`PlanNode` with `ExecutorCapability` requirements; the graph must be acyclic.
2. **`src/workflows/`** — `dynamic_builder.py` compiles the DAG into a LangGraph `StateGraph`; `runner.py` is the unified execution entrypoint with verify/retry/replan loops. Both are listed as **protected** files in `AGENTS.md` (no autonomous changes).
3. **`src/executors/`** — `ExecutorRegistry` matches nodes to executors by declared capabilities. Add new abilities by extending `ExecutorCapability` first, then wiring an executor.
4. **`src/agents/`** — Python Agent classes plus `loader.py`, which reads Markdown Agent definitions from the repo-root `agents/` directory (YAML frontmatter + system prompt body). Agent names must be stable; `tools` is a list, never a comma-string.
5. **`src/api/`** — FastAPI app (`server.py` is protected) with routes/services/WebSocket. The web UI consumes these; when changing response shape, update `web/src/lib/api.ts` and `web/src/types/` in the same change.

Crosscutting modules: `src/config/` (YAML workflow schema in `schema.py` — change schema → loader → example YAML → tests in lockstep), `src/clarifier/` (Phase 9 requirement clarification), `src/knowledge/` (SQLite-backed agent memory, optional embeddings), `src/observability/`, `src/resilience/`, `src/cost/`, `src/integrations/` (GitHub/Jira/Slack), `src/workspace/` (multi-project `.workspace.yaml`), `src/claude/` (Anthropic SDK wrapper + tool registry + safety hooks).

Workflow YAMLs in `config/workflows/` (see `phase8-bootstrap.yaml`) describe planner/executors/flow_template/verifiers/human_review/cost_control/checkpoint — validate via the schema loader, ensure entry point exists, dependencies exist, and the flow is acyclic.

State written to LangGraph workflow state **must be serializable** (checkpoint recovery depends on it). Use async for long tasks, external APIs, and I/O.

## Safety Boundaries (from AGENTS.md)

**Protected — do not autonomously modify:**
- `src/core/` — Agent/Workflow/Tool minimal contracts
- `src/workflows/runner.py`, `src/workflows/dynamic_builder.py`
- `src/api/server.py`
- `pyproject.toml`, `web/package.json`

**Modify only with matching test update:**
- `src/agents/` ↔ agent tests · `src/api/routes/` ↔ route integration tests · `src/executors/` ↔ executor tests · `src/clarifier/` ↔ clarifier tests · `src/knowledge/` ↔ knowledge tests

**Self-dev mode**: structural changes happen in a `git worktree` (`feature/{desc}` or `fix/{desc}`), then lint + tests + report + human review before merge. See `docs/self-dev/README.md`.

## Per-Directory Context

Each major subdirectory has its own `AGENTS.md` (e.g., `src/api/AGENTS.md`, `src/plan/AGENTS.md`, `web/AGENTS.md`). Read the local `AGENTS.md` before editing inside a subdirectory — it constrains both the design rules and the test obligations for that area.

## Code Navigation Strategy (gitnexus + grep)

gitnexus and `rg`/`Read` are complementary. Benchmarked on this repo: gitnexus is ~3× faster for structural questions; grep wins on exact line numbers and dynamic dispatch. Token cost is roughly equal.

| Task | Use |
|---|---|
| Architecture, execution flows, callers, impact | gitnexus (`query` / `context` / `impact` / `detect_changes`) |
| Exact line number for editing | `rg` (gitnexus lines reflect last `analyze`, not HEAD) |
| Dynamic dispatch — LangGraph `ainvoke`, `executor.execute()`, decorators, `getattr` | `rg` |
| Working tree is dirty OR index warns "stale" | `rg`, or re-run `gitnexus analyze` |

**Workflow**: start with gitnexus for shape → cross-check with `rg`+`Read` for line numbers and dynamic call sites. When they disagree on line numbers, trust grep.

**Known blind spot**: the `WorkflowRunner.run` → `app.ainvoke()` → node closure → `executor.execute()` → `agent.run()` chain is partially invisible to gitnexus CALLS edges. Supplement with `rg` for traces through this chain.

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **multi-agent-orchestration** (7753 symbols, 13822 relationships, 222 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> If any GitNexus tool warns the index is stale, run `npx gitnexus analyze` in terminal first.

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `gitnexus_impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `gitnexus_detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `gitnexus_query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `gitnexus_context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `gitnexus_impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `gitnexus_rename` which understands the call graph.
- NEVER commit changes without running `gitnexus_detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/multi-agent-orchestration/context` | Codebase overview, check index freshness |
| `gitnexus://repo/multi-agent-orchestration/clusters` | All functional areas |
| `gitnexus://repo/multi-agent-orchestration/processes` | All execution flows |
| `gitnexus://repo/multi-agent-orchestration/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
