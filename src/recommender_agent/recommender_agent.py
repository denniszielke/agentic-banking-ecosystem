"""Recommender Agent — Foundry hosted agent (Volksbank personal banking assistant).

A personal banking assistant for Volksbank customers, hosted as an Azure AI
Foundry hosted agent (RESPONSES protocol). It answers everyday questions about
the customer's accounts and finances, explains products, and proactively
recommends suitable Volksbank / genossenschaftliche FinanzGruppe products
(Union Investment, R+V Versicherung, Bausparkasse Schwäbisch Hall,
easyCredit/TeamBank).

It is grounded on two tool surfaces:

  1. **Fabric data agent** — live account and transaction data via a Microsoft
     Fabric data agent reached through a Foundry project connection.

  2. **Finance MCP server** — compound-interest and discounted-cash-flow
     calculations, consumed through the ``finance-tools`` Foundry toolbox.

Business flows are loaded from the ``skills/`` folder so the domain process
ships inside the container image.

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT               Foundry project endpoint (required).
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME       model deployment name.
  AZURE_AI_MODEL_DEPLOYMENT_NAME          fallback model name.
  FABRIC_CONNECTION_ID                    Foundry project connection name (required).
  FINANCE_TOOLBOX_NAME                    finance MCP toolbox (default: finance-tools).
  FINANCE_MCP_URL                         direct MCP URL for local dev (optional).

Run locally from the project root:

    python -m src.recommender_agent.recommender_agent
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import httpx
from agent_framework import MCPStreamableHTTPTool, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.ai.projects import AIProjectClient
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
_MODEL = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)

_FABRIC_CONNECTION_ID = os.environ["FABRIC_CONNECTION_ID"]  # connection name

# Finance MCP server — compound interest / DCF calculations.
_FINANCE_TOOLBOX_NAME = os.getenv("FINANCE_TOOLBOX_NAME", "finance-tools")
_FINANCE_TOOLBOX_ENDPOINT = os.getenv("FINANCE_TOOLBOX_MCP_ENDPOINT") or (
    f"{_PROJECT_ENDPOINT.rstrip('/')}/toolboxes/{_FINANCE_TOOLBOX_NAME}/mcp?api-version=v1"
)
_DIRECT_FINANCE_MCP_URL = os.getenv("FINANCE_MCP_URL", "").strip()

_SKILLS_DIR = Path(__file__).parent / "skills"


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
  Wenn dir konkrete Konditionen fehlen, verweise auf die persönliche Beratung in der
  Volksbank.
- Wenn der Kunde Interesse an einem Produkt signalisiert, biete ihm an, eine Empfehlung
  im CRM zu hinterlegen, damit ein menschlicher Berater sich meldet. Nutze dazu das
  Tool `submit_product_recommendation`. Dieses Tool erfordert immer eine explizite
  Bestätigung durch den Nutzer, bevor es ausgeführt wird.

## Stil
- Antworte auf Deutsch, freundlich, knapp und präzise.
- Stelle Salden und Übersichten gut lesbar dar (z. B. als kurze Liste oder Tabelle).
- Erkläre Finanzbegriffe nur auf Nachfrage oder wenn es zum Verständnis nötig ist.
"""


# ---------------------------------------------------------------------------
# CRM submission tool (human-in-the-loop, always requires approval)
# ---------------------------------------------------------------------------

