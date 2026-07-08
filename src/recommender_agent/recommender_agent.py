"""Recommender Agent — AG-UI web agent (Volksbank personal banking assistant).

A personal banking assistant for Volksbank customers. It answers everyday
questions about the customer's accounts and finances, explains products, and
proactively recommends suitable Volksbank / genossenschaftliche FinanzGruppe
products (Union Investment, R+V Versicherung, Bausparkasse Schwäbisch Hall,
easyCredit/TeamBank).

It is grounded on:

  1. **Fabric data agent** — live account and transaction data via a Microsoft
     Fabric data agent reached through a Foundry project connection
     (``FoundryChatClient.get_fabric_tool()``).

  2. **Finance MCP server** — compound-interest and discounted-cash-flow
     calculations, consumed through a Foundry toolbox (or a direct MCP URL
     for local development).

  3. **Financial products index** — the ``banking-products`` Azure AI Search
     index for product discovery and explanations, surfaced as a context
     provider.

Write operations (order product, cancel product, update contact details) are
strictly human-in-the-loop: the agent previews, asks for confirmation, then
commits only after an explicit "yes".

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
  FABRIC_CONNECTION_ID                    — Foundry project connection ID (required)
  FINANCE_TOOLBOX_NAME                    — finance MCP toolbox (default: finance-tools)
  FINANCE_MCP_URL                         — direct MCP URL for local dev (optional)
  COMPLIANCE_A2A_ENABLED                  — consume Compliance agent over A2A (default: false)
  AZURE_AI_COMPLIANCE_AGENT_NAME          — compliance hosted-agent name (default: compliance-agent)
  COMPLIANCE_AGENT_A2A_URL                — direct A2A endpoint override (auto-derived if unset)
  COMPLIANCE_AGENT_AUDIENCE               — Entra audience (default: https://ai.azure.com)
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

# Customer and product data via Microsoft Fabric data agents.
_FABRIC_CONNECTION_ID = os.environ["FABRIC_CONNECTION_ID"]

# Finance MCP server — compound interest / DCF calculations.
_FINANCE_TOOLBOX_NAME = os.getenv("FINANCE_TOOLBOX_NAME", "finance-tools")
_FINANCE_TOOLBOX_ENDPOINT = os.getenv("FINANCE_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_FINANCE_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_FINANCE_MCP_URL = os.getenv("FINANCE_MCP_URL", "").strip()

# Cross-organisation A2A: optionally consume Bank North's Compliance agent.
_COMPLIANCE_A2A_ENABLED = os.getenv(
    "COMPLIANCE_A2A_ENABLED", "false"
).strip().lower() in {"1", "true", "yes", "on"}
_COMPLIANCE_AGENT_NAME = os.getenv("AZURE_AI_COMPLIANCE_AGENT_NAME", "compliance-agent")
_COMPLIANCE_A2A_URL = os.getenv("COMPLIANCE_AGENT_A2A_URL", "").strip() or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/agents/{_COMPLIANCE_AGENT_NAME}/endpoint/protocols/a2a"
)
_COMPLIANCE_A2A_AUDIENCE = os.getenv(
    "COMPLIANCE_AGENT_AUDIENCE", "https://ai.azure.com"
).strip()

_SKILLS_DIR = Path(__file__).parent / "skills"


BASE_INSTRUCTIONS = """\
Du bist ein persönlicher Banking-Assistent der Volksbank. Du hilfst dem eingeloggten Nutzer,
Informationen zu seinen eigenen Konten und Finanzdaten abzurufen und verständlich zu erklären.
Du kannst Produkte erklären und Empfehlungen geben, buchen und kündigen.

## Deine Fähigkeiten
- Du hast Zugriff auf einen Genie Space ('AAP Daten'),
  über den du strukturierte Kontodaten abfragen kannst (z. B. Kontostand, Transaktionen,
  Konto-Übersichten, Salden über die Zeit).
