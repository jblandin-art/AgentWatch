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

Supported task types include meeting preparation, portfolio summaries, account
maintenance, risk assessment, retirement readiness, beneficiary review, cash
reserve checks, and allocation reviews.

## Run the interactive demo

From the repository root, run:

    python -m agentwatch

The menu lets you start successful or deliberately failed tasks, inspect
events, review task results, and see an event summary. It runs locally and
does not require AWS, RDS, or the backend API.

## Run the local backend

Start the local API from the repository root:

    .venv\Scripts\python.exe -m backend.server

It listens at `http://127.0.0.1:8000` and stores demo data in
`agentwatch.db`. The local SQLite database has the same core relationships as
the planned PostgreSQL database, so it can be replaced by RDS later.

The API implements `GET /health`, `POST /events`, `GET /dashboard/summary`,
`GET /advisors`, `GET /tasks`, `GET /tasks/{task_id}`, and
`GET /tasks/{task_id}/events`.

Seed the fictional advisors before running the simulator:

    .venv\Scripts\python.exe -m backend.seed

This creates seven advisors and no agents. Agents are created automatically by
the backend when the simulator sends their first event, so the dashboard only
shows agents that have performed work.

## Generate continuous task activity

With the backend running and the seed loaded, generate a small batch:

    .venv\Scripts\python.exe -m simulator.run --count 10 --interval 1

To keep generating tasks until you stop it with Ctrl+C:

    .venv\Scripts\python.exe -m simulator.run

The simulator uses eight repeatable simulated agent identities, randomly chooses
an appropriate task type, and sends every lifecycle event to the backend. The
backend creates each agent when its first event arrives. By default, about 15%
of tasks fail at a simulated tool. Useful options are `--failure-rate`,
`--delay`, `--interval`, and `--seed`.

## Preview the browser dashboard

Start the backend first:

    .venv\Scripts\python.exe -m backend.server

Then open `frontend/index.html` in a browser. The dashboard calls the local
API for summary counts, tasks, and task traces. You can filter tasks and click
a task to inspect its execution trace. The dashboard polls the API every three
seconds, so new simulator activity appears automatically without a page
refresh. If the backend is unavailable, the UI shows a clear connection error
instead of silently using stale data.

## Deploy the backend to AWS

The deployed backend uses API Gateway, Lambda, and PostgreSQL. The Lambda
handler is `backend.lambda_handler.handler`. Before deploying it, connect to
the RDS `postgres` database and run `migrations/001_postgres_schema.sql` with
`psql`. That migration renames the four original prototype tables to
`legacy_*` and creates the current schema without deleting the old data.

Set these Lambda environment variables:

    AGENTWATCH_DB_BACKEND=postgres
    DB_HOST=your-rds-endpoint
    DB_PORT=5432
    DB_NAME=postgres
    DB_USER=your-database-user
    DB_PASSWORD=your-database-password
    DB_SSLMODE=require
    CORS_ORIGIN=https://your-cloudfront-domain

To create a Lambda zip from PowerShell, use a Python 3.12-compatible package
directory and include the `backend` package:

    Remove-Item -Recurse -Force lambda_package -ErrorAction SilentlyContinue
    New-Item -ItemType Directory lambda_package | Out-Null
    & .venv\Scripts\python.exe -m pip install -r requirements.txt --target lambda_package --platform manylinux2014_x86_64 --implementation cp --python-version 3.12 --only-binary=:all:
    Copy-Item -Recurse backend lambda_package\backend
    Compress-Archive -Path lambda_package\* -DestinationPath agentwatch-lambda.zip -Force

In Lambda, set the handler to `backend.lambda_handler.handler`, then connect
the function to an API Gateway HTTP API. Keep the RDS security group closed to
the public internet; allow PostgreSQL traffic from the Lambda security group.
