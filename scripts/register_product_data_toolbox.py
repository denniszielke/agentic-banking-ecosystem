"""Register the **product data MCP server** as a Foundry toolbox.

Creates (or updates) the Foundry toolbox that the banking agents consume at
runtime, backed by the **remote** ``product_data_mcp_server`` Container App
deployed by ``scripts/deploy_product_data_mcp_server.py``. This publishes the
product catalogue + holdings tools (list_products, get_product, list_holdings,
order_product, update_holding) so any agent in the project can discover them
through the toolbox MCP endpoint ``{project}/toolboxes/{toolbox}/mcp?api-version=v1``.

Run this after the product-data MCP server Container App is deployed.

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT    Foundry project endpoint (required).
  PRODUCT_TOOLBOX_NAME         Toolbox name (default: product-data-tools).
  PRODUCT_MCP_URL              Streamable-HTTP MCP endpoint of the deployed
                               server. If unset, it is derived from the
                               ``product-data-mcp-server`` Container App's
                               ingress FQDN using AZURE_RESOURCE_GROUP.
  PRODUCT_MCP_APP_NAME         Container App name to resolve the URL from
                               (default: product-data-mcp-server).
  PRODUCT_MCP_CONNECTION_ID    Optional Foundry connection id to authorise calls
                               to a network-restricted MCP server.
"""

from __future__ import annotations

import os

from azure.ai.projects.models import MCPToolboxTool

from scripts.agent_deploy_helpers import get_client, get_container_app_fqdn, get_env

TOOLBOX_NAME = os.getenv("PRODUCT_TOOLBOX_NAME", "product-data-tools")


def _resolve_mcp_url() -> str:
    url = os.getenv("PRODUCT_MCP_URL", "").strip()
    if url:
        return url
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    app_name = os.getenv("PRODUCT_MCP_APP_NAME", "product-data-mcp-server")
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
            "Skipping toolbox registration: set PRODUCT_MCP_URL, or set "
            "AZURE_RESOURCE_GROUP so the product-data-mcp-server URL can be derived."
        )
        return

    tool = MCPToolboxTool(
        server_label="product-data",
        server_url=mcp_url,
        description=(
            "Financial product catalogue and per-customer product holdings. "
            "Read tools plus human-in-the-loop order_product and update_holding "
            "write tools."
        ),
        require_approval="never",
    )

    client = get_client()
    version = client.toolboxes.create_version(
        name=TOOLBOX_NAME,
        tools=[tool],
        description="Product data MCP server exposed as a Foundry toolbox.",
        metadata={"source": "product-data-mcp-server"},
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
