"""Customer Support Agent — agent-framework edition (Bank South consumer channel).

The consumer-facing agent behind the customer web app. It answers a banking
customer's everyday questions — "what is my balance?", "list my transactions
from last month", "what products do I have?", "explain this savings account",
"where is my nearest branch?" — and can start a product order (human-in-the-loop).

It is grounded on two Azure AI Search indexes (surfaced as context providers):

  1. **Financial products** (``banking-products``) — product discovery and
     explanations.
  2. **Compliance rules** (``banking-compliance``) — guardrails for
     regulatory / advice questions.

and reaches the customer's live data through two MCP servers:

  * ``customer_data_mcp_server`` — balances, transactions, personal details.
  * ``product_data_mcp_server`` — list / explain products, order a product.

MCP servers are consumed through **Foundry toolboxes** by default (governed
centrally); a direct ``*_MCP_URL`` override connects straight to the server for
local development or intra-environment calls.

Business flows are loaded from the ``skills/`` folder so the domain process
ships inside the container image.

Environment variables:
  AZURE_SEARCH_ENDPOINT                   — required
  AZURE_SEARCH_ADMIN_KEY                  — optional; else DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME         — default: banking-products
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME      — default: banking-compliance
  AZURE_AI_PROJECT_ENDPOINT               — Foundry project endpoint (required)
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME       — model deployment name
  AZURE_AI_MODEL_DEPLOYMENT_NAME          — fallback model name
  AZURE_OPENAI_ENDPOINT                   — Azure OpenAI endpoint for embeddings
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME  — embedding model for hybrid search
  CUSTOMER_TOOLBOX_NAME / CUSTOMER_MCP_URL — customer MCP toolbox / direct URL
  PRODUCT_TOOLBOX_NAME / PRODUCT_MCP_URL   — product MCP toolbox / direct URL
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx
from agent_framework import MCPStreamableHTTPTool
from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.openai import OpenAIEmbeddingClient
from azure.identity import DefaultAzureCredential as SyncDefaultAzureCredential
from azure.identity import get_bearer_token_provider
from azure.identity.aio import DefaultAzureCredential
from dotenv import load_dotenv

# Allow standalone execution / uvicorn module loading from the project root.
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

_SEARCH_ENDPOINT = os.environ["AZURE_SEARCH_ENDPOINT"]
_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip() or None

_PRODUCT_INDEX = os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products")
_COMPLIANCE_INDEX = os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance")

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_MODEL = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)
_AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
_EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "").strip()

# MCP servers — Foundry toolbox by default, direct URL override for local dev.
_CUSTOMER_TOOLBOX_NAME = os.getenv("CUSTOMER_TOOLBOX_NAME", "customer-data-tools")
_CUSTOMER_TOOLBOX_ENDPOINT = os.getenv("CUSTOMER_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_CUSTOMER_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_CUSTOMER_MCP_URL = os.getenv("CUSTOMER_MCP_URL", "").strip()

_PRODUCT_TOOLBOX_NAME = os.getenv("PRODUCT_TOOLBOX_NAME", "product-data-tools")
_PRODUCT_TOOLBOX_ENDPOINT = os.getenv("PRODUCT_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_PRODUCT_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_PRODUCT_MCP_URL = os.getenv("PRODUCT_MCP_URL", "").strip()

_SKILLS_DIR = Path(__file__).parent / "skills"


BASE_INSTRUCTIONS = """\
You are the Customer Support Agent for Bank South's retail customers. You help a
signed-in customer with their everyday banking questions and self-service tasks.

You can:
  - Answer account questions — balance, transactions (by date range), and the
    customer's personal details — using the customer data MCP tools.
  - List and explain the customer's product holdings, and discover or compare
    catalogue products, using the product data MCP tools and the Financial
    products knowledge.
  - Answer branch questions (nearest branch, opening hours, what a branch
    offers) from the branch directory grounding.
  - Start a product order (e.g. a new savings account or credit card) — this is
    a write operation and is ALWAYS human-in-the-loop.

Operating principles:
  1. You only ever act for the ONE signed-in customer in context. Never reveal
     or act on another customer's data.
  2. Ground every factual claim (balances, transactions, product conditions,
     branch details) in a tool result, and name the source — the MCP tool, or
     the knowledge file and its numbered section (e.g. "bank-south.md §2.1").
  3. For any regulatory, eligibility or advice question, apply the compliance
     guardrails first; if it needs personalised financial advice or a
     compliance decision, say so and defer to compliance / a human adviser
     rather than guessing.
  4. Never commit a write (order_product, update_customer) without an explicit
     confirmation step: preview the change, ask the customer to confirm, and
     only then commit with confirm=true.
  5. Keep the sidebar in sync: whenever the account picture or a pending action
     changes, call update_overview with the complete current state BEFORE you
     write your chat reply.

Be warm, clear and concise. Lead with the answer, then the supporting detail.
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


SYSTEM_PROMPT = BASE_INSTRUCTIONS + _load_skills()


