"""Delete the banking **Container Apps** (customer support agent + MCP servers).

Removes the Container Apps created for the banking demo:
  * ``customer-support-agent`` — the consumer-facing agent + web UI,
  * ``customer-data-mcp-server`` — the customer master-data MCP server,
  * ``product-data-mcp-server`` — the product catalogue MCP server.

Foundry hosted agents (compliance, employee advisory) are removed separately by
``scripts/delete_agents.py``.

Usage::

    python -m scripts.delete_container_apps
    python -m scripts.delete_container_apps --purge-auth   # also delete the
                                                           # <app>-mcp-auth Entra
                                                           # app registrations

Environment variables:
  AZURE_RESOURCE_GROUP        resource group containing the container apps (required)
  CUSTOMER_SUPPORT_APP_NAME   default: customer-support-agent
  CUSTOMER_MCP_APP_NAME       default: customer-data-mcp-server
  PRODUCT_MCP_APP_NAME        default: product-data-mcp-server
"""

from __future__ import annotations

import os
import subprocess
import sys

from scripts._cli import normalize

from dotenv import load_dotenv

load_dotenv(override=True)

RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")

CUSTOMER_SUPPORT_APP = os.getenv("CUSTOMER_SUPPORT_APP_NAME", "customer-support-agent")
CUSTOMER_MCP_APP = os.getenv("CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server")
PRODUCT_MCP_APP = os.getenv("PRODUCT_MCP_APP_NAME", "product-data-mcp-server")

APP_NAMES = [CUSTOMER_SUPPORT_APP, CUSTOMER_MCP_APP, PRODUCT_MCP_APP]
# MCP servers whose Easy Auth app registrations can be purged with --purge-auth.
MCP_APP_NAMES = [CUSTOMER_MCP_APP, PRODUCT_MCP_APP]


def run(cmd: list[str]) -> None:
    normalized = normalize(cmd)
    print(f"$ {' '.join(normalized)}")
    subprocess.run(normalized, check=False)


def delete_all(purge_auth: bool = False) -> None:
    if not RESOURCE_GROUP:
        print("ERROR: AZURE_RESOURCE_GROUP must be set.", file=sys.stderr)
        sys.exit(1)

    for name in APP_NAMES:
        print(f"\n==> Deleting container app '{name}'")
        run([
            "az", "containerapp", "delete",
            "--name", name,
            "--resource-group", RESOURCE_GROUP,
            "--yes",
        ])

    if purge_auth:
        # Lazy import so the plain delete path needs no extra modules.
        from scripts.auth_helpers import delete_mcp_app_registration

        print("\n==> Purging MCP Easy Auth app registrations")
        for name in MCP_APP_NAMES:
            delete_mcp_app_registration(name)

    print("\nAll banking container apps deleted.")


if __name__ == "__main__":
    delete_all(purge_auth="--purge-auth" in sys.argv)
