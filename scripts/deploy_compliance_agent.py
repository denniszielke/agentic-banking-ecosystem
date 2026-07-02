"""Deploy the **Compliance Agent** as an Azure AI Foundry hosted agent.

Bank North's regulatory agent, offered cross-organisation to Bank South over
A2A. It is index-only (no MCP dependency): it consumes the Compliance rules
Azure AI Search index. Run it after ``azd up`` and after the compliance index
has been created and ingested
(``scripts/create_search_indexes.py`` + ``scripts/ingest_knowledge.py``).

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT           Foundry project endpoint (required).
  AZURE_CONTAINER_REGISTRY_ENDPOINT   ACR login server for the agent image (required).
  AZURE_AI_COMPLIANCE_AGENT_NAME      Hosted agent name (default: compliance-agent).
  AZURE_SEARCH_ENDPOINT               Compliance index endpoint (required at runtime).
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME  Index name (default: banking-compliance).
  COMPLIANCE_BANK_ID                  Owning bank id (default: bank-north).
"""

from __future__ import annotations

import os

from scripts.agent_deploy_helpers import (
    deploy_hosted_agent,
    get_client,
    load_agent_card,
    resolve_registry,
)

COMPLIANCE_AGENT_CARD = load_agent_card("src/compliance_agent/agentcard.json")


def deploy() -> None:
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        print("Skipping compliance agent deployment: AZURE_AI_PROJECT_ENDPOINT is required.")
        return
    registry = resolve_registry()

    client = get_client()
    deploy_hosted_agent(
        client,
        agent_name=os.getenv("AZURE_AI_COMPLIANCE_AGENT_NAME", "compliance-agent"),
        description="Compliance hosted agent (Bank North, cross-org A2A service)",
        registry=registry,
        project_endpoint=project_endpoint,
        dockerfile_rel="src/compliance_agent/Dockerfile",
        extra_env={
            "BANK_ID": os.getenv("COMPLIANCE_BANK_ID", "bank-north"),
        },
        agent_card=COMPLIANCE_AGENT_CARD,
    )


if __name__ == "__main__":
    deploy()
