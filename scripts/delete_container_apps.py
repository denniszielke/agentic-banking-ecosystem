"""Delete the banking **Container Apps** (customer support agent + MCP servers).

Removes the Container Apps created for the banking demo:
  * ``customer-support-agent`` — the consumer-facing agent + web UI,
  * ``customer-data-mcp-server`` — the customer master-data MCP server,
  * ``product-data-mcp-server`` — the product catalogue MCP server.

Foundry hosted agents (compliance, employee advisory) are removed separately by
``scripts/delete_agents.py``.

Usage::

    python -m scripts.delete_container_apps

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

from dotenv import load_dotenv

load_dotenv(override=True)

RESOURCE_GROUP = os.getenv("AZURE_RESOURCE_GROUP")

APP_NAMES = [
    os.getenv("CUSTOMER_SUPPORT_APP_NAME", "customer-support-agent"),
    os.getenv("CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server"),
    os.getenv("PRODUCT_MCP_APP_NAME", "product-data-mcp-server"),
]


def run(cmd: list[str]) -> None:
    print(f"$ {' '.join(cmd)}")
    subprocess.run(cmd, check=False)


def delete_all() -> None:
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

    print("\nAll banking container apps deleted.")


if __name__ == "__main__":
    delete_all()
