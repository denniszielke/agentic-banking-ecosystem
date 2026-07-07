"""Authentication policy for the Finance MCP server.

The server only runs behind a cloud platform that authenticates every caller at
its own gate before the request reaches the app:

* **Google Cloud Run** -- IAM (`--no-allow-unauthenticated`, `roles/run.invoker`)
* **Databricks Apps** -- the workspace OAuth front door
* **Microsoft Azure** -- App Service Authentication ("Easy Auth") / API Management

In every case the platform, not the app, validates the caller, so the app does
not build its own token verifier. It only needs to confirm that such a gate is
in place before exposing banking data over the network -- signalled by
``MCP_TRUST_PLATFORM_AUTH=1``. See ``server.main`` for the start/refuse decision.
"""

from __future__ import annotations

import os

# Truthy values for MCP_TRUST_PLATFORM_AUTH.
_TRUTHY = {"1", "true", "yes", "on"}


def trust_platform_auth() -> bool:
    """Whether the deployment platform's own auth gate is trusted.

    When true, the app serves network requests without an app-level check
    because the platform (Cloud Run IAM, Databricks OAuth, Azure Easy Auth)
    authenticates every caller before the request reaches the app.
    """
    return os.environ.get("MCP_TRUST_PLATFORM_AUTH", "").strip().lower() in _TRUTHY
