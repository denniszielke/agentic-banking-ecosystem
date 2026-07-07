"""Create Service Principals for Agent 365 MCP servers in your tenant (admin only).

Python port of ``New-Agent365ToolsServicePrincipalProdPublic.ps1``. It follows the
repo convention of driving Entra operations through the Azure CLI (``az``) instead
of the Microsoft.Graph PowerShell modules, so it fits the rest of ``scripts/*.py``
and only needs ``az login`` plus admin permissions.

Two provisioning models:

  V1  Creates the shared 'Agent 365 Tools' Service Principal
      (AppId ea9ffc3e-8a23-4a7d-836d-234d7c7565c1). All V1 servers share this
      single resource and use the ``McpServers.*.All`` scopes.

  V2  Creates one Service Principal per MCP server using per-server AppIds.
      V2 AppIds are discovered from the live Agent 365 V2 endpoint
      (https://agent365.svc.cloud.microsoft/agents/v2/discoverMCPServers) and
      unioned with a hardcoded fallback list. V2 servers use the
      ``Tools.ListInvoke.All`` scope against their own audience GUID. Pass
      ``--v2-app-ids`` to bypass the live call and supply AppIds directly.

Use ``--mode all`` (default) during migration when the tenant may have both V1
and V2 servers.

Requires:
  * Admin permissions to create Service Principals (Application.ReadWrite.All, or
    the Global Administrator / Application Administrator role).
  * Azure CLI (``az login``) — used both to create the Service Principals and to
    acquire a token for the discover endpoint.

This script is safe to re-run — existing Service Principals are skipped, not
re-created.

Usage::

    # Create the V1 SP and discover + create the V2 SPs from the live endpoint
    python -m scripts.create_agent365_tools_service_principals

    # V2 only
    python -m scripts.create_agent365_tools_service_principals --mode v2

    # Both V1 and V2 (default)
    python -m scripts.create_agent365_tools_service_principals --mode all

    # V2 with explicit AppIds (skip the live discover call)
    python -m scripts.create_agent365_tools_service_principals \
        --mode v2 --v2-app-ids 05879165-0320-489e-b644-f72b33f3edf0
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

from scripts._cli import normalize  # noqa: E402


def _az(*args: str, check: bool = True) -> str:
    """Run an ``az`` command and return trimmed stdout."""
    result = subprocess.run(
        normalize(["az", *args]), check=False, capture_output=True, text=True
    )
    if check and result.returncode != 0:
        raise RuntimeError(
            f"az {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout.strip()


# V1: shared ATG AppId (WorkIQToolsProdAppId) — all V1 servers share this resource.
V1_APP_ID = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1"

# V2 discover endpoint — returns a bare JSON array of available MCP servers.
V2_DISCOVER_URL = "https://agent365.svc.cloud.microsoft/agents/v2/discoverMCPServers"

# V2 scope value used by all per-server entries.
V2_SCOPE_VALUE = "Tools.ListInvoke.All"

# V2 fallback AppIds — used when the discover endpoint is unreachable.
# Source: MCPPlatform_McpScopedApps__ServerAppMappings__* configuration values.
V2_FALLBACK_APP_IDS = [
    "16b1878d-62c7-4009-aa25-68989d63bbad",  # mcp_MailTools
    "147dc821-b413-44c0-8009-1a3098378012",  # mcp_MeServer
    "910333d2-47e9-43ca-981f-6df2f4531ef4",  # mcp_CalendarTools
    "ce5029ee-c1d3-45c0-bdcc-efb5a4245687",  # mcp_TeamsServer
    "b0b2a2bb-6361-4549-a00c-a018417eb8e2",  # mcp_OneDriveRemoteServer
    "292cff14-c0e8-4116-9e3b-99934ae05766",  # mcp_SharePointRemoteServer
    "2dbeefeb-6462-48a4-abe6-1c4989699319",  # mcp_AdminTools
    "c2d0c2b6-8013-4346-9f8b-b81d3b754a29",  # mcp_WordServer
    "ab7c82de-7946-4454-ac28-70249d17c95e",  # mcp_M365Copilot
]

_GUID_PREFIX = re.compile(r"^[0-9a-f]{8}-", re.IGNORECASE)


def _get_access_token(resource: str) -> str:
    """Acquire an access token for ``resource`` via the Azure CLI (empty on failure)."""
    try:
        return _az(
            "account", "get-access-token",
            "--resource", resource,
            "--query", "accessToken", "-o", "tsv",
        )
    except RuntimeError as exc:
        print(
            "  WARNING: could not acquire a token via az CLI. Ensure you are "
            f"logged in with 'az login'.\n  Detail: {exc}"
        )
        return ""


def _discover_v2_app_ids() -> list[str]:
    """Call the V2 discover endpoint and extract per-server AppIds (audience GUIDs)."""
    print(f"Discovering V2 AppIds from: {V2_DISCOVER_URL}")

    token = _get_access_token(V1_APP_ID)
    if not token:
        return []

    request = urllib.request.Request(
        V2_DISCOVER_URL, headers={"Authorization": f"Bearer {token}"}
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        print(f"  WARNING: failed to call discover endpoint: {exc}")
        return []

    # V2 returns a bare array; V1 (legacy) returns a wrapped { mcpServers: [...] }.
    servers = payload if isinstance(payload, list) else payload.get("mcpServers", [])
    if not servers:
        print("  No servers returned from discover endpoint.")
        return []

    app_ids: list[str] = []
    for server in servers:
        audience = str(server.get("audience", ""))
        if server.get("scope") == V2_SCOPE_VALUE and _GUID_PREFIX.match(audience):
            if audience not in app_ids:
                app_ids.append(audience)

    print(f"  Found {len(app_ids)} V2 AppId(s) from discover endpoint.\n")
    return app_ids


def _service_principal_exists(app_id: str) -> str:
    """Return the existing Service Principal id for ``app_id`` (empty if missing)."""
    return _az(
        "ad", "sp", "list",
        "--filter", f"appId eq '{app_id}'",
        "--query", "[0].id", "-o", "tsv",
    )


def _register_service_principal_if_missing(app_id: str, label: str) -> None:
    """Create the Service Principal for ``app_id`` unless it already exists."""
    print(f"\n  [{label}] AppId: {app_id}")

    existing = _service_principal_exists(app_id)
    if existing:
        print(f"  Already exists (SP ID: {existing})")
        return

    sp_id = _az(
        "ad", "sp", "create", "--id", app_id, "--query", "id", "-o", "tsv"
    )
    print(f"  Created (SP ID: {sp_id})")


def _resolve_v2_app_ids(mode: str, explicit: list[str]) -> list[str]:
    """Determine the V2 AppIds to provision for the requested mode."""
    if mode == "v1":
        return []

    if explicit:
        print("Using explicit V2 AppIds provided via --v2-app-ids.\n")
        return list(dict.fromkeys(explicit))

    live = _discover_v2_app_ids()
    # Always union live results with the hardcoded fallback so servers absent
    # from the discover response (e.g. mcp_MeServer) are still provisioned.
    resolved = list(dict.fromkeys([*live, *V2_FALLBACK_APP_IDS]))
    print(f"  Total V2 AppIds to provision (live + fallback): {len(resolved)}\n")
    return resolved


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Create Service Principals for Agent 365 MCP servers (admin only)."
        )
    )
    parser.add_argument(
        "--mode",
        choices=["v1", "v2", "all"],
        default="all",
        type=str.lower,
        help=(
            "v1: shared ATG SP only; v2: per-server SPs only; "
            "all: both (default, recommended during migration)."
        ),
    )
    parser.add_argument(
        "--v2-app-ids",
        nargs="*",
        default=[],
        metavar="APPID",
        help="Explicit V2 per-server AppIds. Bypasses the live discover endpoint.",
    )
    args = parser.parse_args()

    print("=" * 64)
    print("Service Principal Creation for Agent 365 MCP Servers (Admin Only)")
    print(f"  Mode: {args.mode}")
    print("=" * 64)
    print("\nWARNING: this requires admin permissions!")
    print("WARNING: safe to re-run — existing Service Principals are skipped.\n")

    resolved_v2 = _resolve_v2_app_ids(args.mode, args.v2_app_ids)

    print("Provisioning Service Principals...")

    if args.mode in ("v1", "all"):
        _register_service_principal_if_missing(V1_APP_ID, "V1 Shared ATG")

    if args.mode in ("v2", "all"):
        if resolved_v2:
            for app_id in resolved_v2:
                _register_service_principal_if_missing(app_id, "V2 Per-Server")
        elif args.mode == "all":
            print("\n  V2 provisioning skipped — no V2 AppIds available.")

    print("\n" + "=" * 64)
    print("Setup Complete!")
    print("=" * 64)


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        message = str(exc)
        print(f"\nERROR: {message}", file=sys.stderr)
        if "Insufficient privileges" in message or "Authorization" in message:
            print(
                "\nThis usually means you lack admin permissions. Required:\n"
                "  - Application.ReadWrite.All, or\n"
                "  - Global Administrator / Application Administrator role.\n"
                "Ask your Microsoft Entra ID administrator to run this script.",
                file=sys.stderr,
            )
        sys.exit(1)
