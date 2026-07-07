"""Deploy the **Fabric Agent** as an Azure Container App.

The consumer-facing agent + web UI (AG-UI) behind Bank South's customer app —
variant that reaches customer and product data through Microsoft Fabric data
agents via Foundry project connections instead of the custom MCP servers.

Unlike the compliance and employee agents (Foundry hosted agents), this one runs
as a public Container App serving the chat UI on port 8090.

Run it after ``azd up`` and after the search indexes are created + ingested.
The Fabric data agents and their Foundry project connections must exist before
deployment.

Usage::

    python -m scripts.deploy_fabric_agent --build   # build in ACR, then deploy
    python -m scripts.deploy_fabric_agent           # deploy existing image

Environment variables (populated from ``.env`` by ``azd up``):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  AZURE_AI_PROJECT_ENDPOINT              Foundry project endpoint (required)
  AZURE_SEARCH_ENDPOINT                  search endpoint (required)
  CUSTOMER_FABRIC_CONNECTION_ID          Foundry project connection ID for the
                                         customer Fabric data agent (required)
  PRODUCT_FABRIC_CONNECTION_ID           Foundry project connection ID for the
                                         product Fabric data agent (required)
  APPLICATIONINSIGHTS_CONNECTION_STRING  telemetry sink (optional)
  FABRIC_AGENT_APP_NAME                  Container App name (default: fabric-agent)
  FABRIC_AGENT_PORT                      container port (default: 8090)
  FABRIC_AGENT_EXTERNAL                  "true" for public ingress (default: true)
  COMPLIANCE_A2A_ENABLED                 "true" to consume Bank North's Compliance
                                         agent over A2A (default: false)
  AZURE_AI_COMPLIANCE_AGENT_NAME         compliance hosted-agent name (default: compliance-agent)
  COMPLIANCE_AGENT_A2A_URL               direct A2A endpoint override (auto-derived if unset)
  COMPLIANCE_AGENT_AUDIENCE              Entra audience for the A2A bearer token
                                         (default: https://ai.azure.com)
  TAG                                    image tag to deploy (default: latest)
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from scripts._cli import normalize
from scripts.deploy_helpers import (
    build_image,
    deploy_container_app,
    get_env,
    resolve_registry,
)

APP_NAME = os.getenv("FABRIC_AGENT_APP_NAME", "fabric-agent")
IMAGE_NAME = "fabric-agent"
PORT = int(os.getenv("FABRIC_AGENT_PORT", "8090"))
_DOCKERFILE = "src/fabric_agent/Dockerfile"

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
        normalize(["az", "identity", "show", "-g", rg, "-n", name,
         "--query", "[principalId, clientId]", "-o", "tsv"]),
        check=True, capture_output=True, text=True,
    ).stdout.split()
    return out[0], out[1]


def _grant_role(principal_id: str, role_id: str, scope: str) -> None:
    try:
        subprocess.run(
            normalize(["az", "role", "assignment", "create",
             "--assignee-object-id", principal_id,
             "--assignee-principal-type", "ServicePrincipal",
             "--role", role_id, "--scope", scope]),
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
        normalize(["az", "group", "show", "-n", rg, "--query", "id", "-o", "tsv"]),
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    print("==> Assigning managed identity roles")
    _grant_role(principal_id, _COGNITIVE_SERVICES_USER, rg_scope)       # consume Foundry models
    _grant_role(principal_id, _SEARCH_INDEX_DATA_READER, rg_scope)      # read search indexes
    _grant_role(principal_id, _MONITORING_METRICS_PUBLISHER, rg_scope)  # publish telemetry


def deploy(tag: str | None = None) -> None:
    project_endpoint = get_env("AZURE_AI_PROJECT_ENDPOINT")
    principal_id, client_id = _identity_principal_and_client()
    assign_identity_roles(principal_id)

    external = os.getenv("FABRIC_AGENT_EXTERNAL", "true").strip().lower() == "true"
    model = (
        os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
        or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
        or "gpt-4.1-mini"
    )

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
        # streaming with_raw_response...parse() path.
        "AZURE_TRACING_GEN_AI_INSTRUMENT_RESPONSES_API": (
            "true"
            if os.getenv("AZURE_EXPERIMENTAL_ENABLE_GENAI_TRACING", "false").strip().lower() == "true"
            else "false"
        ),
        "AZURE_SEARCH_ENDPOINT": get_env("AZURE_SEARCH_ENDPOINT"),
        "AZURE_SEARCH_ADMIN_KEY": os.getenv("AZURE_SEARCH_ADMIN_KEY", ""),
        "AZURE_SEARCH_PRODUCT_INDEX_NAME": os.getenv("AZURE_SEARCH_PRODUCT_INDEX_NAME", "banking-products"),
        # Foundry project connection IDs for the Fabric data agents.
        "CUSTOMER_FABRIC_CONNECTION_ID": get_env("CUSTOMER_FABRIC_CONNECTION_ID"),
        "PRODUCT_FABRIC_CONNECTION_ID": get_env("PRODUCT_FABRIC_CONNECTION_ID"),
        # Cross-org A2A: consume Bank North's Compliance hosted agent over A2A.
        "COMPLIANCE_A2A_ENABLED": os.getenv("COMPLIANCE_A2A_ENABLED", "false"),
        "AZURE_AI_COMPLIANCE_AGENT_NAME": os.getenv("AZURE_AI_COMPLIANCE_AGENT_NAME", "compliance-agent"),
        "COMPLIANCE_AGENT_A2A_URL": os.getenv("COMPLIANCE_AGENT_A2A_URL", ""),
        "COMPLIANCE_AGENT_AUDIENCE": os.getenv("COMPLIANCE_AGENT_AUDIENCE", "https://ai.azure.com"),
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
        print(f"\nFabric Agent deployed: https://{fqdn}/")
    else:
        print("\nDeployed, but no ingress FQDN returned — check the Container App ingress.")


if __name__ == "__main__":
    built_tag = build() if "--build" in sys.argv else None
    deploy(tag=built_tag)
