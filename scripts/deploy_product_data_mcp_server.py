"""Deploy the **product data MCP server** as an Azure Container App.

This is the financial product catalogue + per-customer holdings surface that the
banking agents reach through a Foundry toolbox. Run it after ``azd up`` has
provisioned the infrastructure.

Usage::

    # build the image in ACR, then deploy
    python -m scripts.deploy_product_data_mcp_server --build

    # deploy only (image already in ACR)
    python -m scripts.deploy_product_data_mcp_server

    # build, deploy, then register the Foundry toolbox in one go
    python -m scripts.deploy_product_data_mcp_server --build --register

Environment variables (populated automatically from ``.env`` after ``azd up``):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_REGISTRY                         ACR login server (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  TAG                                    image tag to deploy (default: latest)
  PRODUCT_MCP_EXTERNAL                   "true" for public ingress so the Foundry
                                         project can reach it (default: true)
  PRODUCT_TOOLBOX_NAME                   Foundry toolbox name registered with
                                         --register (default: product-data-tools)
  ENTRA_AUTH_ENABLED                     "true" to protect the Container App with
                                         Entra ID Easy Auth (default: true)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts.auth_helpers import (
    configure_container_app_easy_auth,
    disable_container_app_easy_auth,
    ensure_mcp_app_registration,
    entra_auth_enabled,
    resolve_tenant_id,
)
from scripts.deploy_helpers import (
    build_image,
    deploy_container_app,
    get_env,
    resolve_registry,
)

APP_NAME = os.getenv("PRODUCT_MCP_APP_NAME", "product-data-mcp-server")
IMAGE_NAME = "product-data-mcp-server"
PORT = int(os.getenv("PRODUCT_MCP_PORT", "8093"))
_DOCKERFILE = "src/product_data_mcp_server/Dockerfile"


def build() -> str:
    """Build the product-data-mcp-server image in ACR (timestamp + :latest)."""
    registry = resolve_registry()
    source_path = Path(__file__).resolve().parents[1]
    dockerfile = str(source_path / _DOCKERFILE)
    return build_image(registry, IMAGE_NAME, source_path, dockerfile=dockerfile)


def deploy(tag: str | None = None) -> None:
    external = os.getenv("PRODUCT_MCP_EXTERNAL", "true").strip().lower() == "true"
    env_vars = {
        "PRODUCT_MCP_HOST": "0.0.0.0",
        "PRODUCT_MCP_PORT": str(PORT),
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

    _apply_entra_auth()

    if fqdn:
        mcp_url = f"https://{fqdn}/mcp"
        print(f"\nProduct data MCP server deployed: {mcp_url}")
    else:
        print(
            "\nProduct data MCP server deployed, but no ingress FQDN was "
            "returned. Set PRODUCT_MCP_EXTERNAL=true or check the ingress."
        )
    return fqdn


def _apply_entra_auth() -> None:
    """Toggle Entra ID Easy Auth on the Container App from ENTRA_AUTH_ENABLED."""
    resource_group = get_env("AZURE_RESOURCE_GROUP")
    if not entra_auth_enabled():
        disable_container_app_easy_auth(resource_group, APP_NAME)
        return
    print("\n==> ENTRA_AUTH_ENABLED=true — protecting the MCP server with Easy Auth")
    app_id, audience = ensure_mcp_app_registration(APP_NAME)
    configure_container_app_easy_auth(
        resource_group=resource_group,
        app_name=APP_NAME,
        client_id=app_id,
        tenant_id=resolve_tenant_id(),
        excluded_paths=["/health"],
    )
    print(
        "  Callers must request a token for audience "
        f"'{audience}/.default'.\n"
        "  Set PRODUCT_MCP_CONNECTION_ID so the Foundry toolbox forwards "
        "authenticated calls."
    )


def register_toolbox(fqdn: str | None) -> None:
    """Register the deployed server as a Foundry toolbox.

    Imported lazily so the plain deploy path never needs ``azure-ai-projects``.
    """
    if fqdn:
        os.environ.setdefault("PRODUCT_MCP_URL", f"https://{fqdn}/mcp")
    from scripts.register_product_data_toolbox import deploy as register

    print("\n==> Registering product data MCP server as a Foundry toolbox")
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
