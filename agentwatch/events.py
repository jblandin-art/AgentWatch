"""Event creation and emission for agent executions."""

from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from datetime import datetime, timezone
from typing import Any, Protocol


@dataclass(frozen=True)
class Event:
    advisor_id: str
    agent_id: str
    task_id: str
    event_type: str
    status: str
    timestamp: str
    tool_name: str | None = None
    duration_ms: int | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class EventEmitter(Protocol):
    def emit(self, event: Event) -> None:
        """Publish one agent execution event."""


class InMemoryEventEmitter:
    """Collect events for tests and local development."""

    def __init__(self) -> None:
        self.events: list[Event] = []

    def emit(self, event: Event) -> None:
        self.events.append(event)


class JsonConsoleEventEmitter:
    """Write newline-delimited JSON events to a stream."""

    def __init__(self, stream: Any = None) -> None:
        self.stream = stream or sys.stdout

    def emit(self, event: Event) -> None:
        self.stream.write(json.dumps(event.to_dict()) + "\n")
        self.stream.flush()


class EventEmissionError(RuntimeError):
    """Raised when the backend rejects or cannot receive an event."""


class HttpEventEmitter:
    """Send events to the backend event-ingestion endpoint."""

    def __init__(self, endpoint: str, *, timeout_seconds: float = 10.0) -> None:
        if not endpoint.strip():
            raise ValueError("endpoint must not be empty")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def emit(self, event: Event) -> None:
        payload = json.dumps(event.to_dict()).encode("utf-8")
        request = Request(
            self.endpoint,
            data=payload,
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                if not 200 <= response.status < 300:
                    raise EventEmissionError(
                        f"event ingestion returned HTTP {response.status}"
                    )
        except HTTPError as error:
            raise EventEmissionError(
                f"event ingestion returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise EventEmissionError(
                f"event ingestion request failed: {error.reason}"
            ) from error


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
