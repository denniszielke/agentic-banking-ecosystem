"""Deploy the **Employee Advisory Agent** as an Azure AI Foundry hosted agent.

The internal advisory agent (one hosted instance per bank). It consumes the
Financial products Azure AI Search index plus three Foundry toolboxes — the
product data MCP server, the customer data MCP server (read-only context) and
the WorkIQ MCP server — so run it after those toolboxes are registered:

    python -m scripts.deploy_product_data_mcp_server --build --register
    python -m scripts.deploy_customer_data_mcp_server --build --register
    python -m scripts.register_workiq_toolbox

Environment variables:
  AZURE_AI_PROJECT_ENDPOINT             Foundry project endpoint (required).
  AZURE_CONTAINER_REGISTRY_ENDPOINT     ACR login server for the agent image (required).
  AZURE_AI_EMPLOYEE_AGENT_NAME          Hosted agent name (default: employee-advisory-agent).
  PRODUCT_TOOLBOX_NAME                  Product MCP toolbox (default: product-data-tools).
  CUSTOMER_TOOLBOX_NAME                 Customer MCP toolbox (default: customer-data-tools).
  WORKIQ_TOOLBOX_NAME                   WorkIQ toolbox (default: workiq-tools).
  EMPLOYEE_WORKIQ_ENABLED               Attach WorkIQ tool (default: true).
  EMPLOYEE_BANK_ID                      Owning bank id (default: bank-south).
"""

from __future__ import annotations

import os

from scripts.agent_deploy_helpers import (
    deploy_hosted_agent,
    get_client,
    load_agent_card,
    resolve_registry,
)

EMPLOYEE_AGENT_CARD = load_agent_card("src/employee_advisory_agent/agentcard.json")


def deploy() -> None:
    project_endpoint = os.getenv("AZURE_AI_PROJECT_ENDPOINT")
    if not project_endpoint:
        print("Skipping employee advisory agent deployment: AZURE_AI_PROJECT_ENDPOINT is required.")
        return
    registry = resolve_registry()

    client = get_client()
    deploy_hosted_agent(
        client,
        agent_name=os.getenv("AZURE_AI_EMPLOYEE_AGENT_NAME", "employee-advisory-agent"),
        description="Employee advisory hosted agent (internal channel)",
        registry=registry,
        project_endpoint=project_endpoint,
        dockerfile_rel="src/employee_advisory_agent/Dockerfile",
        extra_env={
            "BANK_ID": os.getenv("EMPLOYEE_BANK_ID", "bank-south"),
            "PRODUCT_TOOLBOX_NAME": os.getenv("PRODUCT_TOOLBOX_NAME", "product-data-tools"),
            "CUSTOMER_TOOLBOX_NAME": os.getenv("CUSTOMER_TOOLBOX_NAME", "customer-data-tools"),
            "WORKIQ_TOOLBOX_NAME": os.getenv("WORKIQ_TOOLBOX_NAME", "workiq-tools"),
            "EMPLOYEE_WORKIQ_ENABLED": os.getenv("EMPLOYEE_WORKIQ_ENABLED", "true"),
            "FINBOT_SQL_TOOLBOX_NAME": os.getenv("FINBOT_SQL_TOOLBOX_NAME", "finbot-sql-tools"),
            "EMPLOYEE_FINBOT_SQL_ENABLED": os.getenv("EMPLOYEE_FINBOT_SQL_ENABLED", "true"),
            # Direct MCP overrides (blank by default → use the toolboxes).
            "PRODUCT_MCP_URL": os.getenv("PRODUCT_MCP_URL", ""),
            "CUSTOMER_MCP_URL": os.getenv("CUSTOMER_MCP_URL", ""),
            "WORKIQ_MCP_URL": os.getenv("WORKIQ_MCP_URL", ""),
        },
        agent_card=EMPLOYEE_AGENT_CARD,
    )


if __name__ == "__main__":
    deploy()
