"""Deploy the **Web Recommender Agent** as an Azure Container App.

The Volksbank personal banking assistant - an AG-UI web agent that reaches
live account and transaction data through a Fabric DataAgent (user OBO) and
offers financial calculations via the finance MCP server (direct URL, no auth).

Run it after ``azd up`` and after the Fabric OBO connection and OAuth app
registration are created:

    python -m scripts.create_fabric_obo_connection
    python -m scripts.setup_web_recommender_oauth_app --fqdn <app-fqdn>

Usage::

    python -m scripts.deploy_web_recommender_agent --build   # build + deploy
    python -m scripts.deploy_web_recommender_agent           # deploy existing image

Environment variables (populated from ``.env`` by ``azd up``):
  AZURE_RESOURCE_GROUP                   target resource group (required)
  AZURE_CONTAINER_APPS_ENVIRONMENT_NAME  Container Apps environment (required)
  AZURE_IDENTITY_NAME                    user-assigned managed identity (required)
  AZURE_AI_PROJECT_ENDPOINT              Foundry project endpoint (required)
  FABRIC_CONNECTION_ID                   Fabric OBO connection name
                                         (default: fabric_dataagent_obo)
  FINANCE_MCP_URL                        Direct finance MCP URL
  WEB_RECOMMENDER_CLIENT_ID             Entra app registration client id for OBO
  WEB_RECOMMENDER_CLIENT_SECRET         Client secret for OBO token exchange
  WEB_RECOMMENDER_TENANT_ID             Entra tenant id
  APPLICATIONINSIGHTS_CONNECTION_STRING  telemetry sink (optional)
  WEB_RECOMMENDER_APP_NAME               Container App name
                                         (default: web-recommender-agent)
  WEB_RECOMMENDER_PORT                   container port (default: 8092)
  WEB_RECOMMENDER_EXTERNAL               "true" for public ingress (default: true)
  TAG                                    image tag to deploy (default: latest)
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from scripts.deploy_helpers import (
    build_image,
    deploy_container_app,
    get_env,
    resolve_registry,
)

APP_NAME = os.getenv("WEB_RECOMMENDER_APP_NAME", "web-recommender-agent")
IMAGE_NAME = "web-recommender-agent"
PORT = int(os.getenv("WEB_RECOMMENDER_PORT", "8092"))
_DOCKERFILE = "src/web_recommender_agent/Dockerfile"


def build() -> str:
    registry = resolve_registry()
    source_path = Path(__file__).resolve().parents[1]
    dockerfile = str(source_path / _DOCKERFILE)
    return build_image(registry, IMAGE_NAME, source_path, dockerfile=dockerfile)


def deploy(tag: str | None = None) -> str | None:
    external = os.getenv("WEB_RECOMMENDER_EXTERNAL", "true").strip().lower() == "true"

    tenant_id = os.getenv("WEB_RECOMMENDER_TENANT_ID", os.getenv("AZURE_TENANT_ID", ""))
    client_id = os.getenv("WEB_RECOMMENDER_CLIENT_ID", "")
    client_secret = os.getenv("WEB_RECOMMENDER_CLIENT_SECRET", "")

    if not client_id:
        print(
            "  WARN: WEB_RECOMMENDER_CLIENT_ID not set - OBO auth will not work.\n"
            "  Run: python -m scripts.setup_web_recommender_oauth_app"
        )

    env_vars = {
        "AZURE_AI_PROJECT_ENDPOINT": get_env("AZURE_AI_PROJECT_ENDPOINT"),
        "FABRIC_CONNECTION_ID": os.getenv("FABRIC_CONNECTION_ID", "fabric_dataagent_obo"),
        "FINANCE_MCP_URL": os.getenv(
            "FINANCE_MCP_URL",
            "https://finance-mcp-server.whitemoss-40897c95.swedencentral.azurecontainerapps.io/mcp",
        ),
        "AZURE_AI_MODEL_DEPLOYMENT_NAME": os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME", "gpt-4.1-mini"),
        "AZURE_OPENAI_CHAT_DEPLOYMENT_NAME": os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME", ""),
        # OAuth / OBO settings - client_id exposed to frontend via server-side injection.
        "WEB_RECOMMENDER_CLIENT_ID": client_id,
        "WEB_RECOMMENDER_CLIENT_SECRET": client_secret,
        "WEB_RECOMMENDER_TENANT_ID": tenant_id,
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
        readiness_probe_path="/healthz",
    )

    if fqdn:
        url = f"https://{fqdn}/"
        print(f"\nWeb Recommender Agent deployed: {url}")
        if client_id:
            print(
                f"\n  Next: add the Container App URL as a redirect URI:\n"
                f"  python -m scripts.setup_web_recommender_oauth_app --fqdn {fqdn}"
            )
    else:
        print(
            "\nWeb Recommender Agent deployed, but no ingress FQDN returned. "
            "Set WEB_RECOMMENDER_EXTERNAL=true or check the ingress."
        )
    return fqdn


if __name__ == "__main__":
    do_build = "--build" in sys.argv
    built_tag: str | None = None
    if do_build:
        built_tag = build()
    deploy(tag=built_tag)
