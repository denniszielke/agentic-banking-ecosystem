"""Register the **finbot SQL MCP server** as a Foundry toolbox.

Creates (or updates) the Foundry toolbox that agents consume at runtime, backed
by the **remote** ``finbot_sql_mcp_server`` Container App deployed by
``scripts/deploy_finbot_sql_mcp_server.py``. This publishes the finbot banking
SQL tools (list_mandanten, get_kunde, list_konten, get_konto,
list_transaktionen, list_produkte, list_kunde_produkte, get_kunde_produkt,
list_monatsberichte, list_chat_konversationen, run_read_query, update_konto,
insert_chat_konversation, write_kunde_produkt, kuendige_produkt)
so any agent in the project can discover them through the toolbox MCP endpoint
``{project}/toolboxes/{toolbox}/mcp?api-version=v1``.

Run this after the finbot-sql MCP server Container App is deployed.

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT      Foundry project endpoint (required).
  FINBOT_SQL_TOOLBOX_NAME        Toolbox name (default: finbot-sql-tools).
  FINBOT_SQL_MCP_URL             Streamable-HTTP MCP endpoint of the deployed
                                 server. If unset, derived from the
                                 ``finbot-sql-mcp-server`` Container App's
                                 ingress FQDN using AZURE_RESOURCE_GROUP.
  FINBOT_SQL_MCP_APP_NAME        Container App name to resolve the URL from
                                 (default: finbot-sql-mcp-server).
  FINBOT_SQL_MCP_CONNECTION_ID   Foundry connection id used to authenticate
                                 calls to the Entra-protected MCP server (an
                                 AgenticIdentityToken connection with audience
                                 api://<appId>); grant the agent identity
                                 Mcp.Invoke via
                                 scripts.grant_agent_identity_mcp_role.
"""

from __future__ import annotations

import os

from azure.ai.projects.models import MCPToolboxTool

from scripts.agent_deploy_helpers import get_client, get_container_app_fqdn, get_env
from scripts.auth_helpers import entra_auth_enabled

TOOLBOX_NAME = os.getenv("FINBOT_SQL_TOOLBOX_NAME", "finbot-sql-tools")


def _resolve_mcp_url() -> str:
    url = os.getenv("FINBOT_SQL_MCP_URL", "").strip()
    if url:
        return url
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    app_name = os.getenv("FINBOT_SQL_MCP_APP_NAME", "finbot-sql-mcp-server")
    if resource_group:
        fqdn = get_container_app_fqdn(resource_group, app_name)
        if fqdn:
            return f"https://{fqdn}/mcp"
    return ""


def deploy() -> None:
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        print("Skipping toolbox registration: AZURE_AI_PROJECT_ENDPOINT is required.")
        return

    mcp_url = _resolve_mcp_url()
    if not mcp_url:
        print(
            "Skipping toolbox registration: set FINBOT_SQL_MCP_URL, or set "
            "AZURE_RESOURCE_GROUP so the finbot-sql-mcp-server URL can be derived."
        )
        return

    tool_kwargs: dict = {
        "server_label": "finbot-sql",
        "server_url": mcp_url,
        "description": (
            "Finbot banking data in a Fabric SQL database: customers (Kunden), "
            "accounts (Konten), transactions (Transaktionen), products, monthly "
            "reports and chat conversations. Read tools plus human-in-the-loop "
            "write tools: update_konto, insert_chat_konversation, "
            "write_kunde_produkt (order a product) and kuendige_produkt "
            "(cancel a product)."
        ),
        "require_approval": "never",
    }

    if entra_auth_enabled():
        connection_id = os.getenv("FINBOT_SQL_MCP_CONNECTION_ID", "").strip()
        if connection_id:
            tool_kwargs["project_connection_id"] = connection_id
            print(f"  Entra auth on: forwarding calls via connection {connection_id}")
        else:
            print(
                "  WARN: ENTRA_AUTH_ENABLED=true but FINBOT_SQL_MCP_CONNECTION_ID is "
                "unset.\n"
                "  The toolbox cannot forward an authenticated token, so tool "
                "calls will fail with 401 until a Foundry connection for the MCP "
                "audience is created and FINBOT_SQL_MCP_CONNECTION_ID is set."
            )

    tool = MCPToolboxTool(**tool_kwargs)

    client = get_client()
    version = client.toolboxes.create_version(
        name=TOOLBOX_NAME,
        tools=[tool],
        description="Finbot SQL MCP server exposed as a Foundry toolbox.",
        metadata={"source": "finbot-sql-mcp-server"},
    )
    client.toolboxes.update(name=TOOLBOX_NAME, default_version=version.version)

    project_endpoint = get_env("AZURE_AI_PROJECT_ENDPOINT")
    consumer_endpoint = (
        f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"
    )
    print(f"Toolbox '{TOOLBOX_NAME}' version '{version.version}' created.")
    print(f"  Remote MCP server: {mcp_url}")
    print(f"  Consumer endpoint: {consumer_endpoint}")


if __name__ == "__main__":
    deploy()
