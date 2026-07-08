"""Create a Fabric DataAgent Foundry connection with **user on-behalf-of** (OBO) auth.

When the recommender agent uses this connection, the Foundry model service
exchanges the **calling user's Entra token** for a Power BI–scoped token via
OBO and forwards it to the Fabric DataAgent. This means the DataAgent queries
run as the signed-in customer — their Fabric workspace permissions apply.

Prerequisites
-------------
1. The Foundry AI Services enterprise application must have admin-consented
   delegated Power BI permissions (``Dataset.ReadWrite.All``).  Grant via::

       az ad sp list --display-name "Azure AI Services" --query "[0].appId" -o tsv
       # then in the Entra portal: Enterprise Apps → Azure AI Services
       # → Permissions → Grant admin consent for Power BI delegated scopes

2. The signed-in user (or each customer user) must have at least **Viewer**
   access on the Fabric workspace that backs the Genie / DataAgent.

Usage::

    python -m scripts.create_fabric_obo_connection

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT   Foundry project endpoint (required).
  FABRIC_OBO_CONNECTION_NAME  Name for the new connection
                              (default: fabric_dataagent_obo).
  FABRIC_OBO_AUDIENCE         Token audience for OBO token
                              (default: https://analysis.windows.net/powerbi/api).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

from scripts._cli import normalize  # noqa: E402


def _az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        normalize(["az", *args]), check=False, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"az {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _project_endpoint() -> str:
    ep = os.getenv("AZURE_AI_PROJECT_ENDPOINT", "").strip().rstrip("/")
    if not ep:
        raise RuntimeError("AZURE_AI_PROJECT_ENDPOINT is required.")
    return ep


def create_obo_connection(
    connection_name: str,
    audience: str,
) -> None:
    """Create (or update) a fabric_dataagent_preview connection with AAD/OBO auth
    via the ARM management-plane API."""

    sub = "e7fbef45-eecb-4fb0-8af5-a70aa3f30715"
    rg = os.getenv("AZURE_RESOURCE_GROUP", "rg-banking")
    account = _derive_account_name()
    project = _derive_project_name()

    uri = (
        f"https://management.azure.com/subscriptions/{sub}/resourceGroups/{rg}"
        f"/providers/Microsoft.CognitiveServices/accounts/{account}"
        f"/projects/{project}/connections/{connection_name}?api-version=2025-04-01-preview"
    )

    body = {
        "properties": {
            "authType": "AAD",
            "category": "CustomKeys",
            "metadata": {
                "type": "fabric_dataagent_preview",
            },
            "target": "-",
            "isDefault": False,
            "group": "AzureAI",
            "useWorkspaceManagedIdentity": False,
        }
    }

    print(f"==> Creating OBO connection '{connection_name}' via ARM API")
    print(f"    authType  : AAD (user on-behalf-of)")
    print(f"    audience  : {audience}")
    print(f"    URI       : {uri}")

    result = _az(
        "rest",
        "--method", "PUT",
        "--uri", uri,
        "--headers", "Content-Type=application/json",
        "--body", json.dumps(body),
        check=False,
    )

    if result.returncode == 0:
        resp = json.loads(result.stdout) if result.stdout.strip() else {}
        props = resp.get("properties", {})
        print(f"\nConnection created successfully.")
        print(f"  Name     : {resp.get('name', connection_name)}")
        print(f"  authType : {props.get('authType', 'AAD')}")
        print(f"  ID       : {resp.get('id', 'n/a')}")
        print(
            f"\nSet FABRIC_CONNECTION_ID=\"{connection_name}\" in ./.env and "
            "redeploy the recommender agent."
        )
    else:
        combined = result.stderr + result.stdout
        try:
            idx = combined.index("{")
            err = json.loads(combined[idx:])
            msg = (
                err.get("error", {}).get("message")
                or err.get("message")
                or combined
            )
        except (ValueError, KeyError):
            msg = combined.strip()
        print(f"\nERROR: {msg}", file=sys.stderr)
        sys.exit(1)


def _derive_account_name() -> str:
    """Derive the AI Services account name from AZURE_AI_PROJECT_ENDPOINT."""
    ep = _project_endpoint()
    # https://ai-account-nu55j3ncdusuo.services.ai.azure.com/api/projects/...
    host = ep.split("//", 1)[-1].split(".")[0]
    return host


def _derive_project_name() -> str:
    """Derive the project name from AZURE_AI_PROJECT_ENDPOINT."""
    ep = _project_endpoint()
    # .../api/projects/ai-banking-banking
    parts = ep.rstrip("/").split("/")
    return parts[-1]


def main() -> None:
    connection_name = os.getenv("FABRIC_OBO_CONNECTION_NAME", "fabric_dataagent_obo")
    audience = os.getenv(
        "FABRIC_OBO_AUDIENCE",
        "https://analysis.windows.net/powerbi/api",
    )
    create_obo_connection(connection_name=connection_name, audience=audience)


if __name__ == "__main__":
    main()
