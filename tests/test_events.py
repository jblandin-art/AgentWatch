import json

from agentwatch import Event, HttpEventEmitter


class FakeResponse:
    status = 202

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def test_http_event_emitter_sends_event_payload(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["method"] = request.method
        captured["timeout"] = timeout
        captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse()

    monkeypatch.setattr("agentwatch.events.urlopen", fake_urlopen)
    event = Event(
        advisor_id="advisor-1",
        agent_id="agent-1",
        task_id="task-1",
        event_type="task_started",
        status="running",
        timestamp="2026-10-02T17:00:00+00:00",
    )

    HttpEventEmitter("https://example.test/events").emit(event)

    assert captured["url"] == "https://example.test/events"
    assert captured["method"] == "POST"
    assert captured["timeout"] == 10.0
    assert captured["body"] == event.to_dict()
