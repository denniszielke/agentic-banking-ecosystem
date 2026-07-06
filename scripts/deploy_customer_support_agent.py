"""Deploy the **Customer Support Agent** as an Azure Container App.

The consumer-facing agent + web UI (AG-UI) behind Bank South's customer app.
Unlike the compliance and employee agents (Foundry hosted agents), this one runs
as a public Container App serving the chat UI on port 8090. It reaches the
customer/product MCP servers directly (their Container App URLs are resolved and
passed in) and grounds on the Financial products + Compliance search indexes.

Run it after ``azd up``, after the customer/product MCP servers are deployed, and
after the search indexes are created + ingested.

Usage::

    python -m scripts.deploy_customer_support_agent --build   # build in ACR, then deploy
    python -m scripts.deploy_customer_support_agent           # deploy existing image

Environment variables (populated from ``.env`` by ``azd up``):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  AZURE_AI_PROJECT_ENDPOINT              Foundry project endpoint (required)
  AZURE_SEARCH_ENDPOINT                  search endpoint (required)
  APPLICATIONINSIGHTS_CONNECTION_STRING  telemetry sink (optional)
  CUSTOMER_SUPPORT_APP_NAME              Container App name (default: customer-support-agent)
  CUSTOMER_SUPPORT_PORT                  container port (default: 8090)
  CUSTOMER_SUPPORT_EXTERNAL              "true" for public ingress (default: true)
  CUSTOMER_MCP_URL / PRODUCT_MCP_URL     direct MCP URLs (auto-resolved if unset)
  ENTRA_AUTH_ENABLED                     "true" to send Entra tokens to the Easy
                                         Auth-protected MCP servers (default: true)
  TAG                                    image tag to deploy (default: latest)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts.auth_helpers import (
    entra_auth_enabled,
    grant_mcp_role_to_principal,
    resolve_mcp_audience,
)
from scripts.deploy_helpers import (
    build_image,
    deploy_container_app,
    get_container_app_fqdn,
    get_env,
    resolve_registry,
)

APP_NAME = os.getenv("CUSTOMER_SUPPORT_APP_NAME", "customer-support-agent")
IMAGE_NAME = "customer-support-agent"
PORT = int(os.getenv("CUSTOMER_SUPPORT_PORT", "8090"))
_DOCKERFILE = "src/customer_support_agent/Dockerfile"

# Built-in role definition IDs.
_COGNITIVE_SERVICES_USER = "a97b65f3-24c7-4388-baec-2e87135dc908"
_SEARCH_INDEX_DATA_READER = "1407120a-92aa-4202-b7e9-c0e197c71c8f"
_MONITORING_METRICS_PUBLISHER = "3913510d-42f4-4e42-8a64-420c390055eb"


def build() -> str:
    registry = resolve_registry()
    source_path = Path(__file__).resolve().parents[1]
    dockerfile = str(source_path / _DOCKERFILE)
    return build_image(registry, IMAGE_NAME, source_path, dockerfile=dockerfile)


def _identity_principal_and_client() -> tuple[str, str]:
    rg = get_env("AZURE_RESOURCE_GROUP")
    name = get_env("AZURE_IDENTITY_NAME")
    out = subprocess.run(
        ["az", "identity", "show", "-g", rg, "-n", name,
         "--query", "[principalId, clientId]", "-o", "tsv"],
        check=True, capture_output=True, text=True,
    ).stdout.split()
    return out[0], out[1]


def _grant_role(principal_id: str, role_id: str, scope: str) -> None:
    try:
        subprocess.run(
            ["az", "role", "assignment", "create",
             "--assignee-object-id", principal_id,
             "--assignee-principal-type", "ServicePrincipal",
             "--role", role_id, "--scope", scope],
            check=True, capture_output=True, text=True,
        )
        print(f"  granted {role_id} on {scope}")
    except subprocess.CalledProcessError as exc:
        if "RoleAssignmentExists" in (exc.stderr or ""):
            print(f"  role {role_id} already assigned on {scope}")
        else:
            print(f"  WARN: could not grant {role_id}: {(exc.stderr or '').strip()}")


def assign_identity_roles(principal_id: str) -> None:
    rg = get_env("AZURE_RESOURCE_GROUP")
    rg_scope = subprocess.run(
        ["az", "group", "show", "-n", rg, "--query", "id", "-o", "tsv"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    print("==> Assigning managed identity roles")
    _grant_role(principal_id, _COGNITIVE_SERVICES_USER, rg_scope)        # consume Foundry models
    _grant_role(principal_id, _SEARCH_INDEX_DATA_READER, rg_scope)       # read search indexes
    _grant_role(principal_id, _MONITORING_METRICS_PUBLISHER, rg_scope)   # publish telemetry


def _resolve_mcp_url(env_var: str, app_env: str, default_app: str) -> str:
    """Resolve an MCP server URL from an env override or its Container App FQDN."""
    url = os.getenv(env_var, "").strip()
    if url:
        return url
    rg = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    app_name = os.getenv(app_env, default_app)
    if rg:
        fqdn = get_container_app_fqdn(rg, app_name)
        if fqdn:
            return f"https://{fqdn}/mcp"
    return ""


def deploy(tag: str | None = None) -> None:
    project_endpoint = get_env("AZURE_AI_PROJECT_ENDPOINT")
    principal_id, client_id = _identity_principal_and_client()
    assign_identity_roles(principal_id)

    external = os.getenv("CUSTOMER_SUPPORT_EXTERNAL", "true").strip().lower() == "true"
    model = (
        os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or "gpt-4.1-mini"
    )
    customer_mcp_url = _resolve_mcp_url("CUSTOMER_MCP_URL", "CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server")
    product_mcp_url = _resolve_mcp_url("PRODUCT_MCP_URL", "PRODUCT_MCP_APP_NAME", "product-data-mcp-server")

    # When the MCP servers are protected with Easy Auth, resolve their audiences
    # and grant this agent's identity the Mcp.Invoke role so it can acquire
    # tokens. The audiences are passed to the container so the direct MCP calls
    # attach a bearer token.
    customer_mcp_audience = ""
    product_mcp_audience = ""
    if entra_auth_enabled():
        customer_app = os.getenv("CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server")
        product_app = os.getenv("PRODUCT_MCP_APP_NAME", "product-data-mcp-server")
        customer_mcp_audience = resolve_mcp_audience(customer_app)
        product_mcp_audience = resolve_mcp_audience(product_app)
        print("==> Granting Mcp.Invoke on the MCP app registrations")
        for audience in (customer_mcp_audience, product_mcp_audience):
            if audience:
                grant_mcp_role_to_principal(audience.removeprefix("api://"), principal_id)

    env_vars = {
        "HOST": "0.0.0.0",
        "PORT": str(PORT),
        "AZURE_CLIENT_ID": client_id,
        "AZURE_AI_PROJECT_ENDPOINT": project_endpoint,
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": model,
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": model,
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        "AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME", "text-embedding-3-small"),
        "OPENAI_API_VERSION": os.getenv("OPENAI_API_VERSION", "2024-05-01-preview"),
        # Keep the azure-ai-projects Responses instrumentor OFF (it defaults to
        # enabled): its AsyncStreamWrapper breaks agent-framework-openai's
        # streaming with_raw_response...parse() path. Enable via
        # AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING=true in ./.env.
        "AZURE_TRACING_GEN_AI_INSTRUMENT_RESPONSES_API": (
            "true"
            if os.getenv("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "false").strip().lower() == "true"
            else "false"
        ),
        "AZURE_SEARCH_ENDPOINT": get_env("AZURE_SEARCH_ENDPOINT"),
        "AZURE_SEARCH_ADMIN_KEY": os.getenv("AZURE_SEARCH_ADMIN_KEY", ""),
        "AZURE_SEARCH_PRODUCT_INDEX_NAME": os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products"),
        "AZURE_SEARCH_COMPLIANCE_INDEX_NAME": os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance"),
        # Direct MCP URLs so the container reaches the servers without a toolbox.
        "CUSTOMER_MCP_URL": customer_mcp_url,
        "PRODUCT_MCP_URL": product_mcp_url,
        # MCP audiences (set only when Easy Auth is enabled) so the direct MCP
        # calls attach an Entra bearer token.
        "CUSTOMER_MCP_AUDIENCE": customer_mcp_audience,
        "PRODUCT_MCP_AUDIENCE": product_mcp_audience,
        "APPLICATIONINSIGHTS_CONNECTION_STRING": os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", ""),
    }

    fqdn = deploy_container_app(
        app_name=APP_NAME,
        image_name=IMAGE_NAME,
        port=PORT,
        external=external,
        env_vars=env_vars,
        tag=tag,
        readiness_probe_path="/healthz",
        min_replicas=1,
    )
    if fqdn:
        print(f"\nCustomer Support Agent deployed: https://{fqdn}/")
    else:
        print("\nDeployed, but no ingress FQDN returned — check the Container App ingress.")


if __name__ == "__main__":
    built_tag = build() if "--build" in sys.argv else None
    deploy(tag=built_tag)
