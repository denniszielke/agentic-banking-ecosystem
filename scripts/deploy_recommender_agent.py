"""Deploy the **Recommender Agent** as an Azure AI Foundry hosted agent.

The Volksbank personal banking assistant. It consumes live account and
transaction data via a Microsoft Fabric data agent and financial calculation
tools via the Finance MCP server toolbox.

Run it after ``azd up`` and after the finance toolbox is registered:

    python -m scripts.register_finance_toolbox

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT           Foundry project endpoint (required).
  AZURE_CONTAINER_REGISTRY_ENDPOINT   ACR login server for the agent image (required).
  AZURE_AI_RECOMMENDER_AGENT_NAME     Hosted agent name (default: recommender-agent).
  FABRIC_CONNECTION_ID                Foundry project connection ID for the Fabric
                                      data agent (required at runtime).
  FINANCE_TOOLBOX_NAME                Finance MCP toolbox (default: finance-tools).
  FINANCE_MCP_URL                     Direct finance MCP URL for local dev (optional).
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
    registry = resolve_registry()

    client = get_client()
    deploy_hosted_agent(
        client,
        agent_name=os.getenv("AZURE_AI_RECOMMENDER_AGENT_NAME", "recommender-agent"),
        description="Volksbank personal banking assistant (Foundry hosted agent)",
        registry=registry,
        project_endpoint=project_endpoint,
        dockerfile_rel="src/recommender_agent/Dockerfile",
        extra_env={
            "FINANCE_TOOLBOX_NAME": os.getenv("FINANCE_TOOLBOX_NAME", "finance-tools"),
            # Direct MCP URL override (blank by default → use the toolbox).
            "FINANCE_MCP_URL": os.getenv("FINANCE_MCP_URL", ""),
        },
        agent_card=RECOMMENDER_AGENT_CARD,
    )


if __name__ == "__main__":
    deploy()