- Nutze das Genie-Tool für jede Frage, die echte Kontodaten erfordert. Erfinde niemals
  Zahlen, Salden oder Transaktionen.
- Mit dem Tool `get_current_time` kannst du das aktuelle Datum/die Uhrzeit ermitteln,
  z. B. für Anfragen wie "letzten Monat" oder "dieses Jahr".
- Über die Tools des `mcp-finbot-writer` kannst du schreibende Aktionen ausführen
  (z. B. Daten anlegen, ändern oder löschen).
- Mit den Finance-Tools (`calculate_compound_interest`, `discount_cashflow`) kannst du
  Zinsberechnungen und Barwertanalysen für den Kunden durchführen.

## Human-in-the-Loop für schreibende Aktionen (VERBINDLICH)
Bevor du ein schreibendes Tool aufrufst:
1. Lege dem Nutzer in einer kurzen, klaren Nachricht vor, was genau ausgeführt werden soll:
   die geplante Aktion, das betroffene Tool und alle konkreten Werte/Parameter.
2. Stelle genau eine Rückfrage, z. B.: „Soll ich das so ausführen? (ja/nein)".
3. Rufe das Tool ERST auf, nachdem der Nutzer eindeutig zugestimmt hat (z. B. „ja",
   „bestätige", „mach das"). Bei „nein", Unklarheit oder Korrekturwunsch führst du nichts
   aus, sondern passt den Vorschlag an und fragst erneut.

Lesende Aktionen benötigen KEINE Bestätigung und werden direkt ausgeführt.

## Deine Rolle als Volksbank-Berater (VERBINDLICH)
- Du bist ein Berater der Volksbank. Empfiehl dem Kunden auch proaktiv passende
  Produkte und Dienstleistungen aus dem Volksbank-Portfolio bzw. der
  genossenschaftlichen FinanzGruppe (z. B. Union Investment, R+V Versicherung,
  Bausparkasse Schwäbisch Hall, easyCredit/TeamBank).
- Erkenne aus dem Kontext der Unterhaltung passende Anlässe und biete proaktiv eine
  passende Lösung an. Beispiele:
  - Der Kunde plant oder sucht eine Reise → empfiehl die Reise-Kreditkarte und/oder
    die R+V Reiseversicherung.
  - Der Kunde plant eine größere Anschaffung → empfiehl z. B. easyCredit oder ein
    passendes Sparprodukt.
  - Der Kunde hat freie Liquidität auf dem Konto → empfiehl eine Geldanlage mit
    Union Investment oder ein Tagesgeld/Sparprodukt der Volksbank.
- Bring deine Empfehlungen natürlich und freundlich ein, ohne aufdringlich zu wirken.
  Stelle die Produktvorteile ehrlich dar und erfinde keine Konditionen oder Zinssätze.
  Wenn dir konkrete Konditionen fehlen, verweise auf die persönliche Beratung in der
  Volksbank.

## Sidebar aktuell halten (VERBINDLICH)
- Rufe `update_overview` auf, sobald sich das Kontobild oder eine ausstehende Aktion ändert —
  immer BEVOR du die Chat-Antwort schreibst.

## Stil
- Antworte auf Deutsch, freundlich, knapp und präzise.
- Stelle Salden und Übersichten gut lesbar dar (z. B. als kurze Liste oder Tabelle).
- Erkläre Finanzbegriffe nur auf Nachfrage oder wenn es zum Verständnis nötig ist.
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
) -> tuple[AzureAISearchContextProvider, OpenAIEmbeddingClient | None]:
    """Build the Financial products context provider and the embedding client."""
    embedding_client = _make_embedding_client(credential)
    product_provider = _make_product_provider(credential, embedding_client)
    return product_provider, embedding_client


# ---------------------------------------------------------------------------
# Fabric data agent tools (Foundry project connections)
# ---------------------------------------------------------------------------


