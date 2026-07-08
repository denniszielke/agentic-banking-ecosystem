"""Banking ecosystem source package.

Importing this package auto-configures observability for the whole ecosystem.
Because every service is started as ``python -m src.<service>.<module>``, Python
imports ``src`` (running this file) *before* the service body imports its
instrumented libraries (``agent_framework`` / ``fastmcp`` / the Azure SDK). That
ordering is exactly what the OpenTelemetry distro needs, so wiring the bootstrap
here means every current and future agent or MCP server publishes telemetry to
Application Insights automatically — no per-service code, and no way to forget.

It is a no-op when ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is unset (local dev
and CLI scripts), so importing ``src`` for any purpose stays cheap and safe.
"""
from __future__ import annotations

from ._shared.observability import setup_observability

# Enable telemetry as early as possible. Guarded internally by the connection
# string, so this is a no-op outside a configured (deployed) environment.
setup_observability()
