"""Set up a **custom Entra OAuth app** for WorkIQ identity passthrough (Option B).

Foundry authenticates a hosted agent to an Agent 365 WorkIQ MCP server with
**OAuth identity passthrough**. A plain "custom keys" bearer token does *not*
work: Foundry refuses to forward a Microsoft-audience token to the WorkIQ
endpoint ("Cannot pass Microsoft token to untrusted MCP endpoint"). Instead you
must bring **your own** Entra app registration and configure a custom-OAuth
Foundry connection against it.

This script automates the scriptable half of that setup:

  1. Resolves the delegated scope id for ``WORKIQ_SCOPE`` on the Agent 365 Tools
     app (``ea9ffc3e-8a23-4a7d-836d-234d7c7565c1``).
  2. Creates (or reuses) an Entra app registration + service principal.
  3. Adds the WorkIQ delegated permission and grants tenant admin consent.
  4. Creates a client secret.
  5. Prints the exact field values to paste into the Foundry **Custom > MCP >
     OAuth Identity Passthrough** connection dialog.

The one step that cannot be scripted is the connection's redirect-URL handshake:
Foundry issues a redirect URL only *after* you create the connection, and you
must add that URL back to this app. The script prints where to do that.

Requires: tenant admin (to grant admin consent) and the Azure CLI (``az login``).

Environment variables:
  WORKIQ_OAUTH_APP_NAME   App registration display name (default: banking-workiq-oauth).
  WORKIQ_SCOPE            Delegated scope value to request (default:
                          McpServers.Calendar.All). Must be a scope exposed by
                          the Agent 365 Tools app — there is no
                          "McpServers.WorkIQ.All"; pick the specific capability
                          (Calendar, Mail, OneDriveSharepoint, Me, Teams, Word …).
  WORKIQ_TENANT_ID       Entra tenant id (falls back to AZURE_TENANT_ID, then az).
"""

from __future__ import annotations

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

# Agent 365 Tools ("Agent Tools") — the shared V1 audience that exposes the
# delegated McpServers.*.All scopes for the WorkIQ MCP servers.
ATG_APP_ID = "ea9ffc3e-8a23-4a7d-836d-234d7c7565c1"

APP_NAME = os.getenv("WORKIQ_OAUTH_APP_NAME", "banking-workiq-oauth")
WORKIQ_SCOPE = os.getenv("WORKIQ_SCOPE", "McpServers.Calendar.All").strip()


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


def _resolve_tenant_id() -> str:
    tenant = (
        os.getenv("WORKIQ_TENANT_ID", "").strip()
        or os.getenv("AZURE_TENANT_ID", "").strip()
    )
    if tenant:
        return tenant
    return _az("account", "show", "--query", "tenantId", "-o", "tsv")


def _resolve_scope_id(scope_value: str) -> str:
    """Find the delegated permission (scope) id for ``scope_value`` on ATG."""
    scopes_json = _az(
        "ad", "sp", "show", "--id", ATG_APP_ID,
        "--query", "oauth2PermissionScopes", "-o", "json",
    )
    scopes = json.loads(scopes_json or "[]")
    for scope in scopes:
        if scope.get("value") == scope_value:
            return scope["id"]
    available = ", ".join(sorted(s["value"] for s in scopes if s.get("value")))
    raise RuntimeError(
        f"Scope '{scope_value}' is not exposed by the Agent 365 Tools app. "
        f"Set WORKIQ_SCOPE to one of: {available}"
    )


def _ensure_app(display_name: str) -> str:
    """Create the app registration if missing; return its appId."""
    existing = _az(
        "ad", "app", "list", "--display-name", display_name,
        "--query", "[0].appId", "-o", "tsv",
    )
    if existing:
        print(f"==> Reusing app registration '{display_name}' (appId {existing})")
        return existing
    app_id = _az(
        "ad", "app", "create", "--display-name", display_name,
        "--sign-in-audience", "AzureADMyOrg",
        "--query", "appId", "-o", "tsv",
    )
    print(f"==> Created app registration '{display_name}' (appId {app_id})")
    return app_id


def _ensure_service_principal(app_id: str) -> None:
    existing = _az(
        "ad", "sp", "list", "--filter", f"appId eq '{app_id}'",
        "--query", "[0].id", "-o", "tsv",
    )
    if existing:
        return
    _az("ad", "sp", "create", "--id", app_id)
    print("==> Created service principal for the app.")


def _add_permission(app_id: str, scope_id: str) -> None:
    _az(
        "ad", "app", "permission", "add",
        "--id", app_id,
        "--api", ATG_APP_ID,
        "--api-permissions", f"{scope_id}=Scope",
    )
    print(f"==> Added delegated permission {WORKIQ_SCOPE} on Agent 365 Tools.")


def _admin_consent(app_id: str) -> None:
    try:
        _az("ad", "app", "permission", "admin-consent", "--id", app_id)
        print("==> Granted tenant admin consent.")
    except RuntimeError as exc:
        print(
            "WARNING: admin consent failed — grant it manually in the Entra "
            "admin center (API permissions > Grant admin consent).\n"
            f"  Detail: {exc}"
        )


def _create_secret(app_id: str) -> str:
    return _az(
        "ad", "app", "credential", "reset",
        "--id", app_id, "--append", "--display-name", "foundry-workiq-oauth",
        "--query", "password", "-o", "tsv",
    )


def main() -> None:
    tenant_id = _resolve_tenant_id()
    scope_id = _resolve_scope_id(WORKIQ_SCOPE)
    app_id = _ensure_app(APP_NAME)
    _ensure_service_principal(app_id)
    _add_permission(app_id, scope_id)
    _admin_consent(app_id)
    secret = _create_secret(app_id)

    authority = f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0"
    scopes = f"{ATG_APP_ID}/{WORKIQ_SCOPE} offline_access"

    print("\n" + "=" * 72)
    print("Custom OAuth app ready. Create the Foundry connection with these values")
    print("(Foundry portal > your project > Tools > Add tool > Custom > MCP >")
    print(" OAuth Identity Passthrough > Custom OAuth):")
    print("=" * 72)
    print(f"  Connection name : workiq-connection")
    print(f"  MCP server URL  : (the tenant-scoped WorkIQ URL you registered)")
    print(f"  Client ID       : {app_id}")
    print(f"  Client secret   : {secret}")
    print(f"  Auth URL        : {authority}/authorize")
    print(f"  Token URL       : {authority}/token")
    print(f"  Refresh URL     : {authority}/token")
    print(f"  Scopes          : {scopes}")
    print("=" * 72)
    print(
        "After you save the connection, Foundry shows a redirect URL. Add it to\n"
        f"this app (Entra admin center > App registrations > {APP_NAME} >\n"
        "Authentication > Add a platform > Web > Redirect URIs), then finish the\n"
        "connection. Finally re-register the toolbox against the connection:\n"
        "  WORKIQ_CONNECTION_NAME=workiq-connection python -m scripts.register_workiq_toolbox\n"
    )
    print(
        "NOTE: the client secret above is shown once. Store it securely; it is\n"
        "only needed to configure the Foundry connection."
    )


if __name__ == "__main__":
    try:
        main()
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
