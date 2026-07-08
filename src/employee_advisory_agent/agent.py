"""Employee Advisory Agent — Foundry hosted agent.

The internal advisory agent used by bank employees (one hosted instance per bank
— Bank North and Bank South). It helps an employee who is talking to a customer:
explain product conditions, look up the customer's context, recommend suitable
products and find the right internal branch contact — grounded on the bank's own
knowledge.

It is built with the **agent-framework** and hosted in **Azure AI Foundry** as a
hosted agent (served over the RESPONSES protocol by ``ResponsesHostServer``). It
draws on three tool surfaces:

  1. **Financial products index** — the ``banking-products`` Azure AI Search
     index (product catalogue + conditions), surfaced through the
     ``search_financial_products`` function tool.

  2. **Product & customer MCP servers** — the ``product_data_mcp_server`` (full
     catalogue + conditions) and ``customer_data_mcp_server`` (read-only
     customer context), consumed through **Foundry toolboxes** so the servers
     are published, discovered and governed centrally.

  3. **WorkIQ (Agent 365)** — the Microsoft Agent 365 WorkIQ MCP server,
     consumed through a **Foundry toolbox**, giving the agent the employee's
     calendar and documents in their own user context.

Business flows (product explanation, recommendation, contact routing) are loaded
from the ``skills/`` folder so the domain process ships inside the container.

Model calls are routed through Azure AI Foundry using Entra ID (no API keys).

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT             — Foundry project endpoint (required)
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME     — chat model deployment
  AZURE_AI_MODEL_DEPLOYMENT_NAME        — fallback model deployment
  AZURE_SEARCH_ENDPOINT                 — financial products index (required)
  AZURE_SEARCH_ADMIN_KEY                — optional; else DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME       — default: banking-products
  BANK_ID                               — owning bank id ("bank-north"/"bank-south")
  PRODUCT_TOOLBOX_NAME                  — product MCP toolbox (default: product-data-tools)
  CUSTOMER_TOOLBOX_NAME                 — customer MCP toolbox (default: customer-data-tools)
  WORKIQ_TOOLBOX_NAME                   — WorkIQ toolbox (default: workiq-tools)
  PRODUCT_MCP_URL / CUSTOMER_MCP_URL    — direct MCP URLs for local dev (optional)
  WORKIQ_MCP_URL                        — direct WorkIQ MCP URL for local dev (optional)
  EMPLOYEE_WORKIQ_ENABLED               — attach the WorkIQ tool (default: true)
  PORT                                  — host port (default: 8088)

Run the hosted agent server locally from the project root:

    python -m src.employee_advisory_agent.agent
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

import httpx
from agent_framework import MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from dotenv import load_dotenv

# Allow standalone execution from the project root.
_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path if _env_path.exists() else None)

logging.basicConfig(level=logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_MODEL_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)

_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip() or None
_PRODUCT_INDEX = os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products")
_BANK_ID = os.getenv("BANK_ID", "").strip()

# MCP servers are consumed through Foundry toolboxes by default so they are
# governed centrally. The direct *_MCP_URL overrides bypass the toolbox for
# local development.
_PRODUCT_TOOLBOX_NAME = os.getenv("PRODUCT_TOOLBOX_NAME", "product-data-tools")
_PRODUCT_TOOLBOX_ENDPOINT = os.getenv("PRODUCT_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_PRODUCT_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_PRODUCT_MCP_URL = os.getenv("PRODUCT_MCP_URL", "").strip()

_CUSTOMER_TOOLBOX_NAME = os.getenv("CUSTOMER_TOOLBOX_NAME", "customer-data-tools")
_CUSTOMER_TOOLBOX_ENDPOINT = os.getenv("CUSTOMER_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_CUSTOMER_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_CUSTOMER_MCP_URL = os.getenv("CUSTOMER_MCP_URL", "").strip()

_FINBOT_SQL_ENABLED = os.getenv("EMPLOYEE_FINBOT_SQL_ENABLED", "true").strip().lower() == "true"
_FINBOT_SQL_TOOLBOX_NAME = os.getenv("FINBOT_SQL_TOOLBOX_NAME", "finbot-sql-tools")
_FINBOT_SQL_TOOLBOX_ENDPOINT = os.getenv("FINBOT_SQL_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_FINBOT_SQL_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_FINBOT_SQL_MCP_URL = os.getenv("FINBOT_SQL_MCP_URL", "").strip()

_WORKIQ_ENABLED = os.getenv("EMPLOYEE_WORKIQ_ENABLED", "true").strip().lower() == "true"
_WORKIQ_TOOLBOX_NAME = os.getenv("WORKIQ_TOOLBOX_NAME", "workiq-tools")
_WORKIQ_TOOLBOX_ENDPOINT = os.getenv("WORKIQ_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_WORKIQ_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_WORKIQ_MCP_URL = os.getenv("WORKIQ_MCP_URL", "").strip()

_SKILLS_DIR = Path(__file__).parent / "skills"


BASE_INSTRUCTIONS = """\
You are the Employee Advisory Agent, an internal assistant for bank employees.
An employee uses you while advising a customer: to explain product conditions,
look up the customer's context, recommend suitable products and find the right
internal contact.

