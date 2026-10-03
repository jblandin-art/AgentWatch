"""AWS Lambda handler for the AgentWatch API Gateway integration."""

from __future__ import annotations

import base64
import json
import os
from http import HTTPStatus
from typing import Any
from urllib.parse import unquote

from .server import Database, validate_event

_database: Database | None = None


def _get_database() -> Database:
    global _database
    if _database is None or (
        _database.backend == "postgres" and _database.connection.closed
    ):
        if _database is not None:
            _database.close()
        _database = Database(os.getenv("AGENTWATCH_DB", "agentwatch.db"))
    return _database


def _response(status: int, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": os.getenv("CORS_ORIGIN", "*"),
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        },
        "body": json.dumps(body),
    }


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    request_context = event.get("requestContext", {})
    method = event.get("httpMethod") or request_context.get("http", {}).get("method", "GET")
    path = event.get("rawPath") or event.get("path", "/")
    path = "/" + "/".join(unquote(part) for part in path.strip("/").split("/") if part)
    if method == "OPTIONS":
        return _response(HTTPStatus.NO_CONTENT, {})

    database = _get_database()
    if method == "GET" and path == "/health":
        return _response(HTTPStatus.OK, {"status": "ok", "database": database.backend})
    if method == "GET" and path == "/dashboard/summary":
        return _response(HTTPStatus.OK, database.summary())
    if method == "GET" and path == "/advisors":
        return _response(HTTPStatus.OK, {"advisors": database.advisors()})
    if method == "GET" and path == "/tasks":
        return _response(HTTPStatus.OK, {"tasks": database.tasks()})
    if method == "GET" and path.startswith("/agents/") and path.endswith("/tasks"):
        agent_id = path[len("/agents/") : -len("/tasks")].strip("/")
        return _response(HTTPStatus.OK, {"tasks": database.agent_tasks(agent_id)})
    if method == "GET" and path.startswith("/tasks/") and path.endswith("/events"):
        task_id = path[len("/tasks/") : -len("/events")].strip("/")
        return _response(HTTPStatus.OK, {"events": database.events(task_id)})
    if method == "GET" and path.startswith("/tasks/"):
        task = database.task(path[len("/tasks/") :])
        if task is None:
            return _response(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "task not found"})
        return _response(HTTPStatus.OK, task)
    if method == "POST" and path == "/events":
        raw_body = event.get("body") or "{}"
        if event.get("isBase64Encoded"):
            raw_body = base64.b64decode(raw_body).decode("utf-8")
        try:
            payload = json.loads(raw_body)
        except (TypeError, json.JSONDecodeError):
            return _response(HTTPStatus.BAD_REQUEST, {"error": "invalid_json"})
        valid, message = validate_event(payload)
        if not valid:
            return _response(HTTPStatus.BAD_REQUEST, {"error": "validation_error", "message": message})
        event_id = database.insert_event(payload)
        return _response(HTTPStatus.CREATED, {"status": "accepted", "event_id": event_id})
    return _response(HTTPStatus.NOT_FOUND, {"error": "not_found", "message": "route not found"})
