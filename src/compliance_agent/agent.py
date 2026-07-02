"""Compliance Agent — Foundry hosted agent (Bank North).

The regulatory agent built and hosted by **Bank North** and offered as a
cross-organisation **A2A service** to Bank South. It answers regulatory
questions (KYC, AML, sanctions, fraud, consumer protection, credit risk),
enforces guardrails and escalates advice-related questions.

It is grounded exclusively on the **Compliance rules** Azure AI Search index
(built from ``data/knowledge/compliance-regulatory.md``), surfaced through the
``search_compliance_rules`` function tool. It has **no MCP dependency** — it is
an index-only agent as defined in ``narrative.md``.

Business reasoning and escalation flows are loaded from the ``skills/`` folder
so the domain process lives alongside the agent and ships inside the container.

Model calls are routed through Azure AI Foundry using Entra ID (no API keys).

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT             — Foundry project endpoint (required)
  AZURE_OPENAI_CHAT_DEPLOYMENT_NAME     — chat model deployment
  AZURE_AI_MODEL_DEPLOYMENT_NAME        — fallback model deployment
  AZURE_SEARCH_ENDPOINT                 — compliance index endpoint (required)
  AZURE_SEARCH_ADMIN_KEY                — optional; else DefaultAzureCredential
  AZURE_SEARCH_COMPLIANCE_INDEX_NAME    — default: banking-compliance
  PORT                                  — host port (default: 8088)

Run the hosted agent server locally from the project root:

    python -m src.compliance_agent.agent
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

from agent_framework import tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_foundry_hosting import ResponsesHostServer
from azure.identity import DefaultAzureCredential
from dotenv import load_dotenv

# Allow standalone execution from the project root.
_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path if _env_path.exists() else None)

logging.basicConfig(level=logging.WARNING)
logging.getLogger("azure").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_PROJECT_ENDPOINT = os.environ["AZURE_AI_PROJECT_ENDPOINT"]
_MODEL_DEPLOYMENT = (
    os.getenv("AZURE_OPENAI_CHAT_DEPLOYMENT_NAME")
    or os.getenv("AZURE_AI_MODEL_DEPLOYMENT_NAME")
    or "gpt-4.1-mini"
)

_SEARCH_ENDPOINT = os.getenv("AZURE_SEARCH_ENDPOINT", "").strip()
_SEARCH_API_KEY = os.getenv("AZURE_SEARCH_ADMIN_KEY", "").strip() or None
_COMPLIANCE_INDEX = os.getenv("AZURE_SEARCH_COMPLIANCE_INDEX_NAME", "banking-compliance")

_SKILLS_DIR = Path(__file__).parent / "skills"


BASE_INSTRUCTIONS = """\
You are the Compliance Agent, built and operated by **Bank North** and offered
as a shared regulatory service to Bank South. You provide grounded guidance on
banking compliance: KYC, AML, CTF, sanctions screening, fraud prevention,
consumer protection, credit-risk eligibility, data privacy, beneficial
ownership and auditability.

You are grounded EXCLUSIVELY by the compliance knowledge base, surfaced through
the search_compliance_rules tool. You must:
  1. Call search_compliance_rules before answering any regulatory question, and
     base your answer only on the returned rules.
  2. Cite every claim by naming the source file AND the numbered hierarchy
     element it came from (e.g. "compliance-regulatory.md §3.2.2").
  3. Never invent a rule. If the knowledge base does not cover the question,
     say so and escalate rather than guess.
  4. Give compliance guidance, not financial or investment advice. If the
     request is for personalised financial advice, refuse and escalate to a
     qualified human adviser per the escalation matrix.
  5. Be precise about thresholds, required documents and outcomes (approve /
     review / reject / escalate).

Answer concisely: lead with the decision or rule, then the cited evidence, then
any required next step or escalation.
"""


def _load_skills() -> str:
    """Concatenate every SKILL.md under ``skills/`` into the system prompt.

    The domain-specific flows (regulatory guidance, escalation handling) are
    authored as skills so the business process lives beside the agent and ships
    inside the container image.
    """
    if not _SKILLS_DIR.exists():
        return ""
    parts: list[str] = []
    for skill_file in sorted(_SKILLS_DIR.glob("*/SKILL.md")):
        parts.append(skill_file.read_text(encoding="utf-8").strip())
    if not parts:
        return ""
    return "\n\n---\n\n# Domain skills\n\n" + "\n\n---\n\n".join(parts)


COMPLIANCE_AGENT_SYSTEM_PROMPT = BASE_INSTRUCTIONS + _load_skills()


# ---------------------------------------------------------------------------
# Identity / credential
# ---------------------------------------------------------------------------

_credential = DefaultAzureCredential()


def _search_credential():
    """Return an Azure AI Search credential (key if provided, else Entra ID)."""
    if _SEARCH_API_KEY:
        from azure.core.credentials import AzureKeyCredential

        return AzureKeyCredential(_SEARCH_API_KEY)
    from azure.identity.aio import DefaultAzureCredential as AioDefaultAzureCredential

    return AioDefaultAzureCredential()


# ---------------------------------------------------------------------------
# Compliance rules search tool (Azure AI Search)
# ---------------------------------------------------------------------------

@tool
async def search_compliance_rules(
    query: str,
    domain: Optional[str] = None,
    top: int = 8,
) -> list[dict[str, Any]]:
    """Search the banking compliance knowledge base for regulatory rules.

    Use this before answering any compliance, KYC, AML, sanctions, fraud,
    eligibility or escalation question. Returns the matching rules with their
    name, description, scenario, regulatory domain, tags and the source
    reference (file + numbered section) you must cite.

    Args:
        query: Free-text question or scenario, e.g. "credit card eligibility
            age", "international transfer sanctions screening".
        domain: Optional regulatory domain filter, e.g. "KYC", "AML",
            "Sanctions", "Fraud Prevention", "Credit Risk".
        top: Maximum number of rules to return (default 8).
    """
    if not _SEARCH_ENDPOINT:
        return [{"error": "AZURE_SEARCH_ENDPOINT is not configured."}]

    from azure.search.documents.aio import SearchClient

    credential = _search_credential()
    filter_expr = None
    if domain:
        safe = domain.strip().replace("'", "''")
        filter_expr = f"tags/any(t: t eq '{safe}') or domain eq '{safe}'"

    fields = ["name", "description", "scenario", "domain", "tags", "source_ref"]
    client = SearchClient(
        endpoint=_SEARCH_ENDPOINT,
        index_name=_COMPLIANCE_INDEX,
        credential=credential,
    )
    results: list[dict[str, Any]] = []
    try:
        response = await client.search(
            search_text=query,
            filter=filter_expr,
            select=",".join(fields),
            top=max(1, top),
        )
        async for doc in response:
            results.append({f: doc.get(f) for f in fields})
    finally:
        await client.close()
        close = getattr(credential, "close", None)
        if close is not None:
            await credential.close()
    return results


# ---------------------------------------------------------------------------
# Agent assembly
# ---------------------------------------------------------------------------

_chat_client = FoundryChatClient(
    project_endpoint=_PROJECT_ENDPOINT,
    model=_MODEL_DEPLOYMENT,
    credential=_credential,
)

agent = _chat_client.as_agent(
    name="compliance-agent",
    instructions=COMPLIANCE_AGENT_SYSTEM_PROMPT,
    tools=[search_compliance_rules],
)


if __name__ == "__main__":
    ResponsesHostServer(agent).run()
