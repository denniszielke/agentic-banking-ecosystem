"""Grant the Agent 365 **observability telemetry-export** permission to the
Foundry hosted agents' Entra Agent Identities.

The Foundry hosted agents (compliance, employee advisory) ship the Agent 365
OpenTelemetry exporter. When that exporter tries to push genAI spans to the
Agent 365 ingestion service it authenticates with the agent's **Entra Agent
Identity**. Recent observability package versions require that identity to hold
the ``Agent365.Observability.OtelWrite`` app role, otherwise the export fails
with::

    HTTP 403 authorization error: the token is missing the required
    'Agent365.Observability.OtelWrite' app role.

This script assigns that app role to each hosted agent's Entra Agent Identity,
exactly as documented at https://aka.ms/foundry-grant-agent-365-permissions:

  1. Resolve the ``Agent365Observability`` service principal object id (the
     *resource* that defines the app role) via Microsoft Graph.
  2. Resolve the hosted agents' Entra Agent Identity object ids — either from
     ``--agent-id`` / ``A365_OBSERVABILITY_AGENT_IDS`` or auto-discovered from
     the Graph ``agentIdentity`` collection by matching the agent names.
  3. POST an ``appRoleAssignment`` granting
     ``Agent365.Observability.OtelWrite`` (app role id
     ``8f71190c-00c8-461d-a63b-f74abde9ba52``) to each identity. Existing
     assignments (HTTP 409) are treated as success (idempotent).
  4. Verify each assignment.

Requires: Azure CLI signed in (``az login``) as a **Global Administrator** or
**Application Administrator** (needed to create app role assignments), and the
hosted agents already deployed (so their Entra Agent Identities exist).

Usage::

    # auto-discover the compliance + employee advisory agent identities
    python -m scripts.grant_observability_permissions

    # target explicit agent identity object ids (from the 403 error message or
    # the agent resource JSON view in the Azure portal)
    python -m scripts.grant_observability_permissions \\
        --agent-id a64b12d3-5a28-42c9-bfb9-ebfb929df563 \\
        --agent-id 8874b705-eb1c-496f-b5db-13de3aeba7d9

Environment variables:
  A365_OBSERVABILITY_AGENT_IDS    Comma-separated Entra Agent Identity object ids
                                  to grant (overrides auto-discovery).
  AZURE_AI_COMPLIANCE_AGENT_NAME  Hosted agent name (default: compliance-agent).
  AZURE_AI_EMPLOYEE_AGENT_NAME    Hosted agent name (default: employee-advisory-agent).
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

from scripts._cli import normalize
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

# Well-known, tenant-independent identifier for the Agent 365
# "Agent365.Observability.OtelWrite" app role. See
# https://aka.ms/foundry-grant-agent-365-permissions.
OTEL_WRITE_APP_ROLE_ID = "8f71190c-00c8-461d-a63b-f74abde9ba52"

# Display name of the service principal that defines the observability app role.
OBSERVABILITY_SP_DISPLAY_NAME = "Agent365Observability"

_GRAPH = "https://graph.microsoft.com"


def _az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run an ``az`` command, capturing stdout/stderr."""
    result = subprocess.run(
        normalize(["az", *args]), check=False, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"az {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _az_rest_json(method: str, uri: str, body: dict | None = None) -> object:
    """Call ``az rest`` against Microsoft Graph and parse the JSON response."""
    args = ["rest", "--method", method, "--uri", uri, "--headers", "Content-Type=application/json"]
    if body is not None:
        args += ["--body", json.dumps(body)]
    result = _az(*args)
    out = result.stdout.strip()
    return json.loads(out) if out else None


def _resolve_observability_sp_id() -> str:
    """Return the ``Agent365Observability`` service principal object id."""
    uri = (
        f"{_GRAPH}/v1.0/servicePrincipals"
        f"?$filter=displayName eq '{OBSERVABILITY_SP_DISPLAY_NAME}'"
        f"&$select=id,displayName"
    )
    data = _az_rest_json("GET", uri)
    values = (data or {}).get("value", []) if isinstance(data, dict) else []
    if not values:
        raise RuntimeError(
            f"'{OBSERVABILITY_SP_DISPLAY_NAME}' service principal not found in this "
            "tenant. The Agent 365 observability service may not be provisioned — "
            "ask your Microsoft 365 administrator to enable it."
        )
    sp_id = values[0]["id"]
    print(f"==> {OBSERVABILITY_SP_DISPLAY_NAME} service principal: {sp_id}")
    return sp_id


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

    env_ids = os.getenv("A365_OBSERVABILITY_AGENT_IDS", "").strip()
    if env_ids:
        return [i.strip() for i in env_ids.split(",") if i.strip()]

    agent_names = [
        os.getenv("AZURE_AI_COMPLIANCE_AGENT_NAME", "compliance-agent"),
        os.getenv("AZURE_AI_EMPLOYEE_AGENT_NAME", "employee-advisory-agent"),
    ]
    print(f"==> Auto-discovering Entra Agent Identities for: {', '.join(agent_names)}")
    discovered = _discover_agent_identities(agent_names)
    for display, obj_id in discovered:
        print(f"  Found agent identity '{display}': {obj_id}")
    return [obj_id for _, obj_id in discovered]


def _assign_role(agent_principal_id: str, resource_sp_id: str) -> None:
    """Assign the OtelWrite app role to one agent identity (idempotent)."""
    uri = (
        f"{_GRAPH}/v1.0/servicePrincipals/{agent_principal_id}/appRoleAssignments"
    )
    body = {
        "principalId": agent_principal_id,
        "resourceId": resource_sp_id,
        "appRoleId": OTEL_WRITE_APP_ROLE_ID,
    }
    result = _az(
        "rest",
        "--method", "POST",
        "--uri", uri,
        "--headers", "Content-Type=application/json",
        "--body", json.dumps(body),
        check=False,
    )
    if result.returncode == 0:
        print(f"  Granted Agent365.Observability.OtelWrite to {agent_principal_id}.")
        return

    stderr = result.stderr.lower()
    if "409" in stderr or "conflict" in stderr or "already exists" in stderr:
        print(f"  Already granted for {agent_principal_id} (skipped).")
        return
    raise RuntimeError(
        f"Failed to assign the OtelWrite app role to {agent_principal_id}: "
        f"{result.stderr.strip() or result.stdout.strip()}"
    )


def _verify(agent_principal_id: str) -> bool:
    """Return True if the OtelWrite app role is present on the identity."""
    uri = (
        f"{_GRAPH}/v1.0/servicePrincipals/{agent_principal_id}/appRoleAssignments"
        f"?$select=appRoleId"
    )
    try:
        data = _az_rest_json("GET", uri)
    except RuntimeError as exc:
        print(f"  WARN: could not verify {agent_principal_id}: {exc}")
        return False
    values = (data or {}).get("value", []) if isinstance(data, dict) else []
    return any(v.get("appRoleId") == OTEL_WRITE_APP_ROLE_ID for v in values)


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

    resource_sp_id = _resolve_observability_sp_id()
    agent_ids = _resolve_agent_ids(args.agent_ids)

    if not agent_ids:
        print(
            "\nERROR: no Entra Agent Identity object ids to grant. Deploy the "
            "hosted agents first, then re-run — or pass them explicitly with "
            "--agent-id (see the object id in the 403 error message).",
            file=sys.stderr,
        )
        return 1

    failures = 0
    for agent_id in agent_ids:
        print(f"\n==> Granting observability permission to {agent_id}")
        try:
            _assign_role(agent_id, resource_sp_id)
        except RuntimeError as exc:
            print(f"  ERROR: {exc}", file=sys.stderr)
            failures += 1
            continue
        if _verify(agent_id):
            print(f"  Verified: OtelWrite app role present on {agent_id}.")
        else:
            print(
                f"  NOTE: assignment not yet visible for {agent_id} — "
                "app role assignments can take 2–5 minutes to propagate."
            )

    print("\nDone." if not failures else f"\nDone with {failures} failure(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
