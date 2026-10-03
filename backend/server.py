"""Dependency-light local API for AgentWatch.

Run with: python -m backend.server
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse
from uuid import uuid4

from .postgres import PostgresConnection

ALLOWED_STATUSES = {"waiting", "running", "completed", "failed"}
ALLOWED_EVENT_TYPES = {
    "agent_started",
    "task_started",
    "tool_started",
    "tool_completed",
    "tool_failed",
    "task_completed",
    "task_failed",
    "agent_finished",
}
REQUIRED_FIELDS = {
    "advisor_id",
    "agent_id",
    "task_id",
    "event_type",
    "status",
    "timestamp",
    "metadata",
}


def utc_timestamp() -> str:
    return datetime.now().astimezone().isoformat()


class Database:
    def __init__(self, path: str = "agentwatch.db") -> None:
        self.path = path
        self.backend = "postgres" if os.getenv("AGENTWATCH_DB_BACKEND") == "postgres" else "sqlite"
        if self.backend == "postgres":
            self.connection = PostgresConnection.from_environment()
        else:
            self.connection = sqlite3.connect(path, check_same_thread=False)
            self.connection.row_factory = sqlite3.Row
            self.connection.execute("PRAGMA foreign_keys = ON")
        self._create_schema()

    def _create_schema(self) -> None:
        if self.backend == "postgres":
            # PostgreSQL is initialized explicitly with migrations so the
            # application role never needs DDL privileges at runtime.
            return
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS advisors (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS agents (
                id TEXT PRIMARY KEY,
                advisor_id TEXT NOT NULL REFERENCES advisors(id),
                name TEXT,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY,
                advisor_id TEXT NOT NULL REFERENCES advisors(id),
                agent_id TEXT NOT NULL REFERENCES agents(id),
                prompt TEXT,
                task_type TEXT,
                status TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                error_message TEXT,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY,
                task_id TEXT NOT NULL REFERENCES tasks(id),
                agent_id TEXT NOT NULL REFERENCES agents(id),
                event_type TEXT NOT NULL,
                status TEXT NOT NULL,
                tool_name TEXT,
                timestamp TEXT NOT NULL,
                duration_ms INTEGER,
                error_message TEXT,
                metadata TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_task_timestamp
                ON events(task_id, timestamp);
            CREATE INDEX IF NOT EXISTS tasks_status ON tasks(status);
            """
        )
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    @staticmethod
    def _row_to_dict(row: sqlite3.Row | tuple[Any, ...], columns: list[str]) -> dict[str, Any]:
        if isinstance(row, (sqlite3.Row, Mapping)):
            return dict(row)
        return dict(zip(columns, row))

    @classmethod
    def _rows_to_dicts(
        cls,
        rows: list[sqlite3.Row | tuple[Any, ...]],
        columns: list[str],
    ) -> list[dict[str, Any]]:
        return [cls._row_to_dict(row, columns) for row in rows]

    def seed_advisors_and_agents(
        self, advisors: list[dict[str, Any]], agents: list[dict[str, Any]]
    ) -> None:
        with self.connection:
            for advisor in advisors:
                self.connection.execute(
                    """
                    INSERT INTO advisors(id, name, email, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET name = excluded.name,
                        email = excluded.email
                    """,
                    (
                        advisor["id"],
                        advisor["name"],
                        advisor["email"],
                        advisor.get("created_at", utc_timestamp()),
                    ),
                )
            for agent in agents:
                self.connection.execute(
                    """
                    INSERT INTO agents(id, advisor_id, name, status, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(id) DO UPDATE SET advisor_id = excluded.advisor_id,
                        name = excluded.name
                    """,
                    (
                        agent["id"],
                        agent["advisor_id"],
                        agent["name"],
                        agent.get("status", "waiting"),
                        agent.get("created_at", utc_timestamp()),
                    ),
                )

    def insert_event(self, event: dict[str, Any]) -> str:
        event_id = f"event-{uuid4().hex[:12]}"
        metadata = json.dumps(event["metadata"])
        with self.connection:
            self.connection.execute(
                "INSERT OR IGNORE INTO advisors(id, name, created_at) VALUES (?, ?, ?)",
                (event["advisor_id"], event["advisor_id"], utc_timestamp()),
            )
            self.connection.execute(
                """
                INSERT OR IGNORE INTO agents(id, advisor_id, name, status, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    event["agent_id"],
                    event["advisor_id"],
                    event["agent_id"],
                    event["status"],
                    event["timestamp"],
                ),
            )
            task_metadata = event["metadata"]
            self.connection.execute(
                """
                INSERT OR IGNORE INTO tasks(
                    id, advisor_id, agent_id, prompt, task_type, status, started_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["task_id"],
                    event["advisor_id"],
                    event["agent_id"],
                    task_metadata.get("prompt"),
                    task_metadata.get("task_type"),
                    event["status"],
                    event["timestamp"] if event["event_type"] == "task_started" else None,
                    event["timestamp"],
                ),
            )
            self.connection.execute(
                """
                INSERT INTO events(
                    id, task_id, agent_id, event_type, status, tool_name,
                    timestamp, duration_ms, error_message, metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_id,
                    event["task_id"],
                    event["agent_id"],
                    event["event_type"],
                    event["status"],
                    event.get("tool_name"),
                    event["timestamp"],
                    event.get("duration_ms"),
                    event.get("error_message"),
                    metadata,
                ),
            )
            self._update_state(event)
        return event_id

    def _update_state(self, event: dict[str, Any]) -> None:
        task_status = (
            event["status"]
            if event["event_type"] in {"task_started", "task_completed", "task_failed"}
            else None
        )
        agent_status = (
            event["status"]
            if event["event_type"] in {"agent_started", "agent_finished"}
            else None
        )
        completed_at = (
            event["timestamp"]
            if event["event_type"] in {"task_completed", "task_failed"}
            else None
        )
        error_message = event.get("error_message")
        self.connection.execute(
            """
            UPDATE tasks SET status = COALESCE(?, status),
                completed_at = COALESCE(?, completed_at),
                error_message = COALESCE(?, error_message),
                prompt = COALESCE(?, prompt),
                task_type = COALESCE(?, task_type),
                started_at = COALESCE(?, started_at)
            WHERE id = ?
            """,
            (
                task_status,
                completed_at,
                error_message,
                event["metadata"].get("prompt"),
                event["metadata"].get("task_type"),
                event["timestamp"] if event["event_type"] == "task_started" else None,
                event["task_id"],
            ),
        )
        self.connection.execute(
            "UPDATE agents SET status = COALESCE(?, status) WHERE id = ?",
            (agent_status, event["agent_id"]),
        )

    def summary(self) -> dict[str, int]:
        counts = {
            row["status"]: row["count"]
            for row in self.connection.execute(
                "SELECT status, COUNT(*) AS count FROM tasks GROUP BY status"
            )
        }
        return {
            "active_agents": self.connection.execute(
                "SELECT COUNT(*) FROM agents WHERE status = 'running'"
            ).fetchone()[0],
            "running_tasks": counts.get("running", 0),
            "completed_tasks": counts.get("completed", 0),
            "failed_tasks": counts.get("failed", 0),
            "waiting_tasks": counts.get("waiting", 0),
        }

    def tasks(self) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT t.*, a.name AS advisor_name, ag.name AS agent_name
            FROM tasks t
            JOIN advisors a ON a.id = t.advisor_id
            JOIN agents ag ON ag.id = t.agent_id
            ORDER BY t.created_at DESC
            """
        )
        rows = cursor.fetchall()
        return self._rows_to_dicts(rows, [column[0] for column in cursor.description])

    def agent_tasks(self, agent_id: str) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT t.*, a.name AS advisor_name, ag.name AS agent_name
            FROM tasks t
            JOIN advisors a ON a.id = t.advisor_id
            JOIN agents ag ON ag.id = t.agent_id
            WHERE t.agent_id = ?
            ORDER BY COALESCE(t.started_at, t.created_at) DESC
            """,
            (agent_id,),
        )
        rows = cursor.fetchall()
        return self._rows_to_dicts(rows, [column[0] for column in cursor.description])

    def advisors(self) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            """
            SELECT a.id, a.name, a.email,
                   ag.id AS agent_id, ag.name AS agent_name,
                   ag.status AS agent_status, ag.created_at AS agent_created_at,
                   t.id AS task_id, t.prompt AS task_prompt,
                   t.task_type, t.status AS task_status,
                   t.started_at AS task_started_at,
                   t.completed_at AS task_completed_at,
                   t.error_message AS task_error_message
            FROM advisors a
            LEFT JOIN agents ag ON ag.advisor_id = a.id
            LEFT JOIN tasks t ON t.id = (
                SELECT latest.id
                FROM tasks latest
                WHERE latest.agent_id = ag.id
                ORDER BY COALESCE(latest.started_at, latest.created_at) DESC
                LIMIT 1
            )
            ORDER BY a.name, COALESCE(t.started_at, ag.created_at) DESC
            """
        )
        rows = cursor.fetchall()
        advisors: dict[str, dict[str, Any]] = {}
        for row in self._rows_to_dicts(rows, [column[0] for column in cursor.description]):
            advisor = advisors.setdefault(
                row["id"],
                {
                    "id": row["id"],
                    "name": row["name"],
                    "email": row["email"],
                    "agents": [],
                },
            )
            if row["agent_id"] is not None:
                advisor["agents"].append(
                    {
                        "id": row["agent_id"],
                        "name": row["agent_name"],
                        "status": row["agent_status"],
                        "created_at": row["agent_created_at"],
                        "latest_task": (
                            {
                                "id": row["task_id"],
                                "prompt": row["task_prompt"],
                                "task_type": row["task_type"],
                                "status": row["task_status"],
                                "started_at": row["task_started_at"],
                                "completed_at": row["task_completed_at"],
                                "error_message": row["task_error_message"],
                            }
                            if row["task_id"] is not None
                            else None
                        ),
                    }
                )
        return list(advisors.values())

    def task(self, task_id: str) -> dict[str, Any] | None:
        cursor = self.connection.execute(
            """
            SELECT t.*, a.name AS advisor_name, ag.name AS agent_name
            FROM tasks t
            JOIN advisors a ON a.id = t.advisor_id
            JOIN agents ag ON ag.id = t.agent_id
            WHERE t.id = ?
            """,
            (task_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        result = self._row_to_dict(
            row, [column[0] for column in cursor.description]
        )
        result["events"] = self.events(task_id)
        return result

    def events(self, task_id: str) -> list[dict[str, Any]]:
        cursor = self.connection.execute(
            "SELECT * FROM events WHERE task_id = ? ORDER BY timestamp, id",
            (task_id,),
        )
        rows = cursor.fetchall()
        items = self._rows_to_dicts(
            rows, [column[0] for column in cursor.description]
        )
        result = []
        for item in items:
            if isinstance(item["metadata"], str):
                item["metadata"] = json.loads(item["metadata"])
            result.append(item)
        return result


def validate_event(payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "request body must be a JSON object"
    missing = sorted(REQUIRED_FIELDS - payload.keys())
    if missing:
        return False, f"missing required fields: {', '.join(missing)}"
    if payload["status"] not in ALLOWED_STATUSES:
        return False, f"unsupported status: {payload['status']}"
    if payload["event_type"] not in ALLOWED_EVENT_TYPES:
        return False, f"unsupported event_type: {payload['event_type']}"
    if not isinstance(payload["metadata"], dict):
        return False, "metadata must be a JSON object"
    duration = payload.get("duration_ms")
    if duration is not None and (not isinstance(duration, int) or duration < 0):
        return False, "duration_ms must be a non-negative integer"
    for field in ("advisor_id", "agent_id", "task_id", "timestamp"):
        if not isinstance(payload[field], str) or not payload[field].strip():
            return False, f"{field} must be a non-empty string"
    return True, ""


class RequestHandler(BaseHTTPRequestHandler):
    database: Database

    def log_message(self, format: str, *args: Any) -> None:
        return

    def _send(self, status: int, body: dict[str, Any]) -> None:
        encoded = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(encoded)

    def do_OPTIONS(self) -> None:
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        if path == "/health":
            self._send(HTTPStatus.OK, {"status": "ok", "database": "sqlite"})
        elif path == "/dashboard/summary":
            self._send(HTTPStatus.OK, self.database.summary())
        elif path == "/tasks":
            self._send(HTTPStatus.OK, {"tasks": self.database.tasks()})
        elif path == "/advisors":
            self._send(HTTPStatus.OK, {"advisors": self.database.advisors()})
        elif path.startswith("/agents/") and path.endswith("/tasks"):
            agent_id = path[len("/agents/") : -len("/tasks")].strip("/")
            self._send(HTTPStatus.OK, {"tasks": self.database.agent_tasks(agent_id)})
        elif path.startswith("/tasks/") and path.endswith("/events"):
            task_id = path[len("/tasks/") : -len("/events")].strip("/")
            self._send(HTTPStatus.OK, {"events": self.database.events(task_id)})
        elif path.startswith("/tasks/"):
            task = self.database.task(path[len("/tasks/") :])
            if task is None:
                self._send(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "task not found"})
            else:
                self._send(HTTPStatus.OK, task)
        else:
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "route not found"})

    def do_POST(self) -> None:
        if urlparse(self.path).path.rstrip("/") != "/events":
            self._send(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "route not found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length))
        except (ValueError, json.JSONDecodeError):
            self._send(HTTPStatus.BAD_REQUEST, {"error": "invalid_json", "message": "request body must be valid JSON"})
            return
        valid, message = validate_event(payload)
        if not valid:
            self._send(HTTPStatus.BAD_REQUEST, {"error": "validation_error", "message": message})
            return
        event_id = self.database.insert_event(payload)
        self._send(HTTPStatus.CREATED, {"status": "accepted", "event_id": event_id})


def run(host: str = "127.0.0.1", port: int = 8000, database_path: str = "agentwatch.db") -> None:
    database = Database(database_path)
    RequestHandler.database = database
    server = ThreadingHTTPServer((host, port), RequestHandler)
    print(f"AgentWatch API listening at http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping AgentWatch API.")
    finally:
        server.server_close()
        database.close()


if __name__ == "__main__":
    run(
        host=os.getenv("AGENTWATCH_HOST", "127.0.0.1"),
        port=int(os.getenv("AGENTWATCH_PORT", "8000")),
        database_path=os.getenv("AGENTWATCH_DB", "agentwatch.db"),
    )