_MOCK_CRM_MODULE = Path(__file__).parent / "mock_crm.py"


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

    Records a personalised product recommendation for the customer in the CRM
    so that a human advisor can follow up. Use this after you have explained a
    product to the customer and they have expressed interest.

    Args:
        customer_id: The customer's unique identifier (e.g. from the Fabric data
            agent response).
        product_code: The product code / SKU (e.g. "UI-GROWTH-2024").
        product_name: Human-readable product name (e.g. "Union Investment
            Wachstumsfonds").
        reason: A short explanation of why this product suits the customer
            (1–3 sentences). This is stored on the CRM record.
        advisor_note: Optional free-text note for the human advisor who will
            follow up (default: empty).

    Returns:
        A dict with ``success`` (bool) and ``crm_record_id`` (str) on success,
        or ``error`` (str) on failure.
    """
    import json
    import subprocess

    cmd = [
        sys.executable,
        str(_MOCK_CRM_MODULE),
        "--customer-id", customer_id,
        "--product-code", product_code,
        "--product-name", product_name,
        "--reason", reason,
    ]
    if advisor_note:
        cmd += ["--advisor-note", advisor_note]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        error_msg = result.stderr.strip() or f"CRM script exited with code {result.returncode}"
        logger.error("mock_crm failed: %s", error_msg)
        return {"success": False, "error": error_msg}

    try:
        return json.loads(result.stdout.strip())
    except json.JSONDecodeError:
        return {"success": False, "error": f"Unexpected CRM output: {result.stdout.strip()}"}


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
# Identity / credential + toolbox auth
# ---------------------------------------------------------------------------

_credential = DefaultAzureCredential()
_toolbox_token_provider = get_bearer_token_provider(_credential, "https://ai.azure.com/.default")


class _ToolboxAuth(httpx.Auth):
    """Inject a fresh Entra token on every Foundry toolbox MCP request."""

    def __init__(self, token_provider):
        self._get_token = token_provider

    def auth_flow(self, request):
        request.headers["Authorization"] = "Bearer " + self._get_token()
        yield request


def _toolbox_http_client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        auth=_ToolboxAuth(_toolbox_token_provider),
        headers={"Foundry-Features": "Toolboxes=V1Preview"},
        timeout=120.0,
    )


# ---------------------------------------------------------------------------
# Foundry client + tools
# ---------------------------------------------------------------------------

_project_client = AIProjectClient(endpoint=_PROJECT_ENDPOINT, credential=_credential)
try:
    _fabric_connection_id = _project_client.connections.get(_FABRIC_CONNECTION_ID).id
    logger.info("Fabric connection resolved: %s → %s", _FABRIC_CONNECTION_ID, _fabric_connection_id)
except Exception as _exc:
    logger.warning(
        "Could not resolve Fabric connection '%s' via API (%s); using name directly.",
        _FABRIC_CONNECTION_ID,
        _exc,
    )
    _fabric_connection_id = _FABRIC_CONNECTION_ID

_foundry_client = FoundryChatClient(
    project_endpoint=_PROJECT_ENDPOINT,
    model=_MODEL,
    credential=_credential,
    allow_preview=True,
)

# Fabric data agent tool — live account and transaction data.
_fabric_tool = _foundry_client.get_fabric_tool(connection_id=_fabric_connection_id).as_dict()

# Finance MCP tool — compound interest / DCF calculations.
if _DIRECT_FINANCE_MCP_URL:
    logger.info("Finance MCP: using direct URL %s", _DIRECT_FINANCE_MCP_URL)
    _finance_tool: MCPStreamableHTTPTool = MCPStreamableHTTPTool(
        name="finance", url=_DIRECT_FINANCE_MCP_URL, load_prompts=False
    )
else:
    logger.info("Finance MCP: using Foundry toolbox %s", _FINANCE_TOOLBOX_ENDPOINT)
    _finance_tool = MCPStreamableHTTPTool(
        name="finance",
        url=_FINANCE_TOOLBOX_ENDPOINT,
        http_client=_toolbox_http_client(),
        load_prompts=False,
    )


# ---------------------------------------------------------------------------
# Agent assembly
# ---------------------------------------------------------------------------

agent = _foundry_client.as_agent(
    name="recommender-agent",
    instructions=SYSTEM_PROMPT,
    tools=[_fabric_tool, _finance_tool, submit_product_recommendation],
)


if __name__ == "__main__":
    ResponsesHostServer(agent).run()
