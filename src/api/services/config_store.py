"""Config management service — SQLite-backed configuration storage."""

import json
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml


@dataclass
class WorkflowConfig:
    name: str
    description: str
    yaml_content: str
    created_at: float
    updated_at: float


@dataclass
class AgentConfig:
    id: str
    name: str
    description: str
    capabilities: list[str]
    model: str
    enabled: bool
    created_at: float
    updated_at: float


@dataclass
class VerifierRule:
    id: str
    name: str
    condition: str
    threshold: float
    action: str
    severity: str
    enabled: bool
    created_at: float
    updated_at: float


# Default agent registry (Phase 4: read-only discovery + model/enabled config)
_DEFAULT_AGENTS: list[dict] = [
    {
        "id": "requirements_agent",
        "name": "Requirements Agent",
        "description": "Generates requirements documents from task descriptions",
        "capabilities": ["requirements_generation", "task_analysis"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
    {
        "id": "design_agent",
        "name": "Design Agent",
        "description": "Creates technical design documents",
        "capabilities": ["design_generation", "architecture"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
    {
        "id": "develop_agent",
        "name": "Develop Agent",
        "description": "Writes code based on design documents",
        "capabilities": ["code_generation", "implementation"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
    {
        "id": "review_agent",
        "name": "Review Agent",
        "description": "Reviews code for quality and best practices",
        "capabilities": ["code_review", "quality_check"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
    {
        "id": "test_agent",
        "name": "Test Agent",
        "description": "Generates and runs tests",
        "capabilities": ["test_generation", "test_execution"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
    {
        "id": "fix_agent",
        "name": "Fix Agent",
        "description": "Fixes bugs based on review/test feedback",
        "capabilities": ["bug_fixing", "refactoring"],
        "model": "qwen3.6-plus",
        "enabled": True,
    },
]


class ConfigStore:
    """SQLite-backed configuration storage."""

    def __init__(self, db_path: str = "./checkpoints/config.db"):
        self._db_path = db_path
        self._local = threading.local()
        self._write_lock = threading.Lock()
        self._ensure_db()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            conn = sqlite3.connect(self._db_path)
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
            self._create_tables(conn)
        return self._local.conn

    def _ensure_db(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        conn = self._get_conn()
        self._create_tables(conn)

    def _create_tables(self, conn: sqlite3.Connection) -> None:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS workflow_configs (
                name TEXT PRIMARY KEY,
                description TEXT NOT NULL DEFAULT '',
                yaml_content TEXT NOT NULL,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS agent_configs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                capabilities TEXT NOT NULL DEFAULT '[]',
                model TEXT NOT NULL DEFAULT '',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS verifier_rules (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                condition TEXT NOT NULL,
                threshold REAL NOT NULL DEFAULT 0,
                action TEXT NOT NULL,
                severity TEXT NOT NULL DEFAULT 'medium',
                enabled INTEGER NOT NULL DEFAULT 1,
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL
            );
        """)
        conn.commit()
        # Seed default agents if empty
        count = conn.execute("SELECT COUNT(*) FROM agent_configs").fetchone()[0]
        if count == 0:
            now = time.time()
            for agent in _DEFAULT_AGENTS:
                conn.execute(
                    "INSERT INTO agent_configs (id, name, description, capabilities, model, enabled, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        agent["id"], agent["name"], agent["description"],
                        json.dumps(agent["capabilities"]),
                        agent["model"], 1 if agent["enabled"] else 0,
                        now, now,
                    ),
                )
            conn.commit()

    # ── Workflow Configs ──

    def list_workflows(self) -> list[WorkflowConfig]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM workflow_configs ORDER BY name").fetchall()
        return [WorkflowConfig(**dict(r)) for r in rows]

    def get_workflow(self, name: str) -> Optional[WorkflowConfig]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM workflow_configs WHERE name = ?", (name,)).fetchone()
        if row is None:
            return None
        return WorkflowConfig(**dict(row))

    def upsert_workflow(self, name: str, yaml_content: str, description: str = "") -> Optional[WorkflowConfig]:
        """Parse and validate YAML, then store. Returns WorkflowConfig or raises ValueError."""
        try:
            parsed = yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML syntax: {e}")

        if not isinstance(parsed, dict):
            raise ValueError("YAML must be a mapping")
        if "nodes" not in parsed:
            raise ValueError("YAML must contain 'nodes' field")
        if not isinstance(parsed["nodes"], list):
            raise ValueError("'nodes' must be a list")
        if "edges" not in parsed:
            raise ValueError("YAML must contain 'edges' field")

        now = time.time()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO workflow_configs (name, description, yaml_content, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT(name) DO UPDATE SET yaml_content = excluded.yaml_content, "
                "description = excluded.description, updated_at = excluded.updated_at",
                (name, description or parsed.get("description", ""), yaml_content, now, now),
            )
            conn.commit()

        return self.get_workflow(name)

    # ── Agent Configs ──

    def list_agents(self) -> list[AgentConfig]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM agent_configs ORDER BY name").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["capabilities"] = json.loads(d["capabilities"])
            d["enabled"] = bool(d["enabled"])
            result.append(AgentConfig(**d))
        return result

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM agent_configs WHERE id = ?", (agent_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["capabilities"] = json.loads(d["capabilities"])
        d["enabled"] = bool(d["enabled"])
        return AgentConfig(**d)

    def update_agent(self, agent_id: str, model: Optional[str] = None, enabled: Optional[bool] = None) -> Optional[AgentConfig]:
        with self._write_lock:
            conn = self._get_conn()
            updates = []
            values = []
            if model is not None:
                updates.append("model = ?")
                values.append(model)
            if enabled is not None:
                updates.append("enabled = ?")
                values.append(1 if enabled else 0)
            if not updates:
                return self.get_agent(agent_id)
            updates.append("updated_at = ?")
            values.append(time.time())
            values.append(agent_id)

            conn.execute(
                f"UPDATE agent_configs SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()

        return self.get_agent(agent_id)

    # ── Verifier Rules ──

    def list_verifiers(self) -> list[VerifierRule]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM verifier_rules ORDER BY created_at").fetchall()
        result = []
        for r in rows:
            d = dict(r)
            d["enabled"] = bool(d["enabled"])
            result.append(VerifierRule(**d))
        return result

    def create_verifier(
        self, name: str, condition: str, threshold: float, action: str, severity: str = "medium"
    ) -> VerifierRule:
        rule_id = f"rule_{uuid.uuid4().hex[:8]}"
        now = time.time()
        with self._write_lock:
            conn = self._get_conn()
            conn.execute(
                "INSERT INTO verifier_rules (id, name, condition, threshold, action, severity, enabled, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)",
                (rule_id, name, condition, threshold, action, severity, now, now),
            )
            conn.commit()
        rule = self.get_verifier(rule_id)
        assert rule is not None
        return rule

    def get_verifier(self, rule_id: str) -> Optional[VerifierRule]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM verifier_rules WHERE id = ?", (rule_id,)).fetchone()
        if row is None:
            return None
        d = dict(row)
        d["enabled"] = bool(d["enabled"])
        return VerifierRule(**d)

    def update_verifier(
        self, rule_id: str, threshold: Optional[float] = None,
        enabled: Optional[bool] = None, action: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> Optional[VerifierRule]:
        with self._write_lock:
            conn = self._get_conn()
            updates = []
            values = []
            if threshold is not None:
                updates.append("threshold = ?")
                values.append(threshold)
            if enabled is not None:
                updates.append("enabled = ?")
                values.append(1 if enabled else 0)
            if action is not None:
                updates.append("action = ?")
                values.append(action)
            if severity is not None:
                updates.append("severity = ?")
                values.append(severity)
            if not updates:
                return self.get_verifier(rule_id)
            updates.append("updated_at = ?")
            values.append(time.time())
            values.append(rule_id)

            conn.execute(
                f"UPDATE verifier_rules SET {', '.join(updates)} WHERE id = ?",
                values,
            )
            conn.commit()

        return self.get_verifier(rule_id)

    def delete_verifier(self, rule_id: str) -> bool:
        with self._write_lock:
            conn = self._get_conn()
            cursor = conn.execute("DELETE FROM verifier_rules WHERE id = ?", (rule_id,))
            conn.commit()
        return cursor.rowcount > 0
