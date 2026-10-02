# AgentWatch event API contract

This is the source-of-truth contract between the fake agent, backend, database,
and dashboard developers.

## Event ingestion

Endpoint: `POST /events`

Content type: `application/json`

The fake agent sends one request for every event in an execution trace. The
backend must process each request independently and persist the event.

Request body:

    {
      "advisor_id": "advisor-007",
      "agent_id": "agent-023",
      "task_id": "task-1042",
      "event_type": "tool_completed",
      "status": "completed",
      "timestamp": "2026-10-02T17:00:00+00:00",
      "tool_name": "get_portfolio",
      "duration_ms": 1200,
      "error_message": null,
      "metadata": {
        "client_id": "client-1008"
      }
    }

Required fields:

- `advisor_id`: string identifying the advisor who initiated the task.
- `agent_id`: string identifying the assigned agent.
- `task_id`: string identifying one task execution.
- `event_type`: string describing the lifecycle event.
- `status`: string describing the event state.
- `timestamp`: ISO 8601 timestamp with timezone.
- `metadata`: JSON object; use `{}` when there is no additional metadata.

Optional fields:

- `tool_name`: string for tool events; otherwise `null`.
- `duration_ms`: non-negative integer when the duration is known; otherwise
  `null`.
- `error_message`: string for failed events; otherwise `null`.

Allowed statuses:

- `waiting`
- `running`
- `completed`
- `failed`

Allowed event types:

- `agent_started`
- `task_started`
- `tool_started`
- `tool_completed`
- `tool_failed`
- `task_completed`
- `task_failed`
- `agent_finished`

The backend should reject malformed requests with HTTP `400` and a JSON body
containing `error` and `message` fields. It should return HTTP `201` or `202`
when the event is accepted. It should return HTTP `500` (or an equivalent
5xx response) for a server or database failure.

Accepted response:

    {
      "status": "accepted",
      "event_id": "event-123"
    }

The agent currently treats any 2xx response as success and raises an explicit
error for network failures or non-2xx responses.

## Identity and ownership rules

- Advisors do not provide `agent_id` or `task_id`.
- The orchestrator assigns an agent to an advisor.
- The orchestrator creates a new task ID for every task execution.
- All events for one task must use the same `advisor_id`, `agent_id`, and
  `task_id`.
- The backend should verify that the agent belongs to the advisor and that the
  event belongs to the referenced task.

## Other planned endpoints

These endpoints are reserved for the dashboard integration:

- `GET /health`
- `GET /dashboard/summary`
- `GET /advisors`
- `GET /agents`
- `GET /tasks`
- `GET /tasks/{task_id}`
- `GET /tasks/{task_id}/events`
