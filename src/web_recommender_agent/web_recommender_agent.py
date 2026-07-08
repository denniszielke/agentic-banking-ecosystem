"""Web Recommender Agent — AG-UI Volksbank banking assistant.

Agent logic and tool definitions for the web_recommender_agent AG-UI server.
Tools:
  - update_overview          AG-UI sidebar push (customer, accounts, pending)
  - Fabric data agent        live account/transaction data (OBO connection)
  - Finance MCP              compound interest / DCF (direct URL, no auth)
  - submit_product_recommendation  CRM write (always requires confirmation)

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT     Foundry project endpoint (required).
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME / AZURE_AI_MODEL_DEPLOYMENT_NAME
  FABRIC_CONNECTION_ID          Fabric OBO connection name (default: fabric_dataagent_obo).
  FINANCE_MCP_URL               Direct finance MCP URL.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

import httpx
from agent_framework import Agent, Content, MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_ag_ui import state_update
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent / "skills"
_MOCK_CRM_MODULE = Path(__file__).parent / "mock_crm.py"

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_MODEL = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)
_FABRIC_CONNECTION_ID = os.getenv("FABRIC_CONNECTION_ID", "fabric_dataagent_obo")
_FINANCE_MCP_URL = os.getenv(
    "FINANCE_MCP_URL",
    "https://finance-mcp-server.whitemoss-40897c95.swedencentral.azurecontainerapps.io/mcp",
)

# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

BASE_INSTRUCTIONS = """\
Du bist ein persönlicher Banking-Assistent der Volksbank. Du hilfst dem eingeloggten Nutzer,
Informationen zu seinen eigenen Konten und Finanzdaten abzurufen und verständlich zu erklären.
Du kannst Produkte erklären und Empfehlungen geben.

## Deine Fähigkeiten
- Du hast Zugriff auf einen **Fabric Data Agent**, über den du strukturierte Kontodaten
  abfragen kannst (z. B. Kontostand, Transaktionen, Konto-Übersichten, Salden über die Zeit).
  Nutze dieses Tool für jede Frage, die echte Kontodaten erfordert. Erfinde niemals
  Zahlen, Salden oder Transaktionen.
- Mit dem Tool `get_current_time` kannst du das aktuelle Datum/die Uhrzeit ermitteln,
  z. B. für Anfragen wie "letzten Monat" oder "dieses Jahr".
- Mit den Finance-Tools (`calculate_compound_interest`, `discount_cashflow`) kannst du
  Zinsberechnungen und Barwertanalysen für den Kunden durchführen.

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
  Wenn dir konkrete Konditionen fehlen, verweise auf die persönliche Beratung in der Volksbank.
- Wenn der Kunde Interesse an einem Produkt signalisiert, biete ihm an, eine Empfehlung
  im CRM zu hinterlegen, damit ein menschlicher Berater sich meldet. Nutze dazu das
  Tool `submit_product_recommendation`. Dieses Tool erfordert immer eine explizite
  Bestätigung durch den Nutzer, bevor es ausgeführt wird.

## Sidebar aktuell halten (VERBINDLICH)
- Rufe `update_overview` auf, sobald du Kundendaten oder Konten geladen hast —
  immer BEVOR du die Chat-Antwort schreibst.

