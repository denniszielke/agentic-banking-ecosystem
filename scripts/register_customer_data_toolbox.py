"""Register the **customer data MCP server** as a Foundry toolbox.

Creates (or updates) the Foundry toolbox that the banking agents consume at
runtime, backed by the **remote** ``customer_data_mcp_server`` Container App
deployed by ``scripts/deploy_customer_data_mcp_server.py``. This publishes the
customer master-data tools (list_customers, get_customer, list_accounts,
get_account, list_transactions, get_balance, update_customer) so any agent in
the project can discover them through the toolbox MCP endpoint
``{project}/toolboxes/{toolbox}/mcp?api-version=v1``.

Run this after the customer-data MCP server Container App is deployed.

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT     Foundry project endpoint (required).
  CUSTOMER_TOOLBOX_NAME         Toolbox name (default: customer-data-tools).
  CUSTOMER_MCP_URL              Streamable-HTTP MCP endpoint of the deployed
                                server. If unset, it is derived from the
                                ``customer-data-mcp-server`` Container App's
                                ingress FQDN using AZURE_RESOURCE_GROUP.
  CUSTOMER_MCP_APP_NAME         Container App name to resolve the URL from
                                (default: customer-data-mcp-server).
  CUSTOMER_MCP_CONNECTION_ID    Optional Foundry connection id to authorise calls
                                to a network-restricted MCP server.
"""

from __future__ import annotations

import os

from azure.ai.projects.models import MCPToolboxTool

from scripts.agent_deploy_helpers import get_client, get_container_app_fqdn, get_env
from scripts.auth_helpers import entra_auth_enabled

TOOLBOX_NAME = os.getenv("CUSTOMER_TOOLBOX_NAME", "customer-data-tools")


def _resolve_mcp_url() -> str:
    url = os.getenv("CUSTOMER_MCP_URL", "").strip()
    if url:
        return url
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    app_name = os.getenv("CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server")
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
            "Skipping toolbox registration: set CUSTOMER_MCP_URL, or set "
            "AZURE_RESOURCE_GROUP so the customer-data-mcp-server URL can be derived."
        )
        return

    tool_kwargs: dict = {
        "server_label": "customer-data",
        "server_url": mcp_url,
        "description": (
            "Bank customer master data: customers, accounts and credit cards, "
            "balances and transactions. Read tools plus a human-in-the-loop "
            "update_customer write tool."
        ),
        "require_approval": "never",
    }

    if entra_auth_enabled():
        connection_id = os.getenv("CUSTOMER_MCP_CONNECTION_ID", "").strip()
        if connection_id:
            tool_kwargs["project_connection_id"] = connection_id
            print(f"  Entra auth on: forwarding calls via connection {connection_id}")
        else:
            print(
                "  WARN: ENTRA_AUTH_ENABLED=true but CUSTOMER_MCP_CONNECTION_ID is "
                "unset.\n"
                "  The toolbox cannot forward an authenticated token, so tool "
                "calls will fail with 401 until a Foundry connection for the MCP "
                "audience is created and CUSTOMER_MCP_CONNECTION_ID is set."
            )

    tool = MCPToolboxTool(**tool_kwargs)

    client = get_client()
    version = client.toolboxes.create_version(
        name=TOOLBOX_NAME,
        tools=[tool],
        description="Customer data MCP server exposed as a Foundry toolbox.",
        metadata={"source": "customer-data-mcp-server"},
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