def make_fabric_tools(credential: DefaultAzureCredential) -> list:
    """Build the Fabric data agent tool for live account/transaction data."""
    chat_client = FoundryChatClient(
        project_endpoint=_PROJECT_ENDPOINT,
        model=_MODEL,
        credential=credential,
        allow_preview=True,
    )
    return [
        chat_client.get_fabric_tool(connection_id=_FABRIC_CONNECTION_ID).as_dict(),
    ]


# ---------------------------------------------------------------------------
# Finance MCP toolbox (compound interest / DCF calculations)
# ---------------------------------------------------------------------------


def make_finance_mcp_tool(credential: DefaultAzureCredential):
    """Build the Finance MCP streamable-HTTP tool.

    Uses the Foundry toolbox endpoint by default; falls back to a direct MCP
    URL when ``FINANCE_MCP_URL`` is set (local development).

    Returns a configured ``MCPStreamableHTTPTool`` or ``None`` when neither
    a toolbox endpoint nor a direct URL is reachable.
    """
    from agent_framework import MCPStreamableHTTPTool

    mcp_url = _DIRECT_FINANCE_MCP_URL or _FINANCE_TOOLBOX_ENDPOINT
    if not mcp_url:
        logger.warning("Finance MCP URL not configured; financial calculations unavailable.")
        return None

    if _DIRECT_FINANCE_MCP_URL:
        logger.info("Finance MCP: using direct URL %s", mcp_url)
        return MCPStreamableHTTPTool(url=mcp_url)

    token_provider = get_bearer_token_provider(credential, "https://ai.azure.com/.default")

    import httpx

    class _ToolboxAuth(httpx.Auth):
        def auth_flow(self, request):
            request.headers["Authorization"] = "Bearer " + token_provider()
            yield request

    logger.info("Finance MCP: using Foundry toolbox %s", mcp_url)
    return MCPStreamableHTTPTool(
        url=mcp_url,
        http_client=httpx.AsyncClient(auth=_ToolboxAuth(), headers={"Foundry-Features": "Toolboxes=V1Preview"}),
    )


# ---------------------------------------------------------------------------
# Cross-organisation A2A tool (optional Compliance agent)
# ---------------------------------------------------------------------------

_COMPLIANCE_TOOL_DESCRIPTION = (
    "Ask the Compliance agent a regulatory, KYC/AML, sanctions, fraud or "
    "product-eligibility question. Use it before recommending a product to a "
    "customer who may have eligibility constraints. "
    "Gather the customer's relevant data first and pass a structured, "
    "self-contained question including the scenario, the product category, and "
    "the customer's KYC status, segment, nationality, and existing holdings."
)


def make_compliance_a2a_tool(credential: DefaultAzureCredential):
    """Build the cross-org Compliance A2A tool, or ``(None, None)`` if disabled."""
    if not _COMPLIANCE_A2A_ENABLED:
        logger.info("Compliance A2A disabled.")
        return None, None

    from a2a.client.middleware import ClientCallInterceptor
    from agent_framework.a2a import A2AAgent

    token_provider = get_bearer_token_provider(
        credential, f"{_COMPLIANCE_A2A_AUDIENCE.rstrip('/')}/.default"
    )

    class _BearerTokenInterceptor(ClientCallInterceptor):
        def __init__(self, get_token):
            self._get_token = get_token

        async def intercept(
            self, method_name, request_payload, http_kwargs, agent_card, context
        ):
            headers = dict(http_kwargs.get("headers") or {})
            headers["Authorization"] = "Bearer " + await self._get_token()
            http_kwargs["headers"] = headers
            return request_payload, http_kwargs

    logger.info("Wiring Compliance A2A agent at %s", _COMPLIANCE_A2A_URL)
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
            "A structured compliance question including the scenario, product, and "
            "the customer's relevant data-model facts (age, nationality, kyc_status, "
            "segment, existing holdings). Mark unknown fields as 'unknown'."
        ),
    )
    return tool, a2a_agent
