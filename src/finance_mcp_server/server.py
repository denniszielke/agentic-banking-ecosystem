"""Finance MCP server providing financial tools."""

from __future__ import annotations

import json
import logging
import os
from typing import Literal, cast, get_args

from fastmcp import FastMCP

from finance_mcp.auth import trust_platform_auth

logger = logging.getLogger(__name__)

mcp = FastMCP("Finance MCP Server")


@mcp.tool()
def calculate_compound_interest(
    principal: float,
    annual_rate: float,
    years: float,
    compounds_per_year: int = 1,
) -> str:
    """Calculate compound interest and the future value of an investment.

    Args:
        principal: Initial investment amount (non-negative).
        annual_rate: Annual interest rate in percent (e.g. 5 for 5%).
        years: Investment duration in years (positive).
        compounds_per_year: Number of compounding periods per year (default: 1 = annual).

    """
    if principal < 0:
        return "Error: principal must be non-negative."
    if annual_rate < 0:
        return "Error: annual_rate must be non-negative."
    if years <= 0:
        return "Error: years must be positive."
    if compounds_per_year <= 0:
        return "Error: compounds_per_year must be a positive integer."

    r = annual_rate / 100
    n = compounds_per_year
    future_value = principal * (1 + r / n) ** (n * years)
    interest_earned = future_value - principal

    return json.dumps(
        {
            "principal": round(principal, 2),
            "annual_rate_percent": annual_rate,
            "years": years,
            "compounds_per_year": compounds_per_year,
            "future_value": round(future_value, 2),
            "interest_earned": round(interest_earned, 2),
            "total_return_percent": round((interest_earned / principal) * 100, 4) if principal > 0 else None,
        },
        indent=2,
    )


@mcp.tool()
def discount_cashflow(
    future_value: float,
    annual_rate: float,
    years: float,
    compounds_per_year: int = 1,
) -> str:
    """Discount a future cash flow to its present value.

    Args:
        future_value: Amount to be received in the future (non-negative).
        annual_rate: Annual discount rate in percent (e.g. 5 for 5%).
        years: Number of years until the cash flow is received (positive).
        compounds_per_year: Number of compounding periods per year (default: 1 = annual).

    """
    if future_value < 0:
        return "Error: future_value must be non-negative."
    if annual_rate < 0:
        return "Error: annual_rate must be non-negative."
    if years <= 0:
        return "Error: years must be positive."
    if compounds_per_year <= 0:
        return "Error: compounds_per_year must be a positive integer."

    r = annual_rate / 100
    n = compounds_per_year
    present_value = future_value / (1 + r / n) ** (n * years)
    discount = future_value - present_value

    return json.dumps(
        {
            "future_value": round(future_value, 2),
            "annual_rate_percent": annual_rate,
            "years": years,
            "compounds_per_year": compounds_per_year,
            "present_value": round(present_value, 2),
            "discount_amount": round(discount, 2),
            "discount_percent": round((discount / future_value) * 100, 4) if future_value > 0 else None,
        },
        indent=2,
    )


# ---------------------------------------------------------------------------
# Server entrypoint
# ---------------------------------------------------------------------------

Transport = Literal["stdio", "http", "streamable-http"]
_NETWORK_TRANSPORTS = {"http", "streamable-http"}


def main() -> None:
    """Run the MCP server.

    Transport, host, and port are read from the environment so the same
    entrypoint works locally (stdio) and in containers (HTTP):

        MCP_TRANSPORT: stdio | http | streamable-http (default: stdio)
        MCP_HOST:      bind address for network transports (default: 0.0.0.0)
        MCP_PORT / PORT: port for network transports (default: 8000)

    For network transports authentication is mandatory: the server refuses to
    start unless the deployment platform's own auth gate is trusted
    (MCP_TRUST_PLATFORM_AUTH=1 -- Cloud Run IAM, Databricks OAuth, Azure Easy
    Auth). See finance_mcp.auth.
    """
    logging.basicConfig(level=os.environ.get("MCP_LOG_LEVEL", "INFO"))

    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport not in get_args(Transport):
        raise SystemExit(f"Invalid MCP_TRANSPORT '{transport}'. Expected one of: {', '.join(get_args(Transport))}.")
    transport = cast(Transport, transport)

    if transport in _NETWORK_TRANSPORTS and not trust_platform_auth():
        raise SystemExit(
            f"Refusing to start: transport '{transport}' is network-exposed but the "
            "platform auth gate is not trusted. Deploy behind Cloud Run IAM, "
            "Databricks OAuth, or Azure Easy Auth and set MCP_TRUST_PLATFORM_AUTH=1. "
            "See the Authentication section of the README."
        )

    if transport == "stdio":
        mcp.run(transport=transport)
        return

    port = int(os.environ.get("MCP_PORT") or os.environ.get("PORT") or os.environ.get("DATABRICKS_APP_PORT") or "8000")
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    mcp.run(transport=transport, host=host, port=port)


if __name__ == "__main__":
    main()
