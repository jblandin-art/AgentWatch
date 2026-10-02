"""Interactive local demonstration of the AgentWatch fake agent."""

from __future__ import annotations

from .agent import AgentOrchestrator, TaskResult
from .events import Event, InMemoryEventEmitter

TASK_TYPES = {
    "1": ("meeting_prep", "Prepare a client meeting summary"),
    "2": ("portfolio_summary", "Summarize the client's portfolio"),
    "3": ("account_maintenance", "Perform an account maintenance check"),
}

TOOL_DESCRIPTIONS = {
    "get_client": "Retrieves fictional client information",
    "get_portfolio": "Retrieves the fictional portfolio",
    "calculate_portfolio_summary": "Calculates a portfolio risk and allocation summary",
    "generate_meeting_summary": "Generates the meeting preparation summary",
    "update_account": "Simulates an account maintenance update",
}

def main() -> None:
    """Run the interactive fake-agent demonstration."""
    emitter = InMemoryEventEmitter()
    orchestrator = AgentOrchestrator(emitter, delay_seconds=0.1)
    results: list[TaskResult] = []

    print("AgentWatch interactive demo")
    print("The system assigns agent and task IDs automatically.")

    while True:
        print_menu()
        choice = input("Choose an option: ").strip()

        if choice == "1":
            result = run_task(orchestrator)
            results.append(result)
        elif choice == "2":
            show_recent_events(emitter.events)
        elif choice == "3":
            show_task_results(results)
        elif choice == "4":
            print_event_summary(emitter.events)
        elif choice in {"q", "quit", "exit"}:
            print("Goodbye.")
            return
        else:
            print("Please choose 1, 2, 3, 4, or q.")


def print_menu() -> None:
    print(
        "\n1. Start a fake task"
        "\n2. Show recent events"
        "\n3. Show task results"
        "\n4. Show event summary"
        "\nq. Quit"
    )


def run_task(orchestrator: AgentOrchestrator) -> TaskResult:
    advisor_id = input("Advisor ID (example: advisor-007): ").strip()
    if not advisor_id:
        print("Advisor ID cannot be empty.")
        return failed_input_result()

    print("\nTask types:")
    for key, (task_type, description) in TASK_TYPES.items():
        print(f"{key}. {task_type} - {description}")
    task_choice = input("Choose a task type: ").strip()
    selected = TASK_TYPES.get(task_choice)
    if selected is None:
        print("Unknown task type.")
        return failed_input_result()

    task_type, default_prompt = selected
    prompt = input(f"Prompt [{default_prompt}]: ").strip() or default_prompt

    fail_on = choose_failure(task_type)
    before = len(orchestrator.emitter.events)
    try:
        result = orchestrator.start_task(
            advisor_id, prompt, task_type, fail_on=fail_on
        )
    except ValueError as error:
        print(f"Could not start task: {error}")
        return failed_input_result()

    new_events = orchestrator.emitter.events[before:]
    print_result(result)
    print(f"Events emitted: {len(new_events)}")
    return result


def choose_failure(task_type: str) -> str | None:
    available_tools = {
        "meeting_prep": [
            "get_client",
            "get_portfolio",
            "calculate_portfolio_summary",
            "generate_meeting_summary",
        ],
        "portfolio_summary": ["get_portfolio", "calculate_portfolio_summary"],
        "account_maintenance": ["update_account"],
    }[task_type]

    print("\nFailure simulation:")
    print("0. No failure")
    for index, tool_name in enumerate(available_tools, start=1):
        print(f"{index}. Fail at {tool_name}")
    choice = input("Choose a failure option [0]: ").strip() or "0"
    if choice == "0":
        return None
    try:
        selected_index = int(choice) - 1
        return available_tools[selected_index]
    except (ValueError, IndexError):
        print("Invalid failure option; running successfully.")
        return None


def show_recent_events(events: list[Event]) -> None:
    if not events:
        print("No events have been emitted yet.")
        return
    print("\nRecent events:")
    for event in events[-20:]:
        tool = f" [{event.tool_name}]" if event.tool_name else ""
        duration = (
            f", {event.duration_ms} ms" if event.duration_ms is not None else ""
        )
        error = f" - {event.error_message}" if event.error_message else ""
        print(f"{event.event_type}{tool}: {event.status}{duration}{error}")
        print(f"  advisor={event.advisor_id}, agent={event.agent_id}, task={event.task_id}")
        if event.event_type == "agent_started":
            prompt = event.metadata.get("prompt")
            if prompt:
                print(f"  prompt: {prompt}")
        elif event.event_type == "task_started":
            task_type = event.metadata.get("task_type")
            if task_type:
                print(f"  task type: {task_type}")
        elif event.tool_name:
            description = TOOL_DESCRIPTIONS.get(event.tool_name)
            if description:
                print(f"  tool purpose: {description}")


def show_task_results(results: list[TaskResult]) -> None:
    if not results:
        print("No tasks have been run yet.")
        return
    print("\nTask results:")
    for result in results:
        print(
            f"{result.task_id}: {result.status} | "
            f"advisor={result.advisor_id} | agent={result.agent_id} | "
            f"type={result.task_type}"
        )
        if result.error_message:
            print(f"  error: {result.error_message}")
        elif result.output:
            print(f"  output: {result.output}")


def print_event_summary(events: list[Event]) -> None:
    counts: dict[str, int] = {}
    for event in events:
        counts[event.event_type] = counts.get(event.event_type, 0) + 1
    print("\nEvent summary:")
    if not counts:
        print("No events have been emitted yet.")
        return
    for event_type, count in sorted(counts.items()):
        print(f"{event_type}: {count}")


def print_result(result: TaskResult) -> None:
    print(f"\nTask {result.task_id} finished with status: {result.status}")
    print(f"Assigned agent: {result.agent_id}")
    if result.error_message:
        print(f"Error: {result.error_message}")
    elif result.output:
        print(f"Output: {result.output}")


def failed_input_result() -> TaskResult:
    """Keep the interactive loop running after invalid input."""
    return TaskResult("", "", "", "", "invalid_input", None, "invalid input")


if __name__ == "__main__":
    main()
