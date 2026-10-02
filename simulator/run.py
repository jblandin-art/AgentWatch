"""Generate realistic task activity for the local AgentWatch API."""

from __future__ import annotations

import argparse
import os
import random
import time
from dataclasses import dataclass

from agentwatch import FakeAgent, HttpEventEmitter


@dataclass(frozen=True)
class SeededAgent:
    advisor_id: str
    agent_id: str
    task_types: tuple[str, ...]


SIMULATED_AGENTS = (
    SeededAgent("advisor-001", "agent-001", ("meeting_prep", "portfolio_summary")),
    SeededAgent("advisor-001", "agent-002", ("portfolio_summary",)),
    SeededAgent("advisor-002", "agent-003", ("portfolio_summary", "meeting_prep")),
    SeededAgent("advisor-003", "agent-004", ("account_maintenance", "meeting_prep")),
)

PROMPTS = {
    "meeting_prep": "Prepare a client meeting summary",
    "portfolio_summary": "Summarize the client's portfolio",
    "account_maintenance": "Check the account maintenance request",
}

FAILURE_TOOLS = {
    "meeting_prep": ("get_portfolio", "generate_meeting_summary"),
    "portfolio_summary": ("get_portfolio", "calculate_portfolio_summary"),
    "account_maintenance": ("update_account",),
}


def run_simulation(
    api_url: str,
    *,
    count: int | None = None,
    interval_seconds: float = 3.0,
    failure_rate: float = 0.15,
    delay_seconds: float = 0.25,
    seed: int | None = None,
) -> int:
    """Generate tasks until count is reached, or forever when count is None."""
    if not 0 <= failure_rate <= 1:
        raise ValueError("failure_rate must be between 0 and 1")
    if interval_seconds < 0 or delay_seconds < 0:
        raise ValueError("interval_seconds and delay_seconds cannot be negative")
    if count is not None and count < 1:
        raise ValueError("count must be positive")

    random_generator = random.Random(seed)
    emitter = HttpEventEmitter(f"{api_url.rstrip('/')}/events")
    completed = 0
    print(
        f"Sending simulated tasks to {api_url}. "
        f"{'Press Ctrl+C to stop.' if count is None else f'Generating {count} tasks.'}"
    )
    while count is None or completed < count:
        assignment = random_generator.choice(SIMULATED_AGENTS)
        task_type = random_generator.choice(assignment.task_types)
        fail_on = None
        if random_generator.random() < failure_rate:
            fail_on = random_generator.choice(FAILURE_TOOLS[task_type])
        agent = FakeAgent(
            assignment.advisor_id,
            emitter,
            agent_id=assignment.agent_id,
            delay_seconds=delay_seconds,
        )
        result = agent.start_task(
            PROMPTS[task_type],
            task_type,
            fail_on=fail_on,
        )
        completed += 1
        failure = f", failure at {fail_on}" if fail_on else ""
        print(
            f"[{completed}] {assignment.advisor_id} / {assignment.agent_id} "
            f"-> {result.task_id}: {result.status}{failure}"
        )
        if count is None or completed < count:
            time.sleep(interval_seconds)
    return completed


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate AgentWatch task activity.")
    parser.add_argument(
        "--api-url",
        default=os.getenv("AGENTWATCH_API_URL", "http://127.0.0.1:8000"),
        help="Backend base URL.",
    )
    parser.add_argument(
        "--count",
        type=int,
        default=None,
        help="Number of tasks to generate. Omit to run continuously.",
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=3.0,
        help="Seconds between tasks.",
    )
    parser.add_argument(
        "--failure-rate",
        type=float,
        default=0.15,
        help="Failure probability from 0 to 1.",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.25,
        help="Delay between tool calls.",
    )
    parser.add_argument("--seed", type=int, help="Seed randomness for repeatable runs.")
    args = parser.parse_args()
    try:
        run_simulation(
            args.api_url,
            count=args.count,
            interval_seconds=args.interval,
            failure_rate=args.failure_rate,
            delay_seconds=args.delay,
            seed=args.seed,
        )
    except KeyboardInterrupt:
        print("\nSimulation stopped.")


if __name__ == "__main__":
    main()
