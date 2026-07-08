"""Deploy all banking agents in one run.

Convenience wrapper that deploys, in order:
  1. the **Compliance Agent** (Foundry hosted agent),
  2. the **Employee Advisory Agent** (Foundry hosted agent),
  3. the **Recommender Agent** (Foundry hosted agent),
  4. the **Customer Support Agent** (Container App + web UI).

It assumes the prerequisites already exist:
  * ``azd up`` has provisioned the infrastructure,
  * the customer/product MCP servers are deployed and registered as toolboxes
    (``deploy_*_mcp_server.py --build --register``),
  * the finance toolbox is registered (``register_finance_toolbox.py``),
  * the WorkIQ toolbox is registered (``register_workiq_toolbox.py``),
  * the search indexes are created and ingested
    (``create_search_indexes.py`` + ``ingest_knowledge.py``).

Usage::

    python -m scripts.deploy_banking_agents            # deploy all four
    python -m scripts.deploy_banking_agents --only recommender

``--only`` accepts: compliance, employee, recommender, customer-support (repeatable).
"""

from __future__ import annotations

import sys

from scripts import (
    deploy_compliance_agent,
    deploy_customer_support_agent,
    deploy_employee_advisory_agent,
    deploy_recommender_agent,
)


def main(argv: list[str]) -> None:
    only: set[str] = set()
    i = 0
    while i < len(argv):
        if argv[i] == "--only" and i + 1 < len(argv):
            only.add(argv[i + 1])
            i += 2
        else:
            i += 1

    def _wanted(name: str) -> bool:
        return not only or name in only

    if _wanted("compliance"):
        print("\n=== Deploying Compliance Agent ===")
        deploy_compliance_agent.deploy()
    if _wanted("employee"):
        print("\n=== Deploying Employee Advisory Agent ===")
        deploy_employee_advisory_agent.deploy()
    if _wanted("recommender"):
        print("\n=== Deploying Recommender Agent ===")
        deploy_recommender_agent.deploy()
    if _wanted("customer-support"):
        print("\n=== Deploying Customer Support Agent ===")
        built_tag = deploy_customer_support_agent.build() if "--build" in argv else None
        deploy_customer_support_agent.deploy(tag=built_tag)


if __name__ == "__main__":
    main(sys.argv[1:])
