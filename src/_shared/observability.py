"""Repo-wide OpenTelemetry → Application Insights bootstrap.

This is the **single** place that wires telemetry for the whole banking
ecosystem.  Every component — the agents *and* the MCP servers — publishes
OpenTelemetry telemetry to Application Insights through this one function, which
is what the design narrative asks for ("All agents, MCP servers, and web
applications should publish OTel-based telemetry into Application Insights").

It is invoked automatically for every service from ``src/__init__.py`` (which
runs first for any ``python -m src.<service>.<module>`` entrypoint, before the
service imports its instrumented libraries), so a new agent or MCP server gets
telemetry **for free** — no per-service bootstrap code, and no way to forget it.

Design points
-------------
* **Idempotent.** Safe to call more than once (the auto-bootstrap plus an
  explicit call in a service both resolve to a single configuration).
* **Import-order safe.** Because it runs from ``src/__init__.py`` before the
  service body imports ``agent_framework`` / ``fastmcp`` / the Azure SDK, the
  distro's import-time instrumentation hooks attach correctly.
* **Opt-in by connection string.** When ``APPLICATIONINSIGHTS_CONNECTION_STRING``
  is unset (local dev) it is a no-op, so importing ``src`` never fails or emits.
* **Distro-agnostic.** Prefers the Microsoft OpenTelemetry distro (adds the
  Agent Framework GenAI instrumentation for the agents); falls back to the plain
  Azure Monitor distro for lightweight services (the MCP servers) that do not
  ship ``agent-framework``.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

_configured = False


def _instrument_asgi() -> None:
    """Best-effort instrument the ASGI stack (MCP servers run on Starlette).

    ``configure_azure_monitor`` auto-instruments common libraries but not
    Starlette (which FastMCP serves over), so incoming MCP requests would not be
    traced.  Instrumenting it globally patches the Starlette app class, so any
    app created afterwards (FastMCP builds its app in ``mcp.run``) is traced.
    Missing packages are ignored so agent images that do not need it are fine.
    """
    for module_name, class_name in (
        ("opentelemetry.instrumentation.starlette", "StarletteInstrumentor"),
        ("opentelemetry.instrumentation.httpx", "HTTPXClientInstrumentor"),
    ):
        try:
            module = __import__(module_name, fromlist=[class_name])
            getattr(module, class_name)().instrument()
        except Exception:  # noqa: BLE001 - telemetry must never break the service
            logger.debug("Optional instrumentor %s unavailable.", module_name)


def setup_observability(service_name: str | None = None) -> bool:
    """Configure OpenTelemetry → Azure Monitor once, for any banking service.

    Args:
        service_name: OTel ``service.name`` → App Insights ``cloud_RoleName``.
            When omitted, ``OTEL_SERVICE_NAME`` from the environment is used
            (each service sets it at deploy time).

    Returns:
        ``True`` when telemetry was enabled (or already was), ``False`` when it
        is skipped because no connection string is configured or no distro is
        installed.
    """
    global _configured
    if _configured:
        return True

    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        logger.info(
            "Observability disabled: APPLICATIONINSIGHTS_CONNECTION_STRING not set."
        )
        return False

    # service.name -> App Insights cloud_RoleName. setdefault so an explicit
    # OTEL_SERVICE_NAME in the environment always wins over the caller default.
    name = (service_name or os.getenv("OTEL_SERVICE_NAME") or "").strip()
    if name:
        os.environ.setdefault("OTEL_SERVICE_NAME", name)

    try:
        from microsoft.opentelemetry import use_microsoft_opentelemetry
    except ImportError:
        # Lightweight services (MCP servers) ship only the Azure Monitor distro.
        try:
            from azure.monitor.opentelemetry import configure_azure_monitor
        except ImportError:
            logger.warning(
                "Observability requested but no OpenTelemetry distro is installed; "
                "skipping telemetry setup."
            )
            return False
        configure_azure_monitor()
        _instrument_asgi()
        _configured = True
        logger.info(
            "Observability enabled via Azure Monitor distro (service=%s).",
            os.getenv("OTEL_SERVICE_NAME"),
        )
        return True

    # Agents: the Microsoft distro also installs the Agent Framework GenAI
    # instrumentation and picks up APPLICATIONINSIGHTS_CONNECTION_STRING itself.
    use_microsoft_opentelemetry(enable_azure_monitor=True)
    _instrument_asgi()
    _configured = True
    logger.info(
        "Observability enabled via Microsoft OpenTelemetry distro (service=%s).",
        os.getenv("OTEL_SERVICE_NAME"),
    )
    return True
