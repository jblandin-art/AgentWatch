"""Fake agent workflows with internally assigned execution IDs."""

from __future__ import annotations

import time
from dataclasses import dataclass
from time import perf_counter
from typing import Any, Callable
from uuid import uuid4

from .events import Event, EventEmitter, utc_now
from . import tools

TaskType = str


@dataclass(frozen=True)
class TaskResult:
    advisor_id: str
    agent_id: str
    task_id: str
    task_type: TaskType
    status: str
    output: dict[str, Any] | None
    error_message: str | None


class FakeAgent:
    """An agent instance assigned by the orchestrator, not by the advisor."""

    def __init__(
        self,
        advisor_id: str,
        emitter: EventEmitter,
        *,
        agent_id: str | None = None,
        delay_seconds: float = 0.0,
    ) -> None:
        self.advisor_id = advisor_id
        self.agent_id = agent_id or f"agent-{uuid4().hex[:12]}"
        self.emitter = emitter
        self.delay_seconds = delay_seconds

    def start_task(
        self,
        prompt: str,
        task_type: TaskType,
        *,
        task_id: str | None = None,
        fail_on: str | None = None,
    ) -> TaskResult:
        """Run one task. Callers provide a prompt, never an agent ID."""
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        supported_task_types = {
            "meeting_prep",
            "portfolio_summary",
            "account_maintenance",
            "risk_assessment",
            "retirement_readiness",
            "beneficiary_review",
            "cash_reserve_check",
            "allocation_review",
        }
        if task_type not in supported_task_types:
            raise ValueError(f"unsupported task_type: {task_type}")

        execution_id = task_id or f"task-{uuid4().hex[:12]}"
        self._emit(execution_id, "agent_started", "running", metadata={"prompt": prompt})
        self._emit(execution_id, "task_started", "running", metadata={"task_type": task_type})

        try:
            output = self._run_workflow(
                execution_id, prompt, task_type, fail_on=fail_on
            )
        except RuntimeError as error:
            self._emit(
                execution_id,
                "task_failed",
                "failed",
                error_message=str(error),
            )
            self._emit(execution_id, "agent_finished", "failed")
            return TaskResult(
                self.advisor_id,
                self.agent_id,
                execution_id,
                task_type,
                "failed",
                None,
                str(error),
            )

        self._emit(execution_id, "task_completed", "completed")
        self._emit(execution_id, "agent_finished", "completed")
        return TaskResult(
            self.advisor_id, self.agent_id, execution_id, task_type, "completed", output, None
        )

    def _run_workflow(
        self,
        task_id: str,
        prompt: str,
        task_type: TaskType,
        *,
        fail_on: str | None,
    ) -> dict[str, Any]:
        if task_type == "meeting_prep":
            client = self._call_tool(task_id, "get_client", tools.get_client, fail_on=fail_on)
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            summary = self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
            return self._call_tool(
                task_id,
                "generate_meeting_summary",
                lambda: tools.generate_meeting_summary(client, summary),
                fail_on=fail_on,
            )
        if task_type == "portfolio_summary":
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            return self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
        if task_type == "risk_assessment":
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            return self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
        if task_type == "retirement_readiness":
            client = self._call_tool(task_id, "get_client", tools.get_client, fail_on=fail_on)
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            summary = self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
            return self._call_tool(
                task_id,
                "generate_meeting_summary",
                lambda: tools.generate_meeting_summary(client, summary),
                fail_on=fail_on,
            )
        if task_type == "beneficiary_review":
            self._call_tool(task_id, "get_client", tools.get_client, fail_on=fail_on)
            return self._call_tool(
                task_id, "update_account", tools.update_account, fail_on=fail_on
            )
        if task_type == "cash_reserve_check":
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            return self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
        if task_type == "allocation_review":
            portfolio = self._call_tool(
                task_id, "get_portfolio", tools.get_portfolio, fail_on=fail_on
            )
            return self._call_tool(
                task_id,
                "calculate_portfolio_summary",
                lambda: tools.calculate_portfolio_summary(portfolio),
                fail_on=fail_on,
            )
        return self._call_tool(
            task_id, "update_account", tools.update_account, fail_on=fail_on
        )

    def _call_tool(
        self,
        task_id: str,
        tool_name: str,
        function: Callable[[], dict[str, Any]],
        *,
        fail_on: str | None,
    ) -> dict[str, Any]:
        started = perf_counter()
        self._emit(task_id, "tool_started", "running", tool_name=tool_name)
        if self.delay_seconds:
            time.sleep(self.delay_seconds)
        if fail_on == tool_name:
            error = f"{tool_name} failed: simulated tool timeout"
            self._emit(
                task_id,
                "tool_failed",
                "failed",
                tool_name=tool_name,
                duration_ms=self._duration_ms(started),
                error_message=error,
            )
            raise RuntimeError(error)
        result = function()
        self._emit(
            task_id,
            "tool_completed",
            "completed",
            tool_name=tool_name,
            duration_ms=self._duration_ms(started),
        )
        return result

    def _emit(
        self,
        task_id: str,
        event_type: str,
        status: str,
        *,
        tool_name: str | None = None,
        duration_ms: int | None = None,
        error_message: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.emitter.emit(
            Event(
                advisor_id=self.advisor_id,
                agent_id=self.agent_id,
                task_id=task_id,
                event_type=event_type,
                status=status,
                timestamp=utc_now(),
                tool_name=tool_name,
                duration_ms=duration_ms,
                error_message=error_message,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def _duration_ms(started: float) -> int:
        return max(0, round((perf_counter() - started) * 1000))


class AgentOrchestrator:
    """Assign agents internally and start tasks from advisor requests."""

    def __init__(self, emitter: EventEmitter, *, delay_seconds: float = 0.0) -> None:
        self.emitter = emitter
        self.delay_seconds = delay_seconds
        self._agents: dict[str, FakeAgent] = {}

    def start_task(
        self,
        advisor_id: str,
        prompt: str,
        task_type: TaskType,
        *,
        fail_on: str | None = None,
    ) -> TaskResult:
        """Start a task without requiring callers to provide an agent ID."""
        if not advisor_id.strip():
            raise ValueError("advisor_id must not be empty")
        agent = self._agents.get(advisor_id)
        if agent is None:
            agent = FakeAgent(
                advisor_id,
                self.emitter,
                delay_seconds=self.delay_seconds,
            )
            self._agents[advisor_id] = agent
        return agent.start_task(prompt, task_type, fail_on=fail_on)

    def agent_for_advisor(self, advisor_id: str) -> FakeAgent:
        """Return the internally assigned agent for inspection or simulation."""
        return self._agents[advisor_id]
