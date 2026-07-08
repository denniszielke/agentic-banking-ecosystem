# Finance MCP Server

A [Model Context Protocol](https://modelcontextprotocol.io) server that exposes
**financial calculation tools** — compound interest and present-value discounting
— to the banking agents (`customer_support_agent`, `employee_advisory_agent`).

The server is a pure-compute surface with no external data dependencies. It is
protected by Microsoft Entra ID JWT authentication when deployed on Azure
Container Apps.

## Tools

| Tool | Purpose | Access |
| --- | --- | --- |
| `calculate_compound_interest` | Future value of an investment given principal, rate, duration and compounding frequency | read |
| `discount_cashflow` | Present value of a future cash flow given amount, discount rate, duration and compounding frequency | read |

All rates are annual percentages (e.g. `5` means 5 %). Results are JSON with
monetary values rounded to 2 decimal places.

## Run

```bash
python -m src.finance_mcp_server.server
```

Serves streamable-HTTP MCP at `http://127.0.0.1:8093/mcp`. Override the bind
address with `FINANCE_MCP_HOST` / `FINANCE_MCP_PORT`.

## Deploy to Azure Container Apps

```bash
# Build the image in ACR, then deploy
python -m scripts.deploy_finance_mcp_server --build

# Deploy only — image already in ACR, uses :latest (or TAG env var)
python -m scripts.deploy_finance_mcp_server
```

This builds the image and deploys it via
[`infra/core/host/app.bicep`](../../infra/core/host/app.bicep), then prints the
resulting `…/mcp` URL. All variables are sourced from `./.env` (written by
`azd up`); set `TAG` to the tag printed by
[`scripts/build_containers.py`](../../scripts/build_containers.py).

| Variable | Description | Default |
| --- | --- | --- |
| `FINANCE_MCP_APP_NAME` | Container App name | `finance-mcp-server` |
| `FINANCE_MCP_PORT` | Container port | `8093` |
| `FINANCE_MCP_EXTERNAL` | Expose the app externally (`true`/`false`) | `true` |

## Authentication

Authentication is handled by **FastMCP's Azure JWT verifier** — the app
validates incoming Entra ID access tokens (issuer, audience and JWKS signature)
without relying on Container Apps Easy Auth.

| Variable | Description |
| --- | --- |
| `ENTRA_AUTH_ENABLED` | `true` to enable JWT validation (default: `true` in deploy scripts) |
| `MCP_AUTH_CLIENT_ID` | App registration client id (the token audience) |
| `AZURE_TENANT_ID` | Entra tenant id |
| `MCP_PUBLIC_BASE_URL` | Public base URL injected for FastMCP's OAuth metadata |

The deploy script creates the Entra app registration automatically when
`ENTRA_AUTH_ENABLED=true`. Callers must request a token for audience
`api://<MCP_AUTH_CLIENT_ID>/.default`.

To grant a calling agent's managed identity the `Mcp.Invoke` role:

```bash
python -m scripts.grant_agent_identity_mcp_role
```
