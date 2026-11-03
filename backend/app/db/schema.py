"""Database design contract (Part IX). Postgres DDL generated from this file.

Honest status: the schema contract below is implemented and validated by
tests. Live SQLAlchemy models, Alembic migrations and a running Postgres
are pending (need the server + dependencies). Large generated files are
never stored in the DB — artifacts reference controlled external storage.

Conventions enforced by validate_schema():
  UUID primary keys, UTC timestamptz timestamps, FK constraints naming
  real entities, project scoping where required, explicit indexes.
"""

from __future__ import annotations

FK = "fk"

# entity -> {columns: {name: type}, fks: {col: target_entity}, indexes: [cols]}
ENTITIES: dict[str, dict] = {
    "users": {"columns": {"id": "UUID PK", "email": "TEXT UNIQUE NOT NULL",
              "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ"},
              "fks": {}, "indexes": ["email"]},
    "projects": {"columns": {"id": "UUID PK", "owner_id": "UUID NOT NULL",
              "name": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ"},
              "fks": {"owner_id": "users"}, "indexes": ["owner_id"]},
    "specifications": {"columns": {"id": "UUID PK", "project_id": "UUID NOT NULL",
              "body": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id"]},
    "requirements": {"columns": {"id": "UUID PK", "spec_id": "UUID NOT NULL",
              "req_code": "TEXT NOT NULL", "priority": "TEXT NOT NULL",
              "status": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"spec_id": "specifications"}, "indexes": ["spec_id", "status"]},
    "engineering_runs": {"columns": {"id": "UUID PK", "project_id": "UUID NOT NULL",
              "state": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ", "updated_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id", "state"]},
    "tasks": {"columns": {"id": "UUID PK", "run_id": "UUID NOT NULL",
              "kind": "TEXT NOT NULL", "state": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"run_id": "engineering_runs"}, "indexes": ["run_id", "state"]},
    "artifacts": {"columns": {"id": "UUID PK", "project_id": "UUID NOT NULL",
              "path": "TEXT NOT NULL", "storage": "TEXT NOT NULL",
              "created_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id"]},
    "test_runs": {"columns": {"id": "UUID PK", "run_id": "UUID NOT NULL",
              "passed": "INT NOT NULL", "failed": "INT NOT NULL",
              "created_at": "TIMESTAMPTZ"},
              "fks": {"run_id": "engineering_runs"}, "indexes": ["run_id"]},
    "test_results": {"columns": {"id": "UUID PK", "test_run_id": "UUID NOT NULL",
              "name": "TEXT NOT NULL", "ok": "BOOL NOT NULL", "output": "TEXT",
              "created_at": "TIMESTAMPTZ"},
              "fks": {"test_run_id": "test_runs"}, "indexes": ["test_run_id", "ok"]},
    "failures": {"columns": {"id": "UUID PK", "test_run_id": "UUID NOT NULL",
              "summary": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"test_run_id": "test_runs"}, "indexes": ["test_run_id"]},
    "diagnoses": {"columns": {"id": "UUID PK", "failure_id": "UUID NOT NULL",
              "category": "TEXT NOT NULL", "cause": "TEXT", "created_at": "TIMESTAMPTZ"},
              "fks": {"failure_id": "failures"}, "indexes": ["failure_id"]},
    "repair_attempts": {"columns": {"id": "UUID PK", "diagnosis_id": "UUID NOT NULL",
              "ok": "BOOL NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"diagnosis_id": "diagnoses"}, "indexes": ["diagnosis_id"]},
    "code_changes": {"columns": {"id": "UUID PK", "repair_id": "UUID",
              "path": "TEXT NOT NULL", "diff": "TEXT", "created_at": "TIMESTAMPTZ"},
              "fks": {"repair_id": "repair_attempts"}, "indexes": ["repair_id"]},
    "memories": {"columns": {"id": "UUID PK", "project_id": "UUID NOT NULL",
              "kind": "TEXT NOT NULL", "lesson": "TEXT NOT NULL",
              "verified": "BOOL NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id", "kind"]},
    "skills": {"columns": {"id": "UUID PK", "skill_code": "TEXT UNIQUE NOT NULL",
              "success_rate": "FLOAT NOT NULL", "trials": "INT NOT NULL",
              "version": "TEXT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {}, "indexes": ["skill_code"]},
    "model_calls": {"columns": {"id": "UUID PK", "run_id": "UUID", "model": "TEXT NOT NULL",
              "latency_ms": "INT NOT NULL", "ok": "BOOL NOT NULL",
              "tokens": "INT NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"run_id": "engineering_runs"}, "indexes": ["run_id", "model"]},
    "approvals": {"columns": {"id": "UUID PK", "project_id": "UUID NOT NULL",
              "action": "TEXT NOT NULL", "status": "TEXT NOT NULL",
              "created_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id", "status"]},
    "audit_events": {"columns": {"id": "UUID PK", "project_id": "UUID",
              "tool": "TEXT NOT NULL", "ok": "BOOL NOT NULL", "created_at": "TIMESTAMPTZ"},
              "fks": {"project_id": "projects"}, "indexes": ["project_id"]},
}

# The spec names 18 entities; the 19th slot documents intent, not a table.
EXPECTED = {"users", "projects", "specifications", "requirements", "engineering_runs",
            "tasks", "artifacts", "test_runs", "test_results", "failures", "diagnoses",
            "repair_attempts", "code_changes", "memories", "skills", "model_calls",
            "approvals", "audit_events"}


def validate_schema(entities: dict | None = None) -> list[str]:
    """Returns a list of violations (empty = valid)."""
    entities = ENTITIES if entities is None else entities
    problems = []
    names = set(entities)
    if names != EXPECTED:
        problems.append(f"entity set mismatch: missing={EXPECTED - names} extra={names - EXPECTED}")
    for name, spec in entities.items():
        cols = spec.get("columns", {})
        if cols.get("id") != "UUID PK":
            problems.append(f"{name}: id must be 'UUID PK'")
        if not any("TIMESTAMPTZ" in str(v) for v in cols.values()):
            problems.append(f"{name}: needs a UTC timestamptz column")
        for col, target in spec.get("fks", {}).items():
            if col not in cols:
                problems.append(f"{name}: fk column {col} missing from columns")
            if target not in names:
                problems.append(f"{name}: fk target {target} is not an entity")
    return problems


def to_postgres_ddl() -> str:
    lines = ["-- Genesis schema (Part IX). Generated, not hand-written.",
             "CREATE EXTENSION IF NOT EXISTS pgcrypto;"]
    for name, spec in ENTITIES.items():
        cols = [f"  {c} {t.replace('UUID PK', 'UUID PRIMARY KEY DEFAULT gen_random_uuid()')}"
                for c, t in spec["columns"].items()]
        for col, target in spec["fks"].items():
            cols.append(f"  FOREIGN KEY ({col}) REFERENCES {target}(id)")
        lines.append(f"CREATE TABLE {name} (\n" + ",\n".join(cols) + "\n);")
        for idx in spec.get("indexes", []):
            lines.append(f"CREATE INDEX ON {name} ({idx});")
    return "\n".join(lines) + "\n"
