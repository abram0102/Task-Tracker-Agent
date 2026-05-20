from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from task_tracker_agent.models import ParsedTask, Task


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    raw_input TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    start_time TEXT,
                    end_time TEXT,
                    location TEXT,
                    people_json TEXT NOT NULL DEFAULT '[]',
                    category TEXT NOT NULL DEFAULT 'personal',
                    priority_score INTEGER NOT NULL DEFAULT 50,
                    priority_label TEXT NOT NULL DEFAULT 'medium',
                    priority_reason TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS priority_rules (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    rule_text TEXT NOT NULL,
                    priority_boost INTEGER NOT NULL DEFAULT 20,
                    enabled INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS suggestions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE
                );
                """
            )

    def create_task(self, parsed: ParsedTask) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    title, raw_input, description, start_time, end_time, location,
                    people_json, category, priority_score, priority_label,
                    priority_reason, status, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    parsed.title,
                    parsed.raw_input,
                    parsed.description,
                    parsed.start_time,
                    parsed.end_time,
                    parsed.location,
                    json.dumps(parsed.people),
                    parsed.category,
                    parsed.priority_score,
                    parsed.priority_label,
                    parsed.priority_reason,
                    now,
                    now,
                ),
            )
            return int(cursor.lastrowid)

    def update_task(self, task_id: int, parsed: ParsedTask) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE tasks
                SET title = ?,
                    raw_input = ?,
                    description = ?,
                    start_time = ?,
                    end_time = ?,
                    location = ?,
                    people_json = ?,
                    category = ?,
                    priority_score = ?,
                    priority_label = ?,
                    priority_reason = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    parsed.title,
                    parsed.raw_input,
                    parsed.description,
                    parsed.start_time,
                    parsed.end_time,
                    parsed.location,
                    json.dumps(parsed.people),
                    parsed.category,
                    parsed.priority_score,
                    parsed.priority_label,
                    parsed.priority_reason,
                    now,
                    task_id,
                ),
            )

    def delete_task(self, task_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))

    def mark_task_achieved(self, task_id: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                "UPDATE tasks SET status = 'achieved', updated_at = ? WHERE id = ?",
                (now, task_id),
            )

    def list_tasks(self) -> list[Task]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY
                    priority_score DESC,
                    COALESCE(start_time, '9999-12-31') ASC,
                    created_at DESC
                """
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def list_past_tasks(self) -> list[Task]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM tasks
                WHERE status = 'achieved'
                ORDER BY updated_at DESC
                """
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def get_task(self, task_id: int) -> Task | None:
        with self._connect() as conn:
            row = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
        return self._row_to_task(row) if row else None

    def list_priority_rules(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT rule_text FROM priority_rules WHERE enabled = 1 ORDER BY id ASC"
            ).fetchall()
        return [str(row["rule_text"]) for row in rows]

    def add_priority_rule(self, name: str, rule_text: str, priority_boost: int = 20) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO priority_rules (name, rule_text, priority_boost, enabled, created_at)
                VALUES (?, ?, ?, 1, ?)
                """,
                (name, rule_text, priority_boost, now),
            )

    def _row_to_task(self, row: sqlite3.Row) -> Task:
        return Task(
            id=int(row["id"]),
            title=str(row["title"]),
            raw_input=str(row["raw_input"]),
            description=str(row["description"]),
            start_time=row["start_time"],
            end_time=row["end_time"],
            location=row["location"],
            people=json.loads(row["people_json"]),
            category=str(row["category"]),
            priority_score=int(row["priority_score"]),
            priority_label=str(row["priority_label"]),
            priority_reason=str(row["priority_reason"]),
            status=str(row["status"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
