"""Shared, cross-cutting building blocks for the banking services.

Currently exposes the repo-wide observability bootstrap
(:func:`_shared.observability.setup_observability`) so that every agent and MCP
server publishes OpenTelemetry telemetry to Application Insights the same way,
without each service re-implementing the wiring.
"""