## Stil
- Antworte auf Deutsch, freundlich, knapp und präzise.
- Stelle Salden und Übersichten gut lesbar dar (z. B. als kurze Liste oder Tabelle).
- Erkläre Finanzbegriffe nur auf Nachfrage oder wenn es zum Verständnis nötig ist.
"""


def _load_skills() -> str:
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
# AG-UI sidebar state schema
# ---------------------------------------------------------------------------

class CustomerProfile(BaseModel):
    customer_id: Optional[str] = Field(default=None)
    full_name: Optional[str] = Field(default=None)
    bank: Optional[str] = Field(default=None)
    segment: Optional[str] = Field(default=None)


class AccountRow(BaseModel):
    account_id: str
    product_name: str
    kind: str = Field(default="account")
    balance: Optional[float] = Field(default=None)
    status: Optional[str] = Field(default=None)


class PendingAction(BaseModel):
    kind: Optional[str] = Field(default=None)
    summary: Optional[str] = Field(default=None)
    awaiting_confirmation: bool = Field(default=False)


@tool
def update_overview(
    customer: CustomerProfile,
    accounts: List[AccountRow],
    pending: PendingAction,
) -> Content:
    """Refresh the live sidebar (customer, accounts, pending action).

    Call this whenever account data changes or a pending action starts/ends.
    Always pass the COMPLETE current state. Call BEFORE writing the chat reply.
    """
    return state_update(
        text="Übersicht aktualisiert.",
        state={
            "customer": CustomerProfile.model_validate(customer).model_dump(),
            "accounts": [AccountRow.model_validate(a).model_dump() for a in accounts],
            "pending": PendingAction.model_validate(pending).model_dump(),
        },
    )


# ---------------------------------------------------------------------------
# CRM submission tool (always requires confirmation)
# ---------------------------------------------------------------------------

@tool(approval_mode="always_require")
def submit_product_recommendation(
    customer_id: str,
    product_code: str,
    product_name: str,
    reason: str,
    advisor_note: str = "",
) -> dict:
    """Submit a product recommendation to the CRM system.

    **Always requires explicit human approval before execution.**

    Args:
        customer_id: The customer's unique identifier.
        product_code: Product code / SKU (e.g. "UI-GROWTH-2024").
        product_name: Human-readable product name.
        reason: Why this product suits the customer (1–3 sentences).
        advisor_note: Optional note for the human advisor who will follow up.
    """
    import json
    import subprocess

    if not _MOCK_CRM_MODULE.exists():
        return {"success": True, "crm_record_id": f"CRM-{customer_id}-{product_code}"}

    cmd = [sys.executable, str(_MOCK_CRM_MODULE),
           "--customer-id", customer_id, "--product-code", product_code,
           "--product-name", product_name, "--reason", reason]
    if advisor_note:
        cmd += ["--advisor-note", advisor_note]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        err = result.stderr.strip() or f"exit {result.returncode}"
        logger.error("mock_crm failed: %s", err)
        return {"success": False, "error": err}
    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"success": False, "error": f"Unexpected output: {result.stdout.strip()}"}


# ---------------------------------------------------------------------------
# Toolbox auth helper
# ---------------------------------------------------------------------------

class _ToolboxAuth(httpx.Auth):
    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = "Bearer " + self._get_token()
        yield request


# ---------------------------------------------------------------------------
# Factory functions (called once at server startup)
# ---------------------------------------------------------------------------

def make_fabric_tool(credential: DefaultAzureCredential) -> "tuple[dict, FoundryChatClient]":
    """Resolve the Fabric OBO connection and return (fabric_tool_dict, FoundryChatClient).

    ``allow_preview=True`` is required for ``get_fabric_tool()`` to work. The
    returned dict must be passed explicitly to the Agent tools list.
    """
    project_client = AIProjectClient(endpoint=_PROJECT_ENDPOINT, credential=credential)
    try:
        conn = project_client.connections.get(_FABRIC_CONNECTION_ID)
        connection_id = conn.id
        logger.info("Fabric connection '%s' ready (authType: %s).", conn.name, getattr(conn, 'auth_type', 'AAD'))
    except Exception as exc:
        logger.warning(
            "Could not resolve Fabric connection '%s': %s — using name directly.",
            _FABRIC_CONNECTION_ID, exc,
        )
        connection_id = _FABRIC_CONNECTION_ID

    foundry_client = FoundryChatClient(
        project_endpoint=_PROJECT_ENDPOINT,
        model=_MODEL,
        credential=credential,
        allow_preview=True,
    )
    fabric_tool = foundry_client.get_fabric_tool(connection_id=connection_id).as_dict()
    logger.info("Fabric tool configured: connection_id=%s", connection_id)
    return fabric_tool, foundry_client


def make_finance_mcp_tool(credential: DefaultAzureCredential) -> MCPStreamableHTTPTool:
    """Build the Finance MCP tool (direct URL, no auth)."""
    logger.info("Finance MCP: %s", _FINANCE_MCP_URL)
    return MCPStreamableHTTPTool(name="finance", url=_FINANCE_MCP_URL, load_prompts=False)


def make_agent(
    foundry_client: "FoundryChatClient",
    fabric_tool: dict,
    finance_tool: MCPStreamableHTTPTool,
) -> Agent:
    """Assemble and return the recommender agent.

    ``fabric_tool`` must be passed explicitly (from ``make_fabric_tool()``); Foundry
    does not auto-inject unless ``allow_preview=True`` + ``get_fabric_tool()`` is used.
    """
    return Agent(
        client=foundry_client,
        name="WebRecommenderAgent",
        instructions=SYSTEM_PROMPT,
        tools=[fabric_tool, update_overview, finance_tool, submit_product_recommendation],
    )