# ---------------------------------------------------------------------------
# Semantic provider with full-field extraction
# ---------------------------------------------------------------------------

class _FlatFieldContextProvider(AzureAISearchContextProvider):
    """Semantic provider that surfaces every flat scalar field, not just strings."""

    _SKIP_FIELDS = frozenset({"description_vector", "scenario_vector", "embedding"})

    def _extract_document_text(self, doc: dict, doc_id: str | None = None) -> str:  # type: ignore[override]
        parts: list[str] = []
        for key, value in doc.items():
            if key.startswith("@") or key in self._SKIP_FIELDS or value is None:
                continue
            parts.append(f"{key}: {value}")
        text = " | ".join(parts)
        if doc_id and text:
            return f"[Source: {doc_id}] {text}"
        return text


# ---------------------------------------------------------------------------
# Context provider factories
# ---------------------------------------------------------------------------

def _make_embedding_client(credential: DefaultAzureCredential) -> OpenAIEmbeddingClient | None:
    """Return an embedding client for hybrid search, or None if not configured."""
    if _AOAI_ENDPOINT and _EMBEDDING_MODEL:
        return OpenAIEmbeddingClient(
            azure_endpoint=_AOAI_ENDPOINT,
            model=_EMBEDDING_MODEL,
            credential=credential,
        )
    return None


def _make_product_provider(
    credential: DefaultAzureCredential,
    embedding_client: OpenAIEmbeddingClient | None,
) -> AzureAISearchContextProvider:
    """Semantic provider for the Financial products index — product discovery."""
    return _FlatFieldContextProvider(
        source_id="financial_products",
        endpoint=_SEARCH_ENDPOINT,
        index_name=_PRODUCT_INDEX,
        api_key=_SEARCH_API_KEY,
        credential=credential if not _SEARCH_API_KEY else None,
        mode="semantic",
        top_k=15,
        embedding_function=embedding_client,
        vector_field_name="description_vector" if embedding_client else None,
    )


def _make_compliance_provider(
    credential: DefaultAzureCredential,
    embedding_client: OpenAIEmbeddingClient | None,
) -> AzureAISearchContextProvider:
    """Semantic provider for the Compliance rules index — guardrails."""
    return _FlatFieldContextProvider(
        source_id="compliance_rules",
        endpoint=_SEARCH_ENDPOINT,
        index_name=_COMPLIANCE_INDEX,
        api_key=_SEARCH_API_KEY,
        credential=credential if not _SEARCH_API_KEY else None,
        mode="semantic",
        top_k=10,
        embedding_function=embedding_client,
        vector_field_name="description_vector" if embedding_client else None,
    )


def make_providers(
    credential: DefaultAzureCredential,
) -> tuple[
    AzureAISearchContextProvider,
    AzureAISearchContextProvider,
    OpenAIEmbeddingClient | None,
]:
    """Build the two Azure AI Search context providers and the embedding client.

    Returns ``(product_provider, compliance_provider, embedding_client)``. The
    providers are async context managers — the caller enters/exits them.
    """
    embedding_client = _make_embedding_client(credential)
    product_provider = _make_product_provider(credential, embedding_client)
    compliance_provider = _make_compliance_provider(credential, embedding_client)
    return product_provider, compliance_provider, embedding_client


# ---------------------------------------------------------------------------
# MCP tools (Foundry toolbox, or direct for local dev / intra-environment)
# ---------------------------------------------------------------------------

_sync_credential = SyncDefaultAzureCredential()
_toolbox_token_provider = get_bearer_token_provider(
    _sync_credential, "https://ai.azure.com/.default"
)


class _ToolboxAuth(httpx.Auth):
    """Inject a fresh Entra token on every Foundry toolbox MCP request."""

    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = "Bearer " + self._get_token()
        yield request


def _build_mcp_tool(name: str, toolbox_endpoint: str, direct_url: str) -> MCPStreamableHTTPTool:
    """Build an MCP tool, preferring a direct URL over the Foundry toolbox."""
    if direct_url:
        logger.info("Using direct %s MCP endpoint %s", name, direct_url)
        return MCPStreamableHTTPTool(name=name, url=direct_url, load_prompts=False)
    logger.info("Using Foundry toolbox %s endpoint %s", name, toolbox_endpoint)
    http_client = httpx.AsyncClient(
        auth=_ToolboxAuth(_toolbox_token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )
    return MCPStreamableHTTPTool(
        name=name,
        url=toolbox_endpoint,
        http_client=http_client,
        load_prompts=False,
    )


def make_mcp_tools() -> list[MCPStreamableHTTPTool]:
    """Build the customer-data and product-data MCP tools."""
    return [
        _build_mcp_tool("customer-data", _CUSTOMER_TOOLBOX_ENDPOINT, _DIRECT_CUSTOMER_MCP_URL),
        _build_mcp_tool("product-data", _PRODUCT_TOOLBOX_ENDPOINT, _DIRECT_PRODUCT_MCP_URL),
    ]
