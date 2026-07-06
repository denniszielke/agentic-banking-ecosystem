"""Grant the ``Mcp.Invoke`` app role to a Foundry hosted agent's Entra **Agent
Identity** so its toolboxes can authenticate to the customer / product MCP
servers using **agent identity** authentication (no client secret).

The employee advisory agent consumes the customer / product MCP servers through
Foundry toolboxes. When those toolboxes use an ``AgenticIdentityToken``
connection (auth type = agent identity, audience = ``api://<appId>``), Agent
Service mints a token for the agent's Entra Agent Identity and forwards it to
the MCP server. Entra only issues that token when the agent identity holds a
permission on the MCP resource — for these custom MCP APIs that is the
``Mcp.Invoke`` app role. This script assigns that role, mirroring
``deploy_customer_support_agent`` (which grants the same role to the customer
support agent's *managed* identity for its direct MCP calls).

What it does:

  1. Resolve the hosted agents' Entra Agent Identity object ids — from
     ``--agent-id`` / ``AGENT_IDENTITY_MCP_IDS`` or auto-discovered from the
     Microsoft Graph ``agentIdentity`` collection by matching the agent name.
  2. Resolve the ``api://<appId>`` audience of each MCP server's app
     registration (``<app>-mcp-auth``), created by the MCP deploy scripts.
  3. Grant ``Mcp.Invoke`` on each MCP app registration to each agent identity
     (idempotent — "already assigned" is treated as success).

Requires: Azure CLI signed in (``az login``) with rights to create app role
assignments (Global Administrator / Application Administrator / Privileged Role
Administrator), the MCP servers already deployed with ``ENTRA_AUTH_ENABLED=true``
(so the app registrations exist), and the hosted agent already deployed (so its
Entra Agent Identity exists).

Usage::

    # auto-discover the employee advisory agent identity and grant on both apps
    python -m scripts.grant_agent_identity_mcp_role

    # target explicit agent identity object ids (from the agent resource JSON
    # view in the Azure portal, or the Entra admin center → Agent ID)
    python -m scripts.grant_agent_identity_mcp_role \\
        --agent-id 6c4bb69b-3f8f-4f8a-972a-5eb5a9a23c71

Environment variables:
  AGENT_IDENTITY_MCP_IDS   Comma-separated Entra Agent Identity object ids to
                           grant (overrides auto-discovery).
  AZURE_AI_EMPLOYEE_AGENT_NAME  Hosted agent name to match (default:
                           employee-advisory-agent).
  CUSTOMER_MCP_APP_NAME    Customer MCP Container App name (default:
                           customer-data-mcp-server).
  PRODUCT_MCP_APP_NAME     Product MCP Container App name (default:
                           product-data-mcp-server).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

from scripts.auth_helpers import (  # noqa: E402  (after dotenv load)
    entra_auth_enabled,
    grant_mcp_role_to_principal,
    resolve_mcp_audience,
)

_GRAPH = "https://graph.microsoft.com"


def _az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["az", *args], check=False, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"az {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _az_rest_json(method: str, uri: str) -> object:
    result = _az(
        "rest", "--method", method, "--uri", uri,
        "--headers", "Content-Type=application/json",
    )
    out = result.stdout.strip()
    return json.loads(out) if out else None


def _discover_agent_identities(agent_names: list[str]) -> list[tuple[str, str]]:
    """Best-effort discovery of Entra Agent Identity object ids by agent name.

    Uses the Microsoft Graph ``agentIdentity`` collection (preview) and matches
    each configured agent name against the identity display name. Returns a list
    of ``(display_name, object_id)`` tuples.
    """
    uri = (
        f"{_GRAPH}/beta/servicePrincipals/microsoft.graph.agentIdentity"
        f"?$select=id,appId,displayName"
    )
    try:
        data = _az_rest_json("GET", uri)
    except RuntimeError as exc:
        print(f"  WARN: could not enumerate agent identities via Graph: {exc}")
        return []

    identities = (data or {}).get("value", []) if isinstance(data, dict) else []
    wanted = [n.lower() for n in agent_names]
    matches: list[tuple[str, str]] = []
    for identity in identities:
        display = (identity.get("displayName") or "").lower()
        if any(name in display for name in wanted):
            matches.append((identity.get("displayName") or "", identity["id"]))
    return matches


def _resolve_agent_ids(cli_ids: list[str]) -> list[str]:
    """Determine the Entra Agent Identity object ids to grant the role to."""
    if cli_ids:
        return cli_ids

    env_ids = os.getenv("AGENT_IDENTITY_MCP_IDS", "").strip()
    if env_ids:
        return [i.strip() for i in env_ids.split(",") if i.strip()]

    agent_name = os.getenv("AZURE_AI_EMPLOYEE_AGENT_NAME", "employee-advisory-agent")
    print(f"==> Auto-discovering the Entra Agent Identity for: {agent_name}")
    discovered = _discover_agent_identities([agent_name])
    for display, obj_id in discovered:
        print(f"  Found agent identity '{display}': {obj_id}")
    return [obj_id for _, obj_id in discovered]


def _resolve_mcp_apps() -> list[tuple[str, str]]:
    """Return ``(label, app_id)`` for each MCP server's app registration."""
    apps: list[tuple[str, str]] = []
    for label, env_var, default in (
        ("customer", "CUSTOMER_MCP_APP_NAME", "customer-data-mcp-server"),
        ("product", "PRODUCT_MCP_APP_NAME", "product-data-mcp-server"),
    ):
        app_name = os.getenv(env_var, default)
        audience = resolve_mcp_audience(app_name)
        if audience:
            apps.append((label, audience.removeprefix("api://")))
        else:
            print(
                f"  WARN: no '{app_name}-mcp-auth' app registration found for the "
                f"{label} MCP server. Deploy it with ENTRA_AUTH_ENABLED=true first."
            )
    return apps


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--agent-id",
        dest="agent_ids",
        action="append",
        default=[],
        metavar="OBJECT_ID",
        help="Entra Agent Identity object id to grant (repeatable). Overrides "
        "auto-discovery.",
    )
    args = parser.parse_args(argv)

    if not entra_auth_enabled():
        print(
            "NOTE: ENTRA_AUTH_ENABLED is false — the MCP servers run anonymously, "
            "so no Mcp.Invoke grant is required. Continuing anyway."
        )

    agent_ids = _resolve_agent_ids(args.agent_ids)
    if not agent_ids:
        print(
            "\nERROR: no Entra Agent Identity object ids to grant. Deploy the "
            "hosted agent first, then re-run — or pass it explicitly with "
            "--agent-id (see the object id in the agent resource JSON view).",
            file=sys.stderr,
        )
        return 1

    apps = _resolve_mcp_apps()
    if not apps:
        print(
            "\nERROR: no MCP app registrations resolved. Deploy the customer / "
            "product MCP servers with ENTRA_AUTH_ENABLED=true first.",
            file=sys.stderr,
        )
        return 1

    for agent_id in agent_ids:
        print(f"\n==> Granting Mcp.Invoke to agent identity {agent_id}")
        for label, app_id in apps:
            print(f"  {label} MCP ({app_id}):")
            grant_mcp_role_to_principal(app_id, agent_id)

    print(
        "\nDone. App role assignments can take 2–5 minutes to propagate. Attach an "
        "AgenticIdentityToken connection (audience api://<appId>) to each toolbox "
        "and set CUSTOMER_MCP_CONNECTION_ID / PRODUCT_MCP_CONNECTION_ID, then "
        "re-register the toolboxes."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
