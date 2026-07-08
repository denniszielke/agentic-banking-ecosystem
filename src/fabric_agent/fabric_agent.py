"""Fabric-agent edition (Bank South consumer channel).

The consumer-facing agent behind the customer web app. It answers a banking
customer's everyday questions — "what is my balance?", "list my transactions
from last month", "what products do I have?", "explain this savings account",
"where is my nearest branch?" — and can start a product order (human-in-the-loop).

It is grounded on a single Azure AI Search index (surfaced as a context
provider):

  1. **Financial products** (``banking-products``) — product discovery and
     explanations.

Compliance / regulatory grounding is NOT bundled into this agent. It is only
available when Bank North's Compliance agent is linked over A2A
(``COMPLIANCE_A2A_ENABLED=true``), exposed as the ``ask_compliance`` tool. When
the A2A link is absent the agent has no compliance grounding and must defer
regulatory / eligibility questions to a human adviser.

It reaches the customer's live data through a Microsoft Fabric data agent,
accessed via a Foundry project connection using ``FoundryChatClient.get_fabric_tool()``.

Business flows are loaded from the ``skills/`` folder so the domain process
ships inside the container image.

Environment variables:
  AZURE_SEARCH_ENDPOINT                   — required
  AZURE_SEARCH_ADMIN_KEY                  — optional; else DefaultAzureCredential
  AZURE_SEARCH_PRODUCT_INDEX_NAME         — default: banking-products
  AZURE_AI_PROJECT_ENDPOINT               — Foundry project endpoint (required)
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME       — model deployment name
  AZURE_AI_MODEL_DEPLOYMENT_NAME          — fallback model name
  AZURE_OPENAI_ENDPOINT                   — Azure OpenAI endpoint for embeddings
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME  — embedding model for hybrid search
  FABRIC_CONNECTION_ID                    — Foundry project connection ID shared by both Fabric data agents (required)
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from agent_framework.azure import AzureAISearchContextProvider
from agent_framework.foundry import FoundryChatClient
from agent_framework.openai import OpenAIEmbeddingClient
from azure.identity.aio import DefaultAzureCredential, get_bearer_token_provider
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

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_MODEL = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)
_AOAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT", "").strip()
_EMBEDDING_MODEL = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "").strip()

# Customer and product data are accessed via Microsoft Fabric data agents
# through a shared Foundry project connection.
_FABRIC_CONNECTION_ID = os.environ["FABRIC_CONNECTION_ID"]

# Cross-organisation A2A: Bank South's customer support agent can consume Bank
# North's Compliance agent as an A2A service (narrative edge 4). This is the
# core cross-org story — a real agent-to-agent call across subscription/tenant
# boundaries, authenticated with Entra ID. It is opt-in: when
# COMPLIANCE_A2A_ENABLED is truthy the agent gains an ``ask_compliance`` tool
# backed by the remote agent. When it is disabled the agent has NO compliance
# grounding at all — there is no local compliance index fallback — and it must
# defer regulatory / eligibility questions to a human adviser.
_COMPLIANCE_A2A_ENABLED = os.getenv(
    "COMPLIANCE_A2A_ENABLED", "false"
).strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_COMPLIANCE_AGENT_NAME = os.getenv("AZURE_AI_COMPLIANCE_AGENT_NAME", "compliance-agent")
# Direct A2A endpoint override; otherwise derive the Foundry hosted-agent A2A
# endpoint from the project endpoint + agent name (see agent_deploy_helpers).
_COMPLIANCE_A2A_URL = os.getenv("COMPLIANCE_AGENT_A2A_URL", "").strip() or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/agents/{_COMPLIANCE_AGENT_NAME}/endpoint/protocols/a2a"
)
# Entra audience for the bearer token sent to the compliance agent. Foundry
# hosted agents accept the Foundry scope; override for a custom audience.
_COMPLIANCE_A2A_AUDIENCE = os.getenv(
    "COMPLIANCE_AGENT_AUDIENCE", "https://ai.azure.com"
).strip()

_SKILLS_DIR = Path(__file__).parent / "skills"


BASE_INSTRUCTIONS = """\
You are the Customer Support Agent for Bank South's retail customers. You help a
signed-in customer with their everyday banking questions and self-service tasks.

