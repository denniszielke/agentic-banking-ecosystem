"""Deploy the **customer data MCP server** as an Azure Container App.

This is the customer master-data surface (customers, accounts, credit cards,
balances and transactions) that the banking agents reach through a Foundry
toolbox. Run it after ``azd up`` has provisioned the infrastructure.

Usage::

    # build the image in ACR, then deploy
    python -m scripts.deploy_customer_data_mcp_server --build

    # deploy only (image already in ACR)
    python -m scripts.deploy_customer_data_mcp_server

    # build, deploy, then register the Foundry toolbox in one go
    python -m scripts.deploy_customer_data_mcp_server --build --register

Environment variables (populated automatically from ``.env`` after ``azd up``):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_REGISTRY                         ACR login server (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  TAG                                    image tag to deploy (default: latest)
  CUSTOMER_MCP_EXTERNAL                  "true" for public ingress so the Foundry
                                         project can reach it (default: true)
  CUSTOMER_TOOLBOX_NAME                  Foundry toolbox name registered with
                                         --register (default: customer-data-tools)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts.deploy_helpers import build_image, deploy_container_app, resolve_registry

APP_NAME = os.getenv("CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server")
IMAGE_NAME = "customer-data-mcp-server"
PORT = int(os.getenv("CUSTOMER_MCP_PORT", "8092"))
_DOCKERFILE = "src/customer_data_mcp_server/Dockerfile"


def build() -> str:
    """Build the customer-data-mcp-server image in ACR (timestamp + :latest)."""
    registry = resolve_registry()
    source_path = Path(__file__).resolve().parents[1]
    dockerfile = str(source_path / _DOCKERFILE)
    return build_image(registry, IMAGE_NAME, source_path, dockerfile=dockerfile)


def deploy(tag: str | None = None) -> None:
    external = os.getenv("CUSTOMER_MCP_EXTERNAL", "true").strip().lower() == "true"
    env_vars = {
        "CUSTOMER_MCP_HOST": "0.0.0.0",
        "CUSTOMER_MCP_PORT": str(PORT),
        "BANK_DATA_DIR": "/app/data",
        "APPLICATIONINSIGHTS_CONNECTION_STRING": os.getenv(
            "APPLICATIONINSIGHTS_CONNECTION_STRING", ""
        ),
    }

    fqdn = deploy_container_app(
        app_name=APP_NAME,
        image_name=IMAGE_NAME,
        port=PORT,
        external=external,
        env_vars=env_vars,
        tag=tag,
        readiness_probe_path="/health",
    )

    if fqdn:
        mcp_url = f"https://{fqdn}/mcp"
        print(f"\nCustomer data MCP server deployed: {mcp_url}")
    else:
        print(
            "\nCustomer data MCP server deployed, but no ingress FQDN was "
            "returned. Set CUSTOMER_MCP_EXTERNAL=true or check the ingress."
        )
    return fqdn


def register_toolbox(fqdn: str | None) -> None:
    """Register the deployed server as a Foundry toolbox.

    Imported lazily so the plain deploy path never needs ``azure-ai-projects``.
    """
    if fqdn:
        os.environ.setdefault("CUSTOMER_MCP_URL", f"https://{fqdn}/mcp")
    from scripts.register_customer_data_toolbox import deploy as register

    print("\n==> Registering customer data MCP server as a Foundry toolbox")
    register()


if __name__ == "__main__":
    do_build = "--build" in sys.argv
    do_register = "--register" in sys.argv
    built_tag: str | None = None
    if do_build:
        built_tag = build()
    fqdn = deploy(tag=built_tag)
    if do_register:
        register_toolbox(fqdn)
