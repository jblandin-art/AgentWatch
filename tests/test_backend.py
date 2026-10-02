import json
import threading
from http.client import HTTPConnection

from backend.server import Database, RequestHandler
from http.server import ThreadingHTTPServer


def start_server(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    RequestHandler.database = database
    server = ThreadingHTTPServer(("127.0.0.1", 0), RequestHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, database, thread


def request(server, method, path, body=None):
    connection = HTTPConnection(*server.server_address)
    encoded = json.dumps(body).encode() if body is not None else None
    connection.request(
        method,
        path,
        body=encoded,
        headers={"Content-Type": "application/json"} if encoded else {},
    )
    response = connection.getresponse()
    result = json.loads(response.read())
    connection.close()
    return response.status, result


def event(event_type, status, **extra):
    return {
        "advisor_id": "advisor-1",
        "agent_id": "agent-1",
        "task_id": "task-1",
        "event_type": event_type,
        "status": status,
        "timestamp": "2026-10-02T17:00:00+00:00",
        "metadata": {},
        **extra,
    }


def test_event_lifecycle_and_trace(tmp_path):
    server, database, thread = start_server(tmp_path)
    try:
        status, accepted = request(server, "POST", "/events", event(
            "agent_started", "running", metadata={"prompt": "Prepare a meeting summary"}
        ))
        assert status == 201
        assert accepted["status"] == "accepted"
        request(server, "POST", "/events", event(
            "task_started", "running", metadata={"task_type": "meeting_prep"}
        ))
        request(server, "POST", "/events", event(
            "tool_completed", "completed", tool_name="get_client", duration_ms=100
        ))
        request(server, "POST", "/events", event("task_completed", "completed"))

        status, summary = request(server, "GET", "/dashboard/summary")
        assert status == 200
        assert summary["completed_tasks"] == 1

        status, task = request(server, "GET", "/tasks/task-1")
        assert status == 200
        assert task["prompt"] == "Prepare a meeting summary"
        assert len(task["events"]) == 4

        status, task_list = request(server, "GET", "/tasks")
        assert status == 200
        assert [item["id"] for item in task_list["tasks"]] == ["task-1"]

        status, agent_tasks = request(server, "GET", "/agents/agent-1/tasks")
        assert status == 200
        assert [item["id"] for item in agent_tasks["tasks"]] == ["task-1"]

        status, advisors = request(server, "GET", "/advisors")
        assert status == 200
        assert advisors["advisors"][0]["agents"][0]["latest_task"]["id"] == "task-1"
    finally:
        server.shutdown()
        server.server_close()
        database.close()


def test_invalid_event_is_rejected(tmp_path):
    server, database, thread = start_server(tmp_path)
    try:
        status, body = request(server, "POST", "/events", {"status": "invalid"})
        assert status == 400
        assert body["error"] == "validation_error"
    finally:
        server.shutdown()
        server.server_close()
        database.close()
