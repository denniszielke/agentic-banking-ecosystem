"""Finance MCP server providing financial calculation tools."""

from __future__ import annotations

import json
import logging
import os

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

_HOST = os.getenv("FINANCE_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("FINANCE_MCP_PORT", "8093"))


def _build_auth():
    """Build the FastMCP Microsoft Entra ID JWT auth provider, or ``None``.

    Enabled only when ``ENTRA_AUTH_ENABLED`` is truthy and both the API audience
    (``MCP_AUTH_CLIENT_ID``) and ``AZURE_TENANT_ID`` are set. The provider
    validates incoming Entra access tokens (issuer, audience and JWKS signature)
    inside the app itself — no Container Apps Easy Auth and no client secret.
    No scope is required, so both delegated (user) and app-only (managed
    identity) tokens are accepted. Returns ``None`` to run anonymously (local
    development, or auth toggled off).
    """
    enabled = os.getenv("ENTRA_AUTH_ENABLED", "false").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    client_id = os.getenv("MCP_AUTH_CLIENT_ID", "").strip()
    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    if not (enabled and client_id and tenant_id):
        return None
    from fastmcp.server.auth import RemoteAuthProvider
    from fastmcp.server.auth.providers.azure import AzureJWTVerifier
    from pydantic import AnyHttpUrl

    base_url = os.getenv("MCP_PUBLIC_BASE_URL", "").strip() or f"http://{_HOST}:{_PORT}"
    verifier = AzureJWTVerifier(client_id=client_id, tenant_id=tenant_id)
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[
            AnyHttpUrl(f"https://login.microsoftonline.com/{tenant_id}/v2.0")
        ],
        base_url=base_url,
    )


mcp = FastMCP(
    name="finance",
    instructions=(
        "Financial calculation tools. Use these tools to compute compound interest, "
        "discount future cash flows to present value, and perform other time-value-of-money "
        "calculations. All rates are expressed as annual percentages (e.g. 5 means 5%). "
        "Results are returned as JSON with rounded monetary values."
    ),
    auth=_build_auth(),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    """Readiness probe endpoint — returns 200 OK when the server is up."""
    return JSONResponse({"status": "ok"})


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
            "total_return_percent": round((interest_earned / principal) * 100, 4)
            if principal > 0
            else None,
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
            "discount_percent": round((discount / future_value) * 100, 4)
            if future_value > 0
            else None,
        },
        indent=2,
    )


def main() -> None:
    """Entry point — serve the finance tools over streamable-HTTP MCP."""
    logging.basicConfig(level=os.environ.get("MCP_LOG_LEVEL", "INFO"))
    mcp.run(
        transport="http",
        host=_HOST,
        port=_PORT,
        host_origin_protection=False,
    )


if __name__ == "__main__":
    main()
