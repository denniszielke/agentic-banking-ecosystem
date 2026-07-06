# Customer Data MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes a
bank's **customer** master data — customers, their product holdings (accounts and
credit cards), balances and transactions — to the banking agents
(`customer_support_agent`, `employee_advisory_agent`, `credit_card_agent`).

All data is **synthetic** and lives in the shared [`data/`](../../data) directory at
the repository root (`customers.json` + `transactions.json`), generated
deterministically by [`scripts/generate_data.py`](../../scripts/generate_data.py).
There is no database — the JSON files *are* the source of truth. This mirrors the
real-world trust boundary: customer data is confidential and is only ever reachable
through this Entra ID authenticated MCP surface. The canonical entities and tool
surface are defined in [`data/products.md`](../../data/products.md).

## Tools

| Tool | Purpose | Access |
| --- | --- | --- |
| `list_customers` | List customers, optionally filtered by bank | read |
| `get_customer` | Full customer profile incl. product holdings | read |
| `list_accounts` | Product holdings of a customer | read |
| `get_account` | A single holding by account id | read |
| `list_transactions` | Transactions for an account or a whole customer | read |
| `get_balance` | Balance + currency of a holding | read |
| `summarize_spending` | Spending total + breakdown by category / top merchants + largest transaction | read |
| `get_net_worth` | Total net worth + balance breakdown by product type | read |
| `update_customer` | Update contact details | write (HITL) |

The `update_customer` write tool is **human-in-the-loop**: call it first with
`confirm=false` to get a preview of the change, then re-call with `confirm=true`
once a human has approved it.

## Run

```bash
python -m src.customer_data_mcp_server.server
```

Serves streamable-HTTP MCP at `http://127.0.0.1:8092/mcp`. Override the bind
address with `CUSTOMER_MCP_HOST` / `CUSTOMER_MCP_PORT`, and the data location with
`BANK_DATA_DIR` (defaults to the repo `data/` directory).

## Deploy to Azure Container Apps

```bash
# Build the image in ACR, then deploy
python -m scripts.deploy_customer_data_mcp_server --build

# Deploy only — image already in ACR, uses :latest (or TAG env var)
python -m scripts.deploy_customer_data_mcp_server
```

This builds the image and deploys it via
[`infra/core/host/app.bicep`](../../infra/core/host/app.bicep), then prints the
resulting `…/mcp` URL. All variables are sourced from `./.env` (written by
`azd up`); set `TAG` to the tag printed by
[`scripts/build_containers.py`](../../scripts/build_containers.py).

| Variable | Description | Default |
| --- | --- | --- |
| `CUSTOMER_MCP_APP_NAME` | Container App name | `customer-data-mcp-server` |
| `CUSTOMER_MCP_PORT` | Container port | `8092` |
| `CUSTOMER_MCP_EXTERNAL` | Expose the app externally (`true`/`false`) | `true` |
