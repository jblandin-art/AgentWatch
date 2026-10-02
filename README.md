# AgentWatch

AgentWatch is an AI-agent observability proof of concept. The initial fake
agent simulator runs locally and emits structured events that can later be
sent to the backend API and stored in RDS.

## Start a task

The advisor supplies only the advisor ID, prompt, and task type. The
orchestrator assigns the agent ID and creates the task ID internally:

    from agentwatch import AgentOrchestrator, InMemoryEventEmitter

    emitter = InMemoryEventEmitter()
    orchestrator = AgentOrchestrator(emitter)
    result = orchestrator.start_task(
        "advisor-007",
        "Prepare a meeting summary",
        "meeting_prep",
    )

The event emitter can later be replaced with an HTTP implementation that
posts events to the backend.

Supported task types are `meeting_prep`, `portfolio_summary`, and
`account_maintenance`.

## Run the interactive demo

From the repository root, run:

    python -m agentwatch

The menu lets you start successful or deliberately failed tasks, inspect
events, review task results, and see an event summary. It runs locally and
does not require AWS, RDS, or the backend API.
