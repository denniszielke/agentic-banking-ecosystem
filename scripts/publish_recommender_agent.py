"""Publish the **Recommender Agent** to the Azure AI Foundry project.

After the Container App is deployed by ``scripts/deploy_recommender_agent.py``,
this script registers the agent card with the Foundry project so that the
agent appears in the project's agent catalogue and can be discovered by other
agents or tools.

This script does NOT deploy the container — run ``deploy_recommender_agent.py``
first.

Usage::

    python -m scripts.publish_recommender_agent

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT         Foundry project endpoint (required).
  RECOMMENDER_AGENT_APP_NAME        Container App name (default: recommender-agent).
  AZURE_RESOURCE_GROUP              Resource group (used to derive the app URL).
  RECOMMENDER_AGENT_PUBLIC_URL      Override the public URL (skips FQDN lookup).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from scripts.agent_deploy_helpers import get_client, get_container_app_fqdn, get_env

_REPO_ROOT = Path(__file__).resolve().parents[1]
_AGENT_CARD_PATH = _REPO_ROOT / "src" / "recommender_agent" / "agentcard.json"

APP_NAME = os.getenv("RECOMMENDER_AGENT_APP_NAME", "recommender-agent")


def _resolve_public_url() -> str:
    url = os.getenv("RECOMMENDER_AGENT_PUBLIC_URL", "").strip()
    if url:
        return url
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    if resource_group:
        fqdn = get_container_app_fqdn(resource_group, APP_NAME)
        if fqdn:
            return f"https://{fqdn}"
    return ""


def publish() -> None:
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        print("Skipping publish: AZURE_AI_PROJECT_ENDPOINT is required.")
        return

    public_url = _resolve_public_url()
    if not public_url:
        print(
            "Skipping publish: set RECOMMENDER_AGENT_PUBLIC_URL, or set "
            "AZURE_RESOURCE_GROUP so the Container App FQDN can be derived."
        )
        return

    agent_card = json.loads(_AGENT_CARD_PATH.read_text(encoding="utf-8"))

    client = get_client()
    agent = client.agents.create_version(
        name=APP_NAME,
        description=agent_card.get("description", "Volksbank Recommender Agent"),
        metadata={
            "agentcard": json.dumps(agent_card),
            "public_url": public_url,
            "source": "recommender_agent",
        },
    )
    client.agents.update(name=APP_NAME, default_version=agent.version)

    project_endpoint = get_env("AZURE_AI_PROJECT_ENDPOINT")
    print(f"Recommender Agent '{APP_NAME}' published (version '{agent.version}').")
    print(f"  Public URL:       {public_url}")
    print(f"  Foundry project:  {project_endpoint}")


if __name__ == "__main__":
    publish()
