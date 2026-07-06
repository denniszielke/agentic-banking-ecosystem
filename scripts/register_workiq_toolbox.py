"""Register the **WorkIQ MCP server** as a Foundry toolbox.

Creates (or updates) a Foundry toolbox backed by the Microsoft Agent 365 WorkIQ
MCP server. This gives the ``employee_advisory_agent`` access to the signed-in
employee's calendar and documents (in their own user context) so it can find
internal material and schedule customer follow-ups.

Run this after ``azd up`` has provisioned the Foundry project and before
deploying the employee advisory agent that consumes WorkIQ.

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT   Foundry project endpoint (required).
  WORKIQ_TOOLBOX_NAME         Toolbox name (default: workiq-tools).
  WORKIQ_MCP_URL              Full WorkIQ MCP server URL. If set it is used
                              verbatim (advanced override); otherwise the URL is
                              built from the base host, tenant id and server name
                              below.
  WORKIQ_MCP_SERVER           WorkIQ MCP server name (default: mcp_CalendarTools).
  WORKIQ_SCOPE                Delegated scope the OAuth connection requests
                              (default: McpServers.Calendar.All).
  WORKIQ_TENANT_ID            Entra tenant id used in the MCP URL path. Falls
                              back to AZURE_TENANT_ID, then to the signed-in
                              ``az account show`` tenant.
  WORKIQ_CONNECTION_ID        Foundry connection ID (or name) that provides the
                              OAuth identity-passthrough token for the WorkIQ MCP
                              server. See scripts/setup_workiq_oauth_app.py.
  WORKIQ_CONNECTION_NAME      Foundry connection name to reference (default:
                              workiq-connection) when WORKIQ_CONNECTION_ID is
                              unset. If neither resolves to an existing
                              connection the toolbox is registered without one
                              (calls will fail auth until a connection is set).
  WORKIQ_DOCS_ENABLED         Also expose the WorkIQ documents server
                              (OneDrive + SharePoint) as a second tool in the
                              same toolbox (default: false).
  WORKIQ_DOCS_SERVER          Documents WorkIQ server name
                              (default: mcp_ODSPRemoteServer).
  WORKIQ_DOCS_SCOPE           Delegated scope the documents OAuth connection
                              requests (default: McpServers.OneDriveSharepoint.All).
  WORKIQ_DOCS_CONNECTION_NAME Foundry OAuth connection for the documents server
                              (default: workiq-documents-connection).
"""

from __future__ import annotations

import os
import subprocess
from scripts._cli import normalize

from azure.ai.projects.models import MCPToolboxTool

from scripts.agent_deploy_helpers import get_client, get_env

# Microsoft Agent 365 WorkIQ MCP server (from the A365 MCP server catalog).
# The Agent 365 tooling gateway requires the tenant id in the URL path:
#   https://agent365.svc.cloud.microsoft/agents/tenants/{tenantId}/servers/{server}
# Omitting the /tenants/{tenantId}/ segment makes the remote server reject
# tools/list with HTTP 400 EndpointInvalid / TenantIdInvalid.
_WORKIQ_HOST = "https://agent365.svc.cloud.microsoft"
# NB: there is no "mcp_WorkIQTools" server / "McpServers.WorkIQ.All" scope — the
# Agent 365 Tools app exposes granular capabilities. Default to Calendar (the
# employee agent schedules follow-ups); override for Mail/OneDriveSharepoint/etc.
_DEFAULT_WORKIQ_SERVER = "mcp_CalendarTools"
_WORKIQ_SCOPE = os.getenv("WORKIQ_SCOPE", "McpServers.Calendar.All").strip()

TOOLBOX_NAME = os.getenv("WORKIQ_TOOLBOX_NAME", "workiq-tools")
CONNECTION_NAME = os.getenv("WORKIQ_CONNECTION_NAME", "workiq-connection").strip()

# Optional second WorkIQ capability: documents (OneDrive + SharePoint). When
# enabled the toolbox gains a second MCP server (mcp_ODSPRemoteServer) alongside
# calendar. It needs its own Foundry OAuth identity-passthrough connection whose
# scope is McpServers.OneDriveSharepoint.All. Disabled by default to preserve the
# calendar-only behaviour.
_DOCS_ENABLED = os.getenv("WORKIQ_DOCS_ENABLED", "false").strip().lower() in {
    "1", "true", "yes", "on",
}
_DOCS_SERVER = os.getenv("WORKIQ_DOCS_SERVER", "mcp_ODSPRemoteServer").strip()
_DOCS_SCOPE = os.getenv("WORKIQ_DOCS_SCOPE", "McpServers.OneDriveSharepoint.All").strip()
_DOCS_CONNECTION_NAME = os.getenv(
    "WORKIQ_DOCS_CONNECTION_NAME", "workiq-documents-connection"
).strip()


def _resolve_tenant_id() -> str:
    """Resolve the Entra tenant id for the WorkIQ MCP URL path."""
    tenant = (
        os.getenv("WORKIQ_TENANT_ID", "").strip()
        or os.getenv("AZURE_TENANT_ID", "").strip()
    )
    if tenant:
        return tenant
    result = subprocess.run(
        normalize(["az", "account", "show", "--query", "tenantId", "-o", "tsv"]),
        check=False,
        capture_output=True,
        text=True,
    )
    tenant = result.stdout.strip()
    if not tenant:
        raise RuntimeError(
            "Could not resolve the Entra tenant id. Set WORKIQ_TENANT_ID (or "
            "AZURE_TENANT_ID) in ./.env, or sign in with 'az login'."
        )
    return tenant


