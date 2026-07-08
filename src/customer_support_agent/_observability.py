"""Telemetry bootstrap for the Customer Support Agent (backward-compat shim).

The actual wiring now lives in the repo-wide :mod:`src._shared.observability`
module so every agent and MCP server is instrumented the same way, and telemetry
is enabled automatically for all services from ``src/__init__.py``.

This thin wrapper is kept so the existing early call in ``server.py`` still works
and remains a self-documenting reminder that the Microsoft OpenTelemetry distro
must be configured before importing any instrumented library. The underlying
setup is idempotent, so this explicit call and the ``src`` auto-bootstrap resolve
to a single configuration.
"""
from __future__ import annotations

from src._shared.observability import setup_observability

__all__ = ["setup_observability"]