You reason over these tool surfaces and must always ground claims in them:
  - search_financial_products — the bank's product catalogue and conditions
    (savings, children's savings, credit cards, current accounts) from the
    Financial products index.
  - the product data tools (product_data MCP) — full catalogue, product
    definitions and per-customer holdings.
  - the customer data tools (customer_data MCP, read-only) — the customer's
    profile, accounts and transactions, plus `summarize_spending` (spending
    behaviour by category / merchant) and `get_net_worth` (balance picture
    across all accounts), used only to frame a recommendation.
  - the WorkIQ tools (Microsoft Agent 365) — the employee's own calendar and
    documents, in their user context, to schedule follow-ups or find internal
    material.

Operating principles:
  1. Ground every product statement (rates, fees, eligibility, notice periods)
     in a tool result and cite the source file and numbered section
     (e.g. "savings-products.md §1.2.2.1").
  2. Treat customer data as confidential: only use it for the customer in
     context and never expose one customer's data to another.
  3. When recommending products, match the customer's segment and needs to the
     product conditions; explain the trade-offs, do not oversell.
  4. You give product and process guidance to an employee — not regulated
     financial advice to a customer. For regulatory questions, defer to the
     compliance guidance.
  5. Be concise and decision-ready: lead with the answer, then the cited
     evidence, then the suggested next step.
"""


def _load_skills() -> str:
    """Concatenate every SKILL.md under ``skills/`` into the system prompt."""
    if not _SKILLS_DIR.exists():
        return ""
    parts: list[str] = []
    for skill_file in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        parts.append(skill_file.read_text(encoding="utf-8").strip())
    if not parts:
        return ""
    return "\n\n---\n\n# Domain skills\n\n" + "\n\n---\n\n".join(parts)


EMPLOYEE_AGENT_SYSTEM_PROMPT = BASE_INSTRUCTIONS + _load_skills()


# ---------------------------------------------------------------------------
# Identity / credential
# ---------------------------------------------------------------------------

_credential = DefaultAzureCredential()
_toolbox_token_provider = get_bearer_token_provider(
    _credential, "https://ai.azure.com/.default"
)


class _ToolboxAuth(httpx.Auth):
    """Inject a fresh Entra token on every Foundry toolbox MCP request."""

    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = "Bearer " + self._get_token()
        yield request


def _search_credential():
    """Return an Azure AI Search credential (key if provided, else Entra ID)."""
    if _SEARCH_API_KEY:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(_SEARCH_API_KEY)
    from azure.identity.aio import DefaultAzureCredential as AioDefaultAzureCredential

    return AioDefaultAzureCredential()


# ---------------------------------------------------------------------------
# Financial products search tool (Azure AI Search)
# ---------------------------------------------------------------------------

@tool
async def search_financial_products(
    query: str,
    top: int = 10,
) -> list[dict[str, Any]]:
    """Search the bank's financial products catalogue and conditions.

    Use this to explain a product, compare products or find one that fits a
    customer's need. Returns matching products with their name, description,
    category, tags, owning bank and the source reference (file + section) to
    cite.

    Args:
        query: Free-text query, e.g. "high interest savings with notice period",
            "children's savings", "credit card with travel insurance".
        top: Maximum number of products to return (default 10).
    """
    if not _SEARCH_ENDPOINT:
        return [{"error": "AZURE_SEARCH_ENDPOINT is not configured."}]

    from azure.search.documents.aio import SearchClient

    credential = _search_credential()
    # Scope to the owning bank when BANK_ID is set (products are shared, but a
    # bank instance prefers its own catalogue framing).
    filter_expr = None
    if _BANK_ID:
        safe = _BANK_ID.replace("'", "''")
        filter_expr = f"bank_id eq '{safe}' or bank_id eq 'all'"

    fields = ["name", "description", "category", "tags", "bank_id", "source_ref"]
    client = SearchClient(
        endpoint=_SEARCH_ENDPOINT,
        index_name=_PRODUCT_INDEX,
        credential=credential,
    )
    results: list[dict[str, Any]] = []
    try:
        response = await client.search(
            search_text=query,
            filter=filter_expr,
            select=",".join(fields),
            top=max(1, top),
        )
        async for doc in response:
            results.append({f: doc.get(f) for f in fields})
    finally:
        await client.close()
        close = getattr(credential, "close", None)
        if close is not None:
            await credential.close()
    return results


# ---------------------------------------------------------------------------
# MCP toolbox tools (Foundry toolbox, or direct for local dev)
# ---------------------------------------------------------------------------

def _toolbox_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        auth=_ToolboxAuth(_toolbox_token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )


def _build_mcp_tool(name: str, toolbox_endpoint: str, direct_url: str) -> MCPStreamableHTTPTool:
    """Build an MCP tool, preferring a direct URL for local dev over the toolbox."""
    if direct_url:
        logger.info("Using direct %s MCP endpoint %s", name, direct_url)
        return MCPStreamableHTTPTool(name=name, url=direct_url, load_prompts=False)
    logger.info("Using Foundry toolbox %s endpoint %s", name, toolbox_endpoint)
    return MCPStreamableHTTPTool(
        name=name,
        url=toolbox_endpoint,
        http_client=_toolbox_http_client(),
        load_prompts=False,
    )


# ---------------------------------------------------------------------------
# Agent assembly
# ---------------------------------------------------------------------------

_tools: list = [
    search_financial_products,
    _build_mcp_tool("product-data", _PRODUCT_TOOLBOX_ENDPOINT, _DIRECT_PRODUCT_MCP_URL),
    _build_mcp_tool("customer-data", _CUSTOMER_TOOLBOX_ENDPOINT, _DIRECT_CUSTOMER_MCP_URL),
]
if _WORKIQ_ENABLED:
    _tools.append(_build_mcp_tool("workiq", _WORKIQ_TOOLBOX_ENDPOINT, _DIRECT_WORKIQ_MCP_URL))
if _FINBOT_SQL_ENABLED:
    _tools.append(
        _build_mcp_tool(
            "finbot-sql", _FINBOT_SQL_TOOLBOX_ENDPOINT, _DIRECT_FINBOT_SQL_MCP_URL
        )
    )

_chat_client = FoundryChatClient(
    project_endpoint=_PROJECT_ENDPOINT,
    model=_MODEL_DEPLOYMENT,
    credential=_credential,
)

agent = _chat_client.as_agent(
    name="employee-advisory-agent",
    instructions=EMPLOYEE_AGENT_SYSTEM_PROMPT,
    tools=_tools,
)


if __name__ == "__main__":
    ResponsesHostServer(agent).run()
