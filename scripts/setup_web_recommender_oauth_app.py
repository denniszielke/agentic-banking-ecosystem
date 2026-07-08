"""Set up the Entra app registration for the **Web Recommender Agent** web app.

Creates (or updates) the app registration that backs the AG-UI web frontend:

  * Configured as a **Single-Page App** (implicit+code flow) AND a **Web**
    platform so MSAL.js can acquire tokens in the browser.
  * Delegated API permissions:
    - ``Azure AI Services``  — ``user_impersonation`` (scope for Foundry/OBO)
    - ``Power BI Service``  — ``Dataset.Read.All`` (Fabric DataAgent via OBO)
  * A client secret so the backend can perform the OBO token exchange
    (user token → Foundry-scoped token).

Usage::

    python -m scripts.setup_web_recommender_oauth_app

    # supply the Container App FQDN to add it as a redirect URI
    python -m scripts.setup_web_recommender_oauth_app --fqdn my-app.azurecontainerapps.io

Environment variables:
  AZURE_TENANT_ID                 tenant id (auto-resolved from az account if unset).
  WEB_RECOMMENDER_APP_REG_NAME    display name (default: web-recommender-agent).
  WEB_RECOMMENDER_CLIENT_ID       existing app id to update instead of create.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

from scripts._cli import normalize

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

_APP_NAME = os.getenv("WEB_RECOMMENDER_APP_REG_NAME", "web-recommender-agent")

# Well-known app IDs for permission grants.
_AZURE_AI_APP_ID = "7c092573-c6f0-4b87-9a5c-2d6f8e3f8a1b"   # Azure AI Services (cognitiveservices)
_POWER_BI_APP_ID = "00000009-0000-0000-c000-000000000000"    # Power BI Service
_GRAPH_APP_ID    = "00000003-0000-0000-c000-000000000000"    # Microsoft Graph

# Default redirect URIs (local dev) - no trailing slash, must match window.location.origin.
_DEFAULT_REDIRECT_URIS = [
    "http://localhost:8092",
]


def _az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(normalize(["az", *args]), check=False, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(
            f"az {' '.join(args)} failed ({result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    return result


def _az_json(*args: str) -> object:
    result = _az(*args)
    return json.loads(result.stdout.strip()) if result.stdout.strip() else None


def _resolve_tenant() -> str:
    tenant = os.getenv("AZURE_TENANT_ID", "").strip()
    if tenant:
        return tenant
    data = _az_json("account", "show", "--query", "tenantId", "-o", "json")
    return str(data).strip('"')


def _ensure_app_registration(tenant_id: str) -> tuple[str, str]:
    """Create or retrieve the app registration. Returns (app_id, object_id)."""
    existing_id = os.getenv("WEB_RECOMMENDER_CLIENT_ID", "").strip()
    if existing_id:
        print(f"==> Using existing app registration: {existing_id}")
        obj = _az_json("ad", "app", "show", "--id", existing_id, "--query", "{id:id,appId:appId}")
        return str(obj["appId"]), str(obj["id"])

    # Check if it already exists by display name.
    existing = _az_json(
        "ad", "app", "list",
        "--display-name", _APP_NAME,
        "--query", "[0].{id:id,appId:appId}",
        "-o", "json",
    )
    if existing and existing.get("appId"):
        print(f"==> Found existing app registration '{_APP_NAME}': {existing['appId']}")
        return str(existing["appId"]), str(existing["id"])

    # Create new registration.
    print(f"==> Creating app registration '{_APP_NAME}'")
    app = _az_json(
        "ad", "app", "create",
        "--display-name", _APP_NAME,
        "--sign-in-audience", "AzureADMyOrg",
        "--query", "{id:id,appId:appId}",
    )
    print(f"    App ID : {app['appId']}")
    print(f"    Obj ID : {app['id']}")
    return str(app["appId"]), str(app["id"])


def _configure_platforms(app_id: str, obj_id: str, extra_redirect_uris: list[str]) -> None:
    """Configure SPA redirect URIs via Microsoft Graph PATCH.

    Only the SPA platform is configured (not Web) since MSAL.js uses the
    authorization code flow with PKCE in the browser. The redirectUri in
    MSAL is set to ``window.location.origin`` which has no trailing slash,
    so URIs are registered without trailing slashes.
    """
    uris = list(dict.fromkeys(_DEFAULT_REDIRECT_URIS + extra_redirect_uris))
    print(f"==> Configuring SPA redirect URIs: {uris}")
    body = json.dumps({
        "spa": {"redirectUris": uris},
    })
    _az(
        "rest", "--method", "PATCH",
        "--uri", f"https://graph.microsoft.com/v1.0/applications/{obj_id}",
        "--headers", "Content-Type=application/json",
        "--body", body,
    )
    print("  SPA redirect URIs configured.")


def _expose_scope(obj_id: str, app_id: str) -> None:
    """Expose a user_impersonation delegated scope on the app registration.

    MSAL acquires a token for ``api://<clientId>/user_impersonation``.
    The backend exchanges it for a ``cognitiveservices.azure.com`` token via OBO.
    """
    scope_id = "a1b2c3d4-0000-0000-0000-000000000001"  # stable GUID for this scope
    print("==> Exposing user_impersonation scope")
    # Set identifierUri first (required for exposing scopes).
    _az(
        "ad", "app", "update",
        "--id", app_id,
        "--identifier-uris", f"api://{app_id}",
        check=False,
    )
    body = json.dumps({
        "api": {
            "oauth2PermissionScopes": [
                {
                    "id": scope_id,
                    "type": "User",
                    "value": "user_impersonation",
                    "adminConsentDisplayName": "Access Web Recommender Agent on behalf of user",
                    "adminConsentDescription": "Allows the web app to call Foundry APIs as the signed-in user.",
                    "userConsentDisplayName": "Zugriff als Sie selbst",
                    "userConsentDescription": "Die Web-App darf Foundry-APIs in Ihrem Namen aufrufen.",
                    "isEnabled": True,
                }
            ]
        }
    })
    _az(
        "rest", "--method", "PATCH",
        "--uri", f"https://graph.microsoft.com/v1.0/applications/{obj_id}",
        "--headers", "Content-Type=application/json",
        "--body", body,
    )
    print(f"  Scope api://{app_id}/user_impersonation exposed.")


def _grant_delegated_permissions(app_id: str) -> None:
    """Add delegated API permissions (Power BI for Fabric DataAgent)."""
    print("==> Granting delegated API permissions")

    # Power BI Service — Dataset.Read.All (needed for Fabric DataAgent OBO).
    pbi_sp = _az_json(
        "ad", "sp", "list",
        "--filter", f"appId eq '{_POWER_BI_APP_ID}'",
        "--query", "[0].{appId:appId}",
    )
    if pbi_sp and pbi_sp.get("appId"):
        oauth2perms = _az_json(
            "ad", "sp", "show",
            "--id", _POWER_BI_APP_ID,
            "--query", "oauth2PermissionScopes[?value=='Dataset.Read.All'].id",
        )
        scope_id = (oauth2perms or [None])[0]
        if scope_id:
            _az(
                "ad", "app", "permission", "add",
                "--id", app_id,
                "--api", _POWER_BI_APP_ID,
                "--api-permissions", f"{scope_id}=Scope",
                check=False,
            )
            print(f"  Added Power BI Service / Dataset.Read.All ({scope_id})")
    else:
        print(f"  WARN: Power BI Service SP ({_POWER_BI_APP_ID}) not found in tenant - skip")

    # Grant admin consent.
    print("==> Granting admin consent")
    result = _az("ad", "app", "permission", "admin-consent", "--id", app_id, check=False)
    if result.returncode == 0:
        print("  Admin consent granted.")
    else:
        print(f"  WARN: admin consent failed (may need Global Admin): {result.stderr.strip()}")


def _create_client_secret(app_id: str) -> str:
    """Create a new client secret and return its value."""
    print("==> Creating client secret")
    secret = _az_json(
        "ad", "app", "credential", "reset",
        "--id", app_id,
        "--display-name", "web-recommender-backend",
        "--years", "1",
        "--query", "password",
    )
    value = str(secret).strip('"')
    print("  Client secret created (1-year expiry).")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fqdn", help="Container App FQDN (e.g. my-app.azurecontainerapps.io)")
    parser.add_argument("--no-secret", action="store_true", help="Skip client secret creation.")
    args = parser.parse_args(argv)

    tenant_id = _resolve_tenant()
    print(f"Tenant: {tenant_id}")

    extra_uris: list[str] = []
    if args.fqdn:
        fqdn = args.fqdn.rstrip("/")
        if not fqdn.startswith("https://"):
            fqdn = f"https://{fqdn}"
        # No trailing slash — must match window.location.origin in MSAL.
        extra_uris = [fqdn]

    app_id, obj_id = _ensure_app_registration(tenant_id)
    _configure_platforms(app_id, obj_id, extra_uris)
    _expose_scope(obj_id, app_id)
    _grant_delegated_permissions(app_id)

    client_secret = ""
    if not args.no_secret:
        client_secret = _create_client_secret(app_id)

    print(
        f"""
=== Web Recommender OAuth App ===
  TENANT_ID                        = {tenant_id}
  WEB_RECOMMENDER_CLIENT_ID        = {app_id}
  WEB_RECOMMENDER_CLIENT_SECRET    = {client_secret or "<use --no-secret or existing>"}

Add these to .env and redeploy:
  WEB_RECOMMENDER_CLIENT_ID={app_id}
  WEB_RECOMMENDER_CLIENT_SECRET=<secret above>
  WEB_RECOMMENDER_TENANT_ID={tenant_id}

MSAL scopes to request in the browser:
  api://{app_id}/user_impersonation
  https://analysis.windows.net/powerbi/api/Dataset.Read.All
"""
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
