"""Deploy the **Recommender Agent** as an Azure AI Foundry hosted agent.

The Volksbank personal banking assistant — grounded on the Fabric data agent
for live account/transaction data and the finance-tools Foundry toolbox for
financial calculations. Run it after the finance toolbox is registered:

    python -m scripts.register_finance_toolbox

The Fabric data agent connection must exist in the Foundry project before
deployment.

Usage::

    python -m scripts.deploy_recommender_agent

Environment variables (populated from ``.env`` by ``azd up``):
  AZURE_AI_PROJECT_ENDPOINT              Foundry project endpoint (required).
  AZURE_CONTAINER_REGISTRY_ENDPOINT      ACR login server for the agent image (required).
  AZURE_AI_RECOMMENDER_AGENT_NAME        Hosted agent name (default: recommender-agent).
  FABRIC_CONNECTION_ID                   Foundry project connection ID (required).
  FINANCE_TOOLBOX_NAME                   Finance MCP toolbox (default: finance-tools).
  FINANCE_MCP_URL                        Direct finance MCP URL for local dev (optional).
"""

from __future__ import annotations

import os

from scripts.agent_deploy_helpers import (
    deploy_hosted_agent,
    get_client,
    load_agent_card,
    resolve_registry,
)

RECOMMENDER_AGENT_CARD = load_agent_card("src/recommender_agent/agentcard.json")


def deploy() -> None:
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        print("Skipping recommender agent deployment: AZURE_AI_PROJECT_ENDPOINT is required.")
        return
    fabric_connection_id = os.getenv("FABRIC_CONNECTION_ID", "").strip()
    if not fabric_connection_id:
        print("Skipping recommender agent deployment: FABRIC_CONNECTION_ID is required.")
        return
    registry = resolve_registry()

    client = get_client()
    deploy_hosted_agent(
        client,
        agent_name=os.getenv("AZURE_AI_RECOMMENDER_AGENT_NAME", "recommender-agent"),
        description="Recommender hosted agent (Volksbank personal banking assistant)",
        registry=registry,
        project_endpoint=project_endpoint,
        dockerfile_rel="src/recommender_agent/Dockerfile",
        extra_env={
            "FABRIC_CONNECTION_ID": fabric_connection_id,
            "FINANCE_TOOLBOX_NAME": os.getenv("FINANCE_TOOLBOX_NAME", "finance-tools"),
            "FINANCE_MCP_URL": os.getenv("FINANCE_MCP_URL", ""),
        },
        agent_card=RECOMMENDER_AGENT_CARD,
    )


if __name__ == "__main__":
    deploy()
