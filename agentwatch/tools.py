"""Fictional tools used by the fake agent."""

from __future__ import annotations

from typing import Any


def get_client() -> dict[str, Any]:
    return {
        "client_id": "client-1008",
        "client_name": "Fictional Client",
        "account_type": "retirement",
    }


def get_portfolio() -> dict[str, Any]:
    return {
        "portfolio_id": "portfolio-1008",
        "balance": 250000,
        "allocation": {"equities": 60, "bonds": 30, "cash": 10},
    }


def calculate_portfolio_summary(portfolio: dict[str, Any]) -> dict[str, Any]:
    allocation = portfolio["allocation"]
    return {
        "balance": portfolio["balance"],
        "risk_profile": "moderate",
        "largest_allocation": max(allocation, key=allocation.get),
    }


def generate_meeting_summary(
    client: dict[str, Any], summary: dict[str, Any]
) -> dict[str, Any]:
    return {
        "summary": (
            f"Prepare to discuss {client['client_name']}'s "
            f"{summary['risk_profile']} portfolio."
        )
    }


def update_account() -> dict[str, str]:
    return {"result": "Account update simulated successfully"}
