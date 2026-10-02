from agentwatch import AgentOrchestrator, FakeAgent, InMemoryEventEmitter


def test_start_task_assigns_ids_without_agent_id_input() -> None:
    emitter = InMemoryEventEmitter()
    orchestrator = AgentOrchestrator(emitter)

    result = orchestrator.start_task(
        "advisor-007", "Prepare a meeting summary", "meeting_prep"
    )

    assert result.status == "completed"
    assert result.agent_id.startswith("agent-")
    assert result.task_id.startswith("task-")
    assert all(event.advisor_id == "advisor-007" for event in emitter.events)
    assert all(event.agent_id == result.agent_id for event in emitter.events)
    assert all(event.task_id == result.task_id for event in emitter.events)


def test_failed_tool_produces_failed_trace() -> None:
    emitter = InMemoryEventEmitter()
    agent = FakeAgent("advisor-007", emitter)
    result = agent.start_task(
        "Prepare a meeting summary", "meeting_prep", fail_on="get_portfolio"
    )

    assert result.status == "failed"
    assert any(event.event_type == "tool_failed" for event in emitter.events)
    assert emitter.events[-1].event_type == "agent_finished"