def _resolve_workiq_url(server: str | None = None) -> str:
    """Build the tenant-scoped WorkIQ MCP URL for a server.

    For the primary (calendar) server ``WORKIQ_MCP_URL`` may override the URL
    verbatim. For additional servers (e.g. documents) the URL is always built
    from the base host, tenant id and the given server name.
    """
    if server is None:
        override = os.getenv("WORKIQ_MCP_URL", "").strip()
        if override:
            return override
        server = os.getenv("WORKIQ_MCP_SERVER", "").strip() or _DEFAULT_WORKIQ_SERVER
    tenant = _resolve_tenant_id()
    return f"{_WORKIQ_HOST}/agents/tenants/{tenant}/servers/{server}"


def _resolve_connection_id(client, explicit_id: str = "", name: str = "") -> str:
    """Resolve the OAuth connection id to reference from an MCP tool.

    Prefers ``explicit_id`` (falling back to ``WORKIQ_CONNECTION_ID`` for the
    primary server). Otherwise looks up the connection by ``name`` (created via
    the Foundry OAuth identity-passthrough setup) and returns its id. Returns ""
    when no connection is configured yet.
    """
    explicit = (explicit_id or os.getenv("WORKIQ_CONNECTION_ID", "")).strip()
    if explicit:
        return explicit
    if not name:
        return ""
    try:
        connection = client.connections.get(name=name)
    except Exception:  # noqa: BLE001 — connection simply not created yet
        return ""
    return getattr(connection, "id", None) or getattr(connection, "name", "") or ""


def _build_tool(client, *, label, server, scope, connection_name,
                use_env_connection_id, description):
    """Build one MCPToolboxTool for a WorkIQ server plus its resolved url/conn."""
    url = _resolve_workiq_url(server)
    explicit = os.getenv("WORKIQ_CONNECTION_ID", "") if use_env_connection_id else ""
    connection_id = _resolve_connection_id(client, explicit_id=explicit, name=connection_name)
    kwargs: dict = {
        "server_label": label,
        "server_url": url,
        "description": description,
        "require_approval": "never",
    }
    if connection_id:
        kwargs["project_connection_id"] = connection_id
    return MCPToolboxTool(**kwargs), url, connection_id


def deploy() -> None:
    if not os.getenv("AZURE_AI_PROJECT_ENDPOINT"):
        print("Skipping toolbox registration: AZURE_AI_PROJECT_ENDPOINT is required.")
        return

    client = get_client()

    calendar_tool, calendar_url, calendar_conn = _build_tool(
        client,
        label="workiq",
        server=None,
        scope=_WORKIQ_SCOPE,
        connection_name=CONNECTION_NAME,
        use_env_connection_id=True,
        description=(
            "Microsoft Agent 365 WorkIQ MCP server (calendar). Provides access to "
            "the signed-in user's calendar in their own user context. "
            f"Required OAuth scope: {_WORKIQ_SCOPE}."
        ),
    )
    tools = [calendar_tool]
    scopes = [_WORKIQ_SCOPE]

    docs_url = docs_conn = ""
    if _DOCS_ENABLED:
        docs_tool, docs_url, docs_conn = _build_tool(
            client,
            label="workiq-documents",
            server=_DOCS_SERVER,
            scope=_DOCS_SCOPE,
            connection_name=_DOCS_CONNECTION_NAME,
            use_env_connection_id=False,
            description=(
                "Microsoft Agent 365 WorkIQ MCP server (documents). Provides access "
                "to the signed-in user's OneDrive and SharePoint documents in their "
                f"own user context. Required OAuth scope: {_DOCS_SCOPE}."
            ),
        )
        tools.append(docs_tool)
        scopes.append(_DOCS_SCOPE)

    version = client.toolboxes.create_version(
        name=TOOLBOX_NAME,
        tools=tools,
        description=(
            "WorkIQ toolbox backed by the Microsoft Agent 365 WorkIQ MCP servers. "
            "Exposes calendar" + (" and document" if _DOCS_ENABLED else "")
            + " capabilities to the employee advisory agent."
        ),
        metadata={"source": "agent365-mcp-workiq", "scope": " ".join(scopes)},
    )
    client.toolboxes.update(name=TOOLBOX_NAME, default_version=version.version)

    project_endpoint = get_env("AZURE_AI_PROJECT_ENDPOINT")
    consumer_endpoint = (
        f"{project_endpoint.rstrip('/')}/toolboxes/{TOOLBOX_NAME}/mcp?api-version=v1"
    )
    print(f"Toolbox '{TOOLBOX_NAME}' version '{version.version}' created.")
    print(f"  WorkIQ calendar server: {calendar_url}")
    if calendar_conn:
        print(f"  Calendar OAuth connection:  {calendar_conn}")
    else:
        print(
            "  Note: no calendar OAuth connection resolved. Create one with "
            "OAuth identity passthrough\n"
            "  (see scripts/setup_workiq_oauth_app.py), then re-run with "
            "WORKIQ_CONNECTION_NAME set.\n"
            "  Until then WorkIQ tool calls fail with 401 Unauthorized."
        )
    if _DOCS_ENABLED:
        print(f"  WorkIQ documents server: {docs_url}")
        print(
            "  Documents OAuth connection: "
            + (docs_conn or "(none yet — create it in the Foundry portal)")
        )
    print(f"  Consumer endpoint: {consumer_endpoint}")


if __name__ == "__main__":
    deploy()
