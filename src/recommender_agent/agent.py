"""Recommender Agent — Foundry hosted agent (Volksbank personal banking assistant).

A personal banking assistant for Volksbank customers. It answers everyday questions
about the customer's accounts and finances, explains products, runs financial
calculations and proactively recommends suitable products from the Volksbank /
genossenschaftliche FinanzGruppe portfolio (Union Investment, R+V Versicherung,
Bausparkasse Schwäbisch Hall, easyCredit/TeamBank).

It draws on two tool surfaces:

  1. **Fabric data agent** — live account and transaction data via a Microsoft
     Fabric data agent reached through a Foundry project connection
     (``FoundryChatClient.get_fabric_tool()``).

  2. **Finance MCP server** — compound-interest and discounted-cash-flow
     calculations, consumed through a Foundry toolbox (or a direct MCP URL
     for local development).

Write operations (order product, cancel product, update contact details) are
strictly human-in-the-loop: the agent previews, asks for confirmation, then
commits only after an explicit "yes".

Business flows are loaded from the ``skills/`` folder so the domain process
ships inside the container image.

Model calls are routed through Azure AI Foundry using Entra ID (no API keys).

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT               — Foundry project endpoint (required)
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME       — chat model deployment
  AZURE_AI_MODEL_DEPLOYMENT_NAME          — fallback model deployment
  FABRIC_CONNECTION_ID                    — Foundry project connection ID (required)
  FINANCE_TOOLBOX_NAME                    — finance MCP toolbox (default: finance-tools)
  FINANCE_MCP_URL                         — direct MCP URL for local dev (optional)
  PORT                                    — host port (default: 8091)

Run the hosted agent server locally from the project root:

    python -m src.recommender_agent.agent
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx
from agent_framework import MCPStreamableHTTPTool
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

_FABRIC_CONNECTION_ID = os.environ["FABRIC_CONNECTION_ID"]

# Finance MCP server consumed through a Foundry toolbox by default; the direct
# URL override bypasses the toolbox for local development.
_FINANCE_TOOLBOX_NAME = os.getenv("FINANCE_TOOLBOX_NAME", "finance-tools")
_FINANCE_TOOLBOX_ENDPOINT = os.getenv("FINANCE_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_FINANCE_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_FINANCE_MCP_URL = os.getenv("FINANCE_MCP_URL", "").strip()

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


RECOMMENDER_AGENT_SYSTEM_PROMPT = BASE_INSTRUCTIONS + _load_skills()


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


# ---------------------------------------------------------------------------
# MCP toolbox tools (Foundry toolbox, or direct URL for local dev)
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
# Fabric data agent tool (Foundry project connection)
# ---------------------------------------------------------------------------

def _make_fabric_tool() -> object:
    """Build the Fabric data agent tool for live account/transaction data."""
    chat_client = FoundryChatClient(
        project_endpoint=_PROJECT_ENDPOINT,
        model=_MODEL_DEPLOYMENT,
        credential=_credential,
        allow_preview=True,
    )
    # Serialise to a plain wire dict so it can be passed alongside regular tools
    # without hitting JSON-serialisation issues in the framework's OTel path.
    return chat_client.get_fabric_tool(connection_id=_FABRIC_CONNECTION_ID).as_dict()


# ---------------------------------------------------------------------------
# Agent assembly
# ---------------------------------------------------------------------------

_tools: list = [
    _make_fabric_tool(),
    _build_mcp_tool("finance", _FINANCE_TOOLBOX_ENDPOINT, _DIRECT_FINANCE_MCP_URL),
]

_chat_client = FoundryChatClient(
    project_endpoint=_PROJECT_ENDPOINT,
    model=_MODEL_DEPLOYMENT,
    credential=_credential,
    allow_preview=True,
)

agent = _chat_client.as_agent(
    name="recommender-agent",
    instructions=RECOMMENDER_AGENT_SYSTEM_PROMPT,
    tools=_tools,
)


if __name__ == "__main__":
    ResponsesHostServer(agent).run()