You can:
  - Answer account questions — balance, transactions (by date range), and the
    customer's personal details — using the Fabric data agent.
  - List and explain the customer's product holdings, and discover or compare
    catalogue products, using the Fabric data agent and the Financial products
    knowledge.
  - Answer branch questions (nearest branch, opening hours, what a branch
    offers) from the branch directory grounding.
  - Start a product order (e.g. a new savings account or credit card) — this is
    a write operation and is ALWAYS human-in-the-loop.
  - Proactively spot an optimisation for the customer (e.g. a large uninvested
    balance on their current account) and — only after asking permission — offer
    two concrete, personalised recommendations (a reshuffle with a concrete
    annual interest gain, and a suitable product).
  - When available, consult Bank North's Compliance agent over A2A via the
    ask_compliance tool for a regulatory / eligibility decision, and relay its
    cited guidance.

Operating principles:
  1. You only ever act for the ONE signed-in customer in context. Never reveal
     or act on another customer's data.
  2. Ground every factual claim (balances, transactions, product conditions,
     branch details) in a tool result, and name the source — the Fabric data
     agent, or the knowledge file and its numbered section (e.g. "bank-south.md §2.1").
  3. For any regulatory, eligibility or advice question, you have NO built-in
     compliance grounding. If the ask_compliance tool is available, consult it
     for a compliance decision and cite its answer. Before you call it, gather
     the signed-in customer's relevant data from the Fabric data agent and
     send a structured, self-contained question — the scenario, the specific
     product with its category/credit exposure, and the customer's fields
     (derived age, nationality, tax_residency, kyc_status, segment, existing
     holdings and whether a reference account exists) — so the answer is specific
     to this customer, per the compliance-consultation skill. If ask_compliance
     is NOT available, do not answer from your own knowledge — tell the customer
     the compliance service is unavailable and defer the question to a human
     adviser. Always defer personalised financial advice to a human adviser.
  4. Never commit a write operation without an explicit confirmation step:
     preview the change, ask the customer to confirm, and only then proceed.
  5. Be proactive but never pushy: only raise an optimisation once the
     customer's immediate question is handled, always ask permission before
     making suggestions, and stay silent when detect_opportunities finds nothing.
  6. Keep the sidebar in sync: whenever the account picture or a pending action
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


def _make_embedding_client(
    credential: DefaultAzureCredential,
) -> OpenAIEmbeddingClient | None:
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


def make_providers(
    credential: DefaultAzureCredential,
) -> tuple[
    AzureAISearchContextProvider,
    OpenAIEmbeddingClient | None,
]:
    """Build the Financial products context provider and the embedding client.

    Returns ``(product_provider, embedding_client)``. The provider is an async
    context manager — the caller enters/exits it. Compliance grounding is not
    included here; it is only available via the ``ask_compliance`` A2A tool.
    """
    embedding_client = _make_embedding_client(credential)
    product_provider = _make_product_provider(credential, embedding_client)
    return product_provider, embedding_client


# ---------------------------------------------------------------------------
# Fabric data agent tools (Foundry project connections)
# ---------------------------------------------------------------------------


def make_fabric_tools(credential: DefaultAzureCredential) -> list:
    """Build the Fabric data agent tool.

    Uses ``FoundryChatClient.get_fabric_tool()`` to create a Microsoft Fabric
    data agent tool configuration backed by a single Foundry project connection.
    ``allow_preview=True`` is required so the underlying AIProjectClient
    sends the ``Foundry-Features`` header that unlocks preview tool types.
    """
    chat_client = FoundryChatClient(
        project_endpoint=_PROJECT_ENDPOINT,
        model=_MODEL,
        credential=credential,
        allow_preview=True,
    )
    # Serialise to plain wire dicts via as_dict(): the Foundry client shallow-copies
    # hosted-tool mappings, so the nested FabricDataAgentToolParameters model would
    # otherwise reach json.dumps and raise "not JSON serializable".
    return [
        chat_client.get_fabric_tool(connection_id=_FABRIC_CONNECTION_ID).as_dict(),
    ]


# ---------------------------------------------------------------------------
# Cross-organisation A2A tool (Bank South -> Bank North Compliance agent)
# ---------------------------------------------------------------------------

