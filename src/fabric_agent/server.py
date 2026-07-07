"""AG-UI server for the Customer Support Agent.

Hosts the `agent-framework` customer support agent behind the AG-UI protocol
(Server-Sent Events) and serves a streaming single-page banking web UI from the
same container. This is the ``customer_app`` front end from ``narrative.md``:
the customer talks to the agent, and the agent mediates all data access through
the Fabric data agents — the web app never calls them directly.

The agent keeps three live sidebar panels in sync via AG-UI *shared state*:

  * Customer      — the signed-in customer's profile summary
  * Accounts      — the customer's product holdings and balances
  * Pending action — any human-in-the-loop action awaiting confirmation

State is pushed deterministically through the ``update_overview`` tool.

Endpoints:
  GET  /          — the chat web UI
  POST /agent     — the AG-UI protocol endpoint (SSE stream)
  GET  /healthz   — liveness probe

Environment: see ``fabric_agent.py``. Additionally honours ``HOST``
and ``PORT`` (default 0.0.0.0:8090).
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, List, Optional

import uvicorn
from agent_framework import Agent, Content, tool
from agent_framework.foundry import FoundryChatClient
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint, state_update
from azure.identity.aio import DefaultAzureCredential
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

# Allow `python -m src.fabric_agent.server` and uvicorn module loading.
_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from src.fabric_agent.fabric_agent import (  # noqa: E402
    _MODEL,
    _PROJECT_ENDPOINT,
    SYSTEM_PROMPT,
    make_compliance_a2a_tool,
    make_fabric_tools,
    make_providers,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("azure").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

_TEMPLATES_DIR = Path(__file__).parent / "templates"


# ---------------------------------------------------------------------------
# Shared-state schema used by the UI sidebar
# ---------------------------------------------------------------------------

class CustomerProfile(BaseModel):
    """The signed-in customer's headline profile."""

    customer_id: Optional[str] = Field(default=None, description="Customer id, e.g. 'CUST-1001'.")
    full_name: Optional[str] = Field(default=None, description="Customer legal name.")
    bank: Optional[str] = Field(default=None, description="Owning bank, e.g. 'Bank South'.")
    segment: Optional[str] = Field(default=None, description="Segment: retail / youth / premium.")


class AccountRow(BaseModel):
    """A single product holding shown in the accounts panel."""

    account_id: str = Field(description="Account id, e.g. 'ACC-100001'.")
    product_name: str = Field(description="Product held, e.g. 'FlexSave', 'GoldCard'.")
    kind: str = Field(default="account", description="'account' or 'card'.")
    balance: Optional[float] = Field(default=None, description="Current balance in EUR.")
    status: Optional[str] = Field(default=None, description="active / blocked / closed / pending.")


class PendingAction(BaseModel):
    """A human-in-the-loop action awaiting the customer's confirmation."""

    kind: Optional[str] = Field(default=None, description="e.g. 'order_product', 'update_customer'.")
    summary: Optional[str] = Field(default=None, description="One-line description of the change.")
    awaiting_confirmation: bool = Field(default=False, description="True while confirmation is pending.")


@tool
def update_overview(
    customer: CustomerProfile,
    accounts: List[AccountRow],
    pending: PendingAction,
) -> Content:
    """Refresh the live sidebar (customer, accounts, pending action).

    Call this whenever the account picture or a pending action changes. Always
    pass the COMPLETE current state — the panels are replaced wholesale, not
    merged. Call this BEFORE writing your chat reply so the UI updates instantly.
    """
    return state_update(
        text="Overview sidebar updated.",
        state={
            "customer": CustomerProfile.model_validate(customer).model_dump(),
            "accounts": [AccountRow.model_validate(a).model_dump() for a in accounts],
            "pending": PendingAction.model_validate(pending).model_dump(),
        },
    )


DEFAULT_STATE: dict = {
    "customer": {"customer_id": None, "full_name": None, "bank": None, "segment": None},
    "accounts": [],
    "pending": {"kind": None, "summary": None, "awaiting_confirmation": False},
}

STATE_SCHEMA: dict = {
    "customer": {"type": "object"},
    "accounts": {"type": "array"},
    "pending": {"type": "object"},
}


# ---------------------------------------------------------------------------
# Agent + context providers + MCP tools (built once, kept alive for app life)
# ---------------------------------------------------------------------------

_credential = DefaultAzureCredential()
_product_provider, _embedding_client = make_providers(_credential)
_fabric_tools = make_fabric_tools(_credential)
# Cross-org A2A: Bank North's Compliance agent as an ask_compliance tool. This
# is the ONLY source of compliance grounding for this agent — when the A2A
# integration is disabled (_compliance_tool is None) the agent has no compliance
# access and must defer regulatory / eligibility questions to a human adviser.
_compliance_tool, _compliance_a2a_agent = make_compliance_a2a_tool(_credential)
_extra_tools = [_compliance_tool] if _compliance_tool is not None else []

_agent = Agent(
    client=FoundryChatClient(
        project_endpoint=_PROJECT_ENDPOINT,
        model=_MODEL,
        credential=_credential,
        allow_preview=True,
    ),
    name="FabricCustomerSupportAgent",
    instructions=SYSTEM_PROMPT,
    tools=[update_overview, *_fabric_tools, *_extra_tools],
    context_providers=[_product_provider],
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Enter the agent + provider + MCP async contexts for the app lifetime."""
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_product_provider)
        if _compliance_a2a_agent is not None:
            await stack.enter_async_context(_compliance_a2a_agent)
        await stack.enter_async_context(_agent)
        logger.info("Customer Support Agent ready (model=%s).", _MODEL)
        try:
            yield
        finally:
            if _embedding_client is not None:
                close = getattr(_embedding_client, "close", None)
                if close is not None:
                    result = close()
                    if asyncio.iscoroutine(result):
                        await result
            await _credential.close()


app = FastAPI(title="Customer Support Agent — AG-UI", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


add_agent_framework_fastapi_endpoint(
    app=app,
    agent=_agent,
    path="/agent",
    state_schema=STATE_SCHEMA,
    default_state=DEFAULT_STATE,
)


def main() -> None:
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8090"))
    logger.info("Starting Customer Support Agent AG-UI server on http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
