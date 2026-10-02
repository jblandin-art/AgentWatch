from simulator.run import run_simulation


def test_simulator_emits_agent_activity(monkeypatch):
    emitted = []

    class FakeEmitter:
        def __init__(self, endpoint):
            self.endpoint = endpoint

        def emit(self, event):
            emitted.append(event)

    monkeypatch.setattr("simulator.run.HttpEventEmitter", FakeEmitter)
    count = run_simulation(
        "http://localhost:8000",
        count=3,
        interval_seconds=0,
        delay_seconds=0,
        failure_rate=0,
        seed=4,
    )

    assert count == 3
    agent_ids = {event.agent_id for event in emitted}
    assert agent_ids <= {"agent-001", "agent-002", "agent-003", "agent-004"}
    assert len({event.task_id for event in emitted}) == 3
