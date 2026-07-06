"""Telemetry bootstrap for the Customer Support Agent.

**Import and call** ``setup_observability`` **before importing any instrumented
library** (agent_framework, azure-sdk, openai, …).  The Microsoft OpenTelemetry
distro may use import-time patching; if it is called after those libraries are
already loaded the hooks may not attach and spans (model calls, MCP tool calls,
human-in-the-loop confirmations) may never be exported to Application Insights.

Keeping this module free of heavy imports makes it safe to import and invoke
early — before the rest of the agent package is loaded.
"""
from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)


def setup_observability() -> bool:
    """Configure the Microsoft OpenTelemetry distro → Azure Monitor, once.

    Wires the Microsoft OpenTelemetry distro so Agent Framework model calls, MCP
    tool calls and human-in-the-loop confirmations are emitted as GenAI
    spans/events and exported to Application Insights (via
    ``APPLICATIONINSIGHTS_CONNECTION_STRING``).

    **Must be called before importing any instrumented library** (agent_framework,
    azure-sdk, openai, …).  The Microsoft distro may use import-time patching; if
    called after those libraries are already imported the hooks may not attach and
    spans may never be exported, which defeats the observability goal.

    Returns ``True`` when telemetry was enabled, or ``False`` when it is skipped
    because no connection string is configured (local dev).  The
    ``microsoft.opentelemetry`` import is lazy so the module still loads where the
    telemetry packages are not installed.
    """
    conn = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "").strip()
    if not conn:
        logger.info("Observability disabled: APPLICATIONINSIGHTS_CONNECTION_STRING not set.")
        return False
    try:
        from microsoft.opentelemetry import use_microsoft_opentelemetry
    except ImportError:
        logger.warning(
            "Observability requested but 'microsoft-opentelemetry' is not "
            "installed; skipping telemetry setup."
        )
        return False
    # enable_azure_monitor picks up APPLICATIONINSIGHTS_CONNECTION_STRING from the
    # environment and installs the Agent Framework GenAI instrumentation.
    use_microsoft_opentelemetry(enable_azure_monitor=True)
    agent_id = os.getenv("CUSTOMER_SUPPORT_AGENT_ID", "customer-support-agent")
    logger.info(
        "Observability enabled: exporting GenAI telemetry to Application Insights "
        "(agent id=%s).", agent_id,
    )
    return True