_COMPLIANCE_TOOL_DESCRIPTION = (
    "Ask Bank North's Compliance agent (a cross-organisation A2A service) a "
    "regulatory, KYC/AML, sanctions, fraud or product-eligibility question. Use "
    "it whenever a customer request needs a compliance decision or a rule you "
    "must cite before acting (e.g. eligibility for a product order). "
    "IMPORTANT: gather the signed-in customer's data first (get_customer, "
    "list_accounts) and pass a structured, self-contained question that includes "
    "the scenario, the specific product with its category/credit exposure, and "
    "the customer's relevant fields (derived age, nationality, tax_residency, "
    "kyc_status, segment, existing holdings and whether a reference account "
    "exists) — see the compliance-consultation skill. A question carrying the "
    "customer facts yields a specific, field-level answer; a bare question yields "
    "a generic one. The remote agent returns grounded guidance with cited "
    "sources; relay the decision and the citation, and defer to it rather than "
    "guessing."
)


def make_compliance_a2a_tool(credential: DefaultAzureCredential):
    """Build the cross-org Compliance A2A tool, or ``(None, None)`` if disabled.

    When ``COMPLIANCE_A2A_ENABLED`` is truthy, wraps Bank North's Compliance
    hosted agent (exposed over A2A) as an ``ask_compliance`` function tool so the
    customer support agent can consult it across organisational boundaries. Each
    A2A request is authenticated with a fresh Entra bearer token for the Foundry
    audience, injected via an A2A client interceptor (minted per request from the
    shared credential).

    Returns ``(tool, a2a_agent)`` where ``a2a_agent`` is an async context manager
    the caller must enter/exit for the app lifetime, or ``(None, None)`` when the
    A2A integration is disabled.
    """
    if not _COMPLIANCE_A2A_ENABLED:
        logger.info("Compliance A2A disabled; using the Compliance rules index only.")
        return None, None

    # Imported lazily so the module still loads where agent-framework-a2a is not
    # installed and the A2A integration is switched off.
    from a2a.client.middleware import ClientCallInterceptor
    from agent_framework.a2a import A2AAgent

    token_provider = get_bearer_token_provider(
        credential, f"{_COMPLIANCE_A2A_AUDIENCE.rstrip('/')}/.default"
    )

    class _BearerTokenInterceptor(ClientCallInterceptor):
        """Attach a fresh Entra bearer token to every outgoing A2A request.

        The built-in ``AuthInterceptor`` only injects credentials declared in the
        remote agent card's security schemes; a URL-derived minimal card has
        none, so we set the Authorization header unconditionally instead.
        """

        def __init__(self, get_token):
            self._get_token = get_token

        async def intercept(
            self, method_name, request_payload, http_kwargs, agent_card, context
        ):
            headers = dict(http_kwargs.get("headers") or {})
            headers["Authorization"] = "Bearer " + await self._get_token()
            http_kwargs["headers"] = headers
            return request_payload, http_kwargs

    logger.info("Wiring cross-org Compliance A2A agent at %s", _COMPLIANCE_A2A_URL)
    # Do NOT pass a custom http_client: when one is supplied together with a
    # URL-derived card, A2AAgent leaves _close_http_client unset and its
    # __aexit__ fails / leaks the client. Letting A2AAgent own the client keeps
    # cleanup correct; auth is applied through the interceptor above.
    a2a_agent = A2AAgent(
        name="compliance",
        url=_COMPLIANCE_A2A_URL,
        auth_interceptor=_BearerTokenInterceptor(token_provider),
        timeout=120.0,
    )
    tool = a2a_agent.as_tool(
        name="ask_compliance",
        description=_COMPLIANCE_TOOL_DESCRIPTION,
        arg_name="question",
        arg_description=(
            "A structured, self-contained compliance question. Include the "
            "scenario and specific product (with category/credit exposure) plus "
            "the customer's relevant data-model facts — derived age and DOB, "
            "nationality, tax_residency, kyc_status, segment, customer-since "
            "year, and existing holdings (including whether a reference account "
            "exists). Ask it to list every required field/document, each one's "
            "required state, and the determination with citations. Mark any fact "
            "you could not fetch as 'unknown' rather than omitting it."
        ),
    )
    return tool, a2a_agent
