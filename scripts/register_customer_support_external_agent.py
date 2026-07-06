"""Register the **Customer Support Agent** in Foundry as an *external agent*.

The customer support agent runs outside Foundry (as an Azure Container App) and
emits OpenTelemetry GenAI spans to Application Insights (see
``setup_observability`` in ``src/customer_support_agent/customer_support_agent.py``).
Registering it as an external agent wires the runtime's emitted
``gen_ai.agent.id`` to a Foundry agent so the spans light up in the project's
trace view (Portal → Project → Agents → customer-support-agent → Traces).

External agents are in **preview**: the client is constructed with
``allow_preview=True`` (which adds the ``Foundry-Features: ExternalAgents=V1Preview``
header required by create/update requests).

RBAC handled here (best-effort, idempotent):
  * the agent's user-assigned **managed identity** gets **Monitoring Metrics
    Publisher** so its telemetry export authenticates to Azure Monitor (also
    granted at deploy time; re-asserted here for completeness); and
  * the **registering principal** (the signed-in user) is granted the Foundry
    project management role (``Azure AI Project Manager`` / ``Foundry Project
    Manager``) so ``create_version`` is permitted. If the assignment cannot be
    made (insufficient rights), a clear message is printed and registration is
    still attempted.

Prerequisites:
  * ``az login`` as a principal allowed to create agent versions in the project
    (and, for the RBAC step, to create role assignments).
  * The customer support agent Container App is deployed and emitting telemetry.

Usage::

    python -m scripts.register_customer_support_external_agent

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT   Foundry project endpoint (required).
  CUSTOMER_SUPPORT_AGENT_ID   stable agent id; must equal the runtime's
                              gen_ai.agent.id (default: customer-support-agent).
  AZURE_RESOURCE_GROUP        resource group (for RBAC resolution; optional).
  AZURE_IDENTITY_NAME         the agent's user-assigned managed identity
                              (for the Monitoring Metrics Publisher grant; optional).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
load_dotenv(dotenv_path=_REPO_ROOT / ".env", override=True)
load_dotenv(override=False)

# Built-in role definition id — Monitoring Metrics Publisher.
_MONITORING_METRICS_PUBLISHER = "3913510d-42f4-4e42-8a64-420c390055eb"
# Foundry project management role display names (renamed; either may resolve).
_PROJECT_MANAGER_ROLE_NAMES = ("Azure AI Project Manager", "Foundry Project Manager")

AGENT_ID = os.getenv("CUSTOMER_SUPPORT_AGENT_ID", "customer-support-agent")


def _az(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["az", *args], check=check, capture_output=True, text=True)


def _resolve_ai_account_scope() -> str:
    """Best-effort resolve the Azure AI (Cognitive Services) account resource id."""
    rg = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    if not rg:
        return ""
    try:
        return _az(
            "cognitiveservices", "account", "list", "-g", rg,
            "--query", "[?kind=='AIServices'].id | [0]", "-o", "tsv",
        ).stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _grant_role(assignee_object_id: str, assignee_type: str, role: str,
                scope: str) -> bool:
    """Create a role assignment (idempotent, best-effort). Returns success."""
    if not (assignee_object_id and scope):
        return False
    try:
        _az(
            "role", "assignment", "create",
            "--assignee-object-id", assignee_object_id,
            "--assignee-principal-type", assignee_type,
            "--role", role, "--scope", scope,
        )
        print(f"  granted '{role}' on {scope}")
        return True
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "")
        if "RoleAssignmentExists" in stderr:
            print(f"  '{role}' already assigned on {scope}")
            return True
        print(f"  WARN: could not grant '{role}': {stderr.strip() or exc.stdout.strip()}")
        return False


def _assign_rbac() -> None:
    """Grant the RBAC required for telemetry export and registration."""
    print("==> Ensuring RBAC assignments")
    account_scope = _resolve_ai_account_scope()

    # 1) Monitoring Metrics Publisher for the agent's managed identity.
    rg = os.getenv("AZURE_RESOURCE_GROUP", "").strip()
    identity_name = os.getenv("AZURE_IDENTITY_NAME", "").strip()
    if rg and identity_name:
        try:
            mi_principal = _az(
                "identity", "show", "-g", rg, "-n", identity_name,
                "--query", "principalId", "-o", "tsv",
            ).stdout.strip()
            rg_scope = _az("group", "show", "-n", rg, "--query", "id", "-o", "tsv").stdout.strip()
            _grant_role(mi_principal, "ServicePrincipal",
                        _MONITORING_METRICS_PUBLISHER, rg_scope)
        except subprocess.CalledProcessError as exc:
            print(f"  WARN: could not resolve the managed identity: {(exc.stderr or '').strip()}")
    else:
        print("  (skipping Monitoring Metrics Publisher — AZURE_RESOURCE_GROUP / "
              "AZURE_IDENTITY_NAME not set; it is also granted at deploy time)")

    # 2) Project management role for the signed-in principal (registration rights).
    if account_scope:
        try:
            me = _az("ad", "signed-in-user", "show", "--query", "id", "-o", "tsv").stdout.strip()
        except subprocess.CalledProcessError:
            me = ""
        if me:
            granted = any(
                _grant_role(me, "User", role, account_scope)
                for role in _PROJECT_MANAGER_ROLE_NAMES
            )
            if not granted:
                print("  NOTE: could not assign the project management role — ensure "
                      "you have 'Azure AI Project Manager' (or 'Foundry Project "
                      "Manager') on the project before registering.")
    else:
        print("  (skipping project-role grant — could not resolve the AI account scope; "
              "ensure you hold 'Azure AI Project Manager' on the project)")


def register() -> None:
    from azure.ai.projects import AIProjectClient
    from azure.ai.projects.models import ExternalAgentDefinition
    from azure.identity import DefaultAzureCredential

    project_endpoint = os.environ["AZURE_AI_PROJECT_ENDPOINT"]

    # allow_preview=True adds the required 'Foundry-Features: ExternalAgents=V1Preview'
    # header for the preview external-agents surface.
    client = AIProjectClient(
        endpoint=project_endpoint,
        credential=DefaultAzureCredential(),
        allow_preview=True,
    )

    print(f"==> Registering external agent '{AGENT_ID}' (otel_agent_id={AGENT_ID})")
    agent = client.agents.create_version(
        agent_name=AGENT_ID,
        description="Customer Support Agent (Bank South) hosted outside Foundry "
                    "as an Azure Container App; emits GenAI telemetry to App Insights.",
        definition=ExternalAgentDefinition(otel_agent_id=AGENT_ID),
    )
    print(f"  Registered: {agent.name} (version {agent.version})")
    print(f"  otel_agent_id: {agent.definition.otel_agent_id}")
    print("\nOpen the Foundry portal → Project → Agents → "
          f"{agent.name} → Traces to see spans from the running agent.")


def main() -> None:
    _assign_rbac()
    register()


if __name__ == "__main__":
    main()
