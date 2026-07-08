"""AG-UI server for the Web Recommender Agent (Volksbank personal banking assistant).

Hosts the recommender agent behind the AG-UI protocol (Server-Sent Events) and
serves a streaming single-page Volksbank web UI from the same container.

Authentication
--------------
The frontend acquires a delegated Entra token via MSAL.js and sends it in the
``Authorization: Bearer <token>`` header with every ``POST /agent`` request.
The backend extracts this token and creates an ``OnBehalfOfCredential`` so that
all downstream Foundry / Fabric calls run under the **signed-in user's identity**
(OBO flow). This is the critical step that lets the Fabric DataAgent enforce the
user's own Fabric workspace permissions.

When no user token is present (local dev without MSAL), the server falls back to
``DefaultAzureCredential`` (developer's own identity via ``az login``).

Required env vars for OBO (set after running setup_web_recommender_oauth_app.py):
  WEB_RECOMMENDER_CLIENT_ID        app registration client id
  WEB_RECOMMENDER_CLIENT_SECRET    client secret for OBO token exchange
  WEB_RECOMMENDER_TENANT_ID        Entra tenant id

Endpoints:
  GET  /          — the chat web UI
  POST /agent     — the AG-UI protocol endpoint (SSE stream)
  GET  /healthz   — liveness probe

Environment: see ``web_recommender_agent.py``. Additionally honours ``HOST``
and ``PORT`` (default 0.0.0.0:8092).
"""
from __future__ import annotations

import logging
import json
import os
import sys
from contextlib import AsyncExitStack, asynccontextmanager
from pathlib import Path
from typing import AsyncIterator, Optional

import uvicorn
from agent_framework_ag_ui import add_agent_framework_fastapi_endpoint
from azure.identity import DefaultAzureCredential, OnBehalfOfCredential
from fastapi import FastAPI
from fastapi.responses import HTMLResponse

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dotenv import load_dotenv
_env_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=_env_path if _env_path.exists() else None)

from src.web_recommender_agent.web_recommender_agent import (  # noqa: E402
    make_agent,
    make_fabric_tool,
    make_finance_mcp_tool,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logging.getLogger("azure").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Red console handler for tool-call events
# ---------------------------------------------------------------------------

class _RedToolHandler(logging.StreamHandler):
    """Print tool-call log records in bold red to make them stand out."""
    _RED = "\033[1;31m"
    _RESET = "\033[0m"
    _KEYWORDS = ("TOOL_CALL", "Function name", "Function ", "azure_fabric", "calculate_", "discount_")

    def emit(self, record: logging.LogRecord) -> None:
        msg = self.format(record)
        if any(k in msg for k in self._KEYWORDS):
            print(f"{self._RED}{msg}{self._RESET}", flush=True)
        else:
            super().emit(record)


_red_handler = _RedToolHandler()
_red_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
for _noisy in ("agent_framework", "agent_framework_ag_ui", "httpx"):
    _log = logging.getLogger(_noisy)
    _log.addHandler(_red_handler)
    _log.propagate = False

_TEMPLATES_DIR = Path(__file__).parent / "templates"

# ---------------------------------------------------------------------------
# OAuth / OBO configuration (set by setup_web_recommender_oauth_app.py)
# ---------------------------------------------------------------------------

_OAUTH_CLIENT_ID = os.getenv("WEB_RECOMMENDER_CLIENT_ID", "").strip()
_OAUTH_CLIENT_SECRET = os.getenv("WEB_RECOMMENDER_CLIENT_SECRET", "").strip()
_OAUTH_TENANT_ID = os.getenv(
    "WEB_RECOMMENDER_TENANT_ID",
    os.getenv("AZURE_TENANT_ID", "").strip(),
)

# ---------------------------------------------------------------------------
# AG-UI sidebar state defaults
# ---------------------------------------------------------------------------

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
# Credential + agent factory
# ---------------------------------------------------------------------------

# Fallback credential (local dev without MSAL / OBO not configured).
_fallback_credential = DefaultAzureCredential()
_finance_mcp_tool = make_finance_mcp_tool(_fallback_credential)
_fabric_tool, _foundry_client = make_fabric_tool(_fallback_credential)
_agent = make_agent(_foundry_client, _fabric_tool, _finance_mcp_tool)


def _build_credential(user_token: Optional[str]):
    """Return an OBO credential when a user token is available, else fallback."""
    if user_token and _OAUTH_CLIENT_ID and _OAUTH_CLIENT_SECRET and _OAUTH_TENANT_ID:
        logger.info("Using OnBehalfOfCredential for user OBO.")
        # user_assertion: token for api://<CLIENT_ID>/user_impersonation
        # OBO exchanges this for cognitiveservices.azure.com (Foundry) tokens.
        return OnBehalfOfCredential(
            tenant_id=_OAUTH_TENANT_ID,
            client_id=_OAUTH_CLIENT_ID,
            client_secret=_OAUTH_CLIENT_SECRET,
            user_assertion=user_token,
        )
    if not user_token:
        logger.info("No user token — using DefaultAzureCredential (dev mode).")
    else:
        logger.warning(
            "User token present but OBO env vars not set "
            "(WEB_RECOMMENDER_CLIENT_ID/SECRET/TENANT_ID). Falling back to DefaultAzureCredential."
        )
    return _fallback_credential


def _build_agent(user_token: Optional[str]) -> tuple[Agent, any]:
    """Build a per-request agent with the appropriate credential."""
    credential = _build_credential(user_token)
    fabric_tool, foundry_client = make_fabric_tool(credential)
    return make_agent(foundry_client, fabric_tool, _finance_mcp_tool), None


# ---------------------------------------------------------------------------
# Lifespan: keep Finance MCP connection alive
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    async with AsyncExitStack() as stack:
        await stack.enter_async_context(_finance_mcp_tool)
        await stack.enter_async_context(_agent)
        logger.info("Web Recommender Agent ready.")
        yield


app = FastAPI(title="Web Recommender Agent — AG-UI", lifespan=lifespan)


@app.get("/", response_class=HTMLResponse)
def home() -> str:
    return (_TEMPLATES_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/config.js")
def config_js():
    """Expose OAuth config to the frontend (client ID and tenant — no secrets)."""
    from fastapi.responses import Response
    js = (
        f"window.WEB_RECOMMENDER_CLIENT_ID = {json.dumps(_OAUTH_CLIENT_ID)};\n"
        f"window.WEB_RECOMMENDER_TENANT_ID = {json.dumps(_OAUTH_TENANT_ID or 'common')};\n"
    )
    return Response(content=js, media_type="application/javascript")


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
    port = int(os.getenv("PORT", "8092"))
    logger.info("Starting Web Recommender Agent on http://%s:%d", host, port)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
