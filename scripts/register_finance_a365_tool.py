"""Print the a365 CLI command to register the finance MCP server as a BYO tool.

Builds and outputs the ``a365 develop-mcp register-external-mcp-server`` command
from environment variables so it can be reviewed and run manually, or piped
directly to a shell. This registers the deployed ``finance-mcp-server`` Container
App (compound interest + present-value discounting) as an Agent 365 external MCP
tool.

Usage::

    # Print the command
    python -m scripts.register_finance_a365_tool

    # Print and execute immediately
    eval $(python -m scripts.register_finance_a365_tool)

Environment variables:
  FINANCE_MCP_URL          MCP endpoint URL of the deployed finance server.
                           If unset, derived from the ``finance-mcp-server``
                           Container App FQDN using AZURE_RESOURCE_GROUP.
  FINANCE_MCP_APP_NAME     Container App name (default: finance-mcp-server).
  AZURE_RESOURCE_GROUP     Resource group containing the Container App.
  FINANCE_MCP_SERVER_NAME  A365 server identifier -- must start with ``ext_``,
                           <= 20 chars (default: ext_finance).
  FINANCE_MCP_PUBLISHER    Publisher name in MOS package metadata
                           (default: Bank North / Bank South).
  FINANCE_MCP_DESCRIPTION  Server description in MOS package metadata.
  FINANCE_MCP_AUTH_TYPE    EntraOAuth | ExternalOAuth | APIKey | NoAuth
                           (default: NoAuth).
  FINANCE_MCP_TOOLS        Raw ``--tools`` value to advertise. If unset, the
                           tool names and descriptions are loaded from
                           register-external-mcp-server.json.
  A365_DRY_RUN             Set to ``true`` to append ``--dry-run``.
"""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from scripts.deploy_helpers import get_container_app_fqdn

_MANIFEST_PATH = (
    Path(__file__).resolve().parents[1]
    / "src" / "finance_mcp_server" / "register-external-mcp-server.json"
)


def _load_tools() -> str:
    """Return the ``--tools`` value, defaulting to the JSON manifest tools.

    Honours ``FINANCE_MCP_TOOLS`` as a verbatim override; otherwise reads the
    tool names *and descriptions* from register-external-mcp-server.json and
    renders them as a JSON array so the descriptions are advertised too.
    """
    override = os.getenv("FINANCE_MCP_TOOLS", "").strip()
    if override:
        return override
    manifest = json.loads(_MANIFEST_PATH.read_text(encoding="utf-8"))
    tools = [
        {"name": t["name"], "description": t.get("description", "")}
        for t in manifest.get("tools", [])
    ]
    return json.dumps(tools, ensure_ascii=False)


def _resolve_mcp_url() -> str:
    url = os.getenv("FINANCE_MCP_URL", "").strip()
    if url:
        return url
    resource_group = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    app_name = os.getenv("FINANCE_MCP_APP_NAME", "finance-mcp-server")
    if resource_group:
        try:
            fqdn = get_container_app_fqdn(resource_group, app_name)
        except (subprocess.CalledProcessError, FileNotFoundError):
            fqdn = ""
        if fqdn:
            return f"https://{fqdn}/mcp"
    return ""


def build_command(mcp_url: str) -> list[str]:
    cmd = [
        "a365", "develop-mcp", "register-external-mcp-server",
        "--server-name", os.getenv("FINANCE_MCP_SERVER_NAME", "ext_finance").strip(),
        "--server-url",  mcp_url,
        "--publisher",   os.getenv("FINANCE_MCP_PUBLISHER", "Bank North / Bank South").strip(),
        "--description", os.getenv(
            "FINANCE_MCP_DESCRIPTION",
            "Finance MCP server: compound-interest and present-value "
            "discounting tools.",
        ).strip(),
        "--auth-type",   os.getenv("FINANCE_MCP_AUTH_TYPE", "NoAuth").strip(),
        "--tools",       _load_tools(),
    ]
    if os.getenv("A365_DRY_RUN", "false").strip().lower() == "true":
        cmd.append("--dry-run")
    return cmd


def _shell_quote(s: str) -> str:
    """Shell-quote a value so embedded spaces, quotes and JSON stay intact."""
    return shlex.quote(s)


def deploy() -> None:
    mcp_url = _resolve_mcp_url()
    if not mcp_url:
        print(
            "Error: cannot resolve finance MCP URL.\n"
            "Set FINANCE_MCP_URL, or set AZURE_RESOURCE_GROUP so the URL can be\n"
            "derived from the finance-mcp-server Container App FQDN."
        )
        return

    cmd = build_command(mcp_url)

    # Render as a readable multi-line shell command.
    # Positional tokens (a365 / sub-commands) go on the first line;
    # each --flag value pair on its own continuation line.
    parts: list[str] = []
    i = 0
    while i < len(cmd):
        token = cmd[i]
        if token.startswith("--") and i + 1 < len(cmd) and not cmd[i + 1].startswith("--"):
            parts.append(f"{token} {_shell_quote(cmd[i + 1])}")
            i += 2
        else:
            parts.append(_shell_quote(token))
            i += 1

    print(" \\\n  ".join(parts))


if __name__ == "__main__":
    deploy()
