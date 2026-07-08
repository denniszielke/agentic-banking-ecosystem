"""Deploy the **Recommender OBO Agent** as a Foundry prompt agent.

Creates (or updates) a native Foundry prompt agent that uses:

  * **Fabric DataAgent** — live account and transaction data via the
    ``fabric_dataagent_obo`` connection (AAD / user on-behalf-of auth so the
    DataAgent queries run as the signed-in customer).
  * **Finance MCP toolbox** — compound-interest and DCF calculations via the
    ``finance-tools`` Foundry toolbox.

Unlike the container-based hosted agent (``deploy_recommender_agent.py``),
this agent runs entirely inside the Foundry platform — no ACR build, no
container image. The Foundry model service executes the tool calls directly.

Usage::

    python -m scripts.deploy_recommender_obo_agent

Environment variables (populated from ``.env`` after ``azd up``):
  AZURE_AI_PROJECT_ENDPOINT              Foundry project endpoint (required).
  FABRIC_OBO_CONNECTION_NAME             Fabric OBO connection name
                                         (default: fabric_dataagent_obo).
  FINANCE_MCP_URL                        Direct finance MCP URL
                                         (default: the deployed Container App URL).
  AZURE_AI_RECOMMENDER_OBO_AGENT_NAME    Prompt agent name
                                         (default: recommender-obo-agent).
  AZURE_AI_MODEL_DEPLOYMENT_NAME         Model deployment
                                         (default: gpt-4.1-mini).
"""

from __future__ import annotations

import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    FabricDataAgentToolParameters,
    MCPToolboxTool,
    MicrosoftFabricPreviewTool,
    PromptAgentDefinition,
    ToolProjectConnection,
)
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_AGENT_NAME = os.getenv("AZURE_AI_RECOMMENDER_OBO_AGENT_NAME", "recommender-obo-agent")
_MODEL = os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini")
_FABRIC_CONNECTION_NAME = os.getenv("FABRIC_OBO_CONNECTION_NAME", "fabric_dataagent_obo")
_FINANCE_MCP_URL = os.getenv(
    "FINANCE_MCP_URL",
    "https://finance-mcp-server.whitemoss-40897c95.swedencentral.azurecontainerapps.io/mcp",
)

_INSTRUCTIONS = """\
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

## Stil
- Antworte auf Deutsch, freundlich, knapp und präzise.
- Stelle Salden und Übersichten gut lesbar dar (z. B. als kurze Liste oder Tabelle).
- Erkläre Finanzbegriffe nur auf Nachfrage oder wenn es zum Verständnis nötig ist.
"""


def deploy() -> None:
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        print("Skipping: AZURE_AI_PROJECT_ENDPOINT is required.")
        return

    credential = DefaultAzureCredential()
    project = AIProjectClient(endpoint=_PROJECT_ENDPOINT, credential=credential)

    # Resolve Fabric connection id from name.
    print(f"==> Resolving Fabric connection '{_FABRIC_CONNECTION_NAME}'")
    fabric_conn = project.connections.get(_FABRIC_CONNECTION_NAME)
    print(f"    id: {fabric_conn.id}")
    print(f"    authType: {getattr(fabric_conn, 'auth_type', 'AAD')}")

    # Finance MCP server — direct URL, no auth required.
    finance_mcp_url = _FINANCE_MCP_URL

    # Build the tool list.
    tools = [
        MicrosoftFabricPreviewTool(
            fabric_dataagent_preview=FabricDataAgentToolParameters(
                project_connections=[
                    ToolProjectConnection(project_connection_id=fabric_conn.id)
                ]
            )
        ),
        MCPToolboxTool(
            server_label="finance",
            server_url=finance_mcp_url,
            require_approval="always",
        ),
    ]

    print(f"\n==> Creating/updating prompt agent '{_AGENT_NAME}' (model: {_MODEL})")
    agent = project.agents.create_version(
        agent_name=_AGENT_NAME,
        definition=PromptAgentDefinition(
            model=_MODEL,
            instructions=_INSTRUCTIONS,
            tools=tools,
        ),
    )

    print(f"\nPrompt agent deployed successfully.")
    print(f"  Name    : {agent.name}")
    print(f"  Version : {agent.version}")
    print(f"  Tools   : Fabric DataAgent (OBO AAD) + Finance MCP (direct, no auth)")
    print(f"  Finance MCP: {finance_mcp_url}")


if __name__ == "__main__":
    deploy()
