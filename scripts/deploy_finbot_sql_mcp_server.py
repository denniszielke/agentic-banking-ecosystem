"""Deploy the **finbot SQL MCP server** as an Azure Container App.

This MCP server exposes the finbot banking data held in the Fabric SQL database
``finbot-data-2`` (customers, accounts, transactions, products, monthly reports,
chat conversations). Unlike the customer/product MCP servers it bundles **no
data** — it queries the Fabric SQL database **live** via the Container App's
user-assigned managed identity (``id-banking``), which must already hold
``db_datareader``/``db_datawriter`` on that database.

Usage::

    # build the image in ACR, then deploy
    python -m scripts.deploy_finbot_sql_mcp_server --build

    # build, deploy, then register the Foundry toolbox in one go
    python -m scripts.deploy_finbot_sql_mcp_server --build --register

Environment variables (defaults target the finbot-data-2 database):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_REGISTRY                         ACR login server (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  FINBOT_SQL_SERVER                      Fabric SQL server FQDN,<port>
  FINBOT_SQL_DATABASE                    Fabric SQL database name
  FINBOT_SQL_MI_CLIENT_ID                client id of the managed identity used
                                         to authenticate to SQL (auto-resolved
                                         from AZURE_IDENTITY_NAME if unset)
  TAG                                    image tag to deploy (default: latest)
  FINBOT_SQL_MCP_EXTERNAL                "true" for public ingress (default: true)
  FINBOT_SQL_TOOLBOX_NAME                Foundry toolbox name (default:
                                         finbot-sql-tools)
  ENTRA_AUTH_ENABLED                     "true" to protect the server with
                                         FastMCP Entra JWT auth (default: true)
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from scripts._cli import normalize
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

APP_NAME = os.getenv("FINBOT_SQL_MCP_APP_NAME", "finbot-sql-mcp-server")
IMAGE_NAME = "finbot-sql-mcp-server"
PORT = int(os.getenv("FINBOT_SQL_MCP_PORT", "8094"))
_DOCKERFILE = "src/finbot_sql_mcp_server/Dockerfile"

# Sensible defaults for the finbot-data-2 Fabric SQL database (not secrets).
_DEFAULT_SERVER = (
    "43xf537b6wfubo4zhzviwijsti-isdex3whxdqexopfz43uvpd3qm."
    "database.fabric.microsoft.com,1433"
)
_DEFAULT_DATABASE = "finbot-data-2-7b43a5c9-6e55-4600-af64-1c576ec66c2d"


def build() -> str:
    """Build the finbot-sql-mcp-server image in ACR (timestamp + :latest)."""
    registry = resolve_registry()
    source_path = Path(__file__).resolve().parents[1]
    dockerfile = str(source_path / _DOCKERFILE)
    return build_image(registry, IMAGE_NAME, source_path, dockerfile=dockerfile)


def _resolve_mi_client_id() -> str:
    """Resolve the client id of the SQL managed identity.

    Precedence: ``FINBOT_SQL_MI_CLIENT_ID`` > client id of ``AZURE_IDENTITY_NAME``
    resolved via ``az identity show``.
    """
    explicit = os.getenv("FINBOT_SQL_MI_CLIENT_ID", "").strip()
    if explicit:
        return explicit
    resource_group = get_env("AZURE_RESOURCE_GROUP")
    identity_name = get_env("AZURE_IDENTITY_NAME")
    result = subprocess.run(
        normalize([
            "az", "identity", "show",
            "-g", resource_group, "-n", identity_name,
            "--query", "clientId", "-o", "tsv",
        ]),
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def deploy(tag: str | None = None) -> str | None:
    external = os.getenv("FINBOT_SQL_MCP_EXTERNAL", "true").strip().lower() == "true"
    mi_client_id = _resolve_mi_client_id()
    env_vars = {
        "FINBOT_SQL_MCP_HOST": "0.0.0.0",
        "FINBOT_SQL_MCP_PORT": str(PORT),
        "FINBOT_SQL_SERVER": os.getenv("FINBOT_SQL_SERVER", _DEFAULT_SERVER),
        "FINBOT_SQL_DATABASE": os.getenv("FINBOT_SQL_DATABASE", _DEFAULT_DATABASE),
        "FINBOT_SQL_MI_CLIENT_ID": mi_client_id,
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
        print(f"\nFinbot SQL MCP server deployed: https://{fqdn}/mcp")
    else:
        print(
            "\nFinbot SQL MCP server deployed, but no ingress FQDN was returned. "
            "Set FINBOT_SQL_MCP_EXTERNAL=true or check the ingress."
        )
    return fqdn


def _auth_env_vars() -> dict[str, str]:
    """Build the FastMCP Entra JWT auth env vars for the container."""
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
    """Register the deployed server as a Foundry toolbox (lazy import)."""
    if fqdn:
        os.environ.setdefault("FINBOT_SQL_MCP_URL", f"https://{fqdn}/mcp")
    from scripts.register_finbot_sql_toolbox import deploy as register

    print("\n==> Registering finbot SQL MCP server as a Foundry toolbox")
    register()


if __name__ == "__main__":
    do_build = "--build" in sys.argv
    do_register = "--register" in sys.argv
    built_tag: str | None = None
    if do_build:
        built_tag = build()
    deployed_fqdn = deploy(tag=built_tag)
    if do_register:
        register_toolbox(deployed_fqdn)
