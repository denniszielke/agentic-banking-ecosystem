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
    ensure_mcp_app_registration,
    entra_auth_enabled,
    resolve_tenant_id,
)
from scripts.deploy_helpers import (
    build_image,
    deploy_container_app,
    get_containerapp_env_default_domain,
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

    env_vars.update(_auth_env_vars())

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
        print(f"\nProduct data MCP server deployed: {mcp_url}")
    else:
        print(
            "\nProduct data MCP server deployed, but no ingress FQDN was "
            "returned. Set PRODUCT_MCP_EXTERNAL=true or check the ingress."
        )
    return fqdn


def _auth_env_vars() -> dict[str, str]:
    """Build the FastMCP Entra JWT auth env vars for the container.

    When ``ENTRA_AUTH_ENABLED`` is off the server runs anonymously. When on, the
    server validates incoming Entra access tokens itself (FastMCP's Azure JWT
    verifier) using the MCP app registration as the token audience — no Container
    Apps Easy Auth. The audience client id, tenant and the server's own public
    base URL are injected as env vars the FastMCP ``AzureJWTVerifier`` reads at
    startup.
    """
    if not entra_auth_enabled():
        print("\n==> ENTRA_AUTH_ENABLED=false — MCP server runs without authentication")
        return {"ENTRA_AUTH_ENABLED": "false"}

    print("\n==> ENTRA_AUTH_ENABLED=true — protecting the MCP server with FastMCP Entra JWT auth")
    app_id, audience = ensure_mcp_app_registration(APP_NAME)
    tenant_id = resolve_tenant_id()
    resource_group = get_env("AZURE_RESOURCE_GROUP")
    environment_name = get_env("AZURE_CONTAINER_APPS_ENVIRONMENT_NAME")
    default_domain = get_containerapp_env_default_domain(resource_group, environment_name)
    base_url = f"https://{APP_NAME}.{default_domain}" if default_domain else ""
    print(f"  Callers must request a token for audience '{audience}/.default'.")
    return {
        "ENTRA_AUTH_ENABLED": "true",
        "MCP_AUTH_CLIENT_ID": app_id,
        "AZURE_TENANT_ID": tenant_id,
        "MCP_PUBLIC_BASE_URL": base_url,
    }


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
