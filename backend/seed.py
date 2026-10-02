"""Seed fictional advisors for local development."""

from __future__ import annotations

import os

from .server import Database

ADVISORS = [
    {
        "id": "advisor-001",
        "name": "Jordan Smith",
        "email": "jordan.smith@example.test",
    },
    {
        "id": "advisor-002",
        "name": "Maya Patel",
        "email": "maya.patel@example.test",
    },
    {
        "id": "advisor-003",
        "name": "Luis Garcia",
        "email": "luis.garcia@example.test",
    },
]


def seed(database_path: str = "agentwatch.db") -> None:
    database = Database(database_path)
    try:
        database.seed_advisors_and_agents(ADVISORS, [])
    finally:
        database.close()
    print(f"Seeded {len(ADVISORS)} advisors into {database_path}.")


if __name__ == "__main__":
    seed(os.getenv("AGENTWATCH_DB", "agentwatch.db"))
