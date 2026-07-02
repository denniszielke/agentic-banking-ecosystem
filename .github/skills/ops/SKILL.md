---
name: ops
description: >
  Operations runbook for the agentic-banking-ecosystem repo. USE THIS SKILL when
  the user asks to deploy, build, provision, generate data, index, ingest,
  register, or clean up any part of the project — including infrastructure (azd),
  container images, Container Apps, the customer/product MCP servers, AI Search
  indexes, Foundry toolboxes, and the banking agents. Covers the full lifecycle:
  provision → generate data → build → deploy MCP → register toolboxes → index →
  ingest → deploy agents → clean up.
---

# Ops Runbook — agentic-banking-ecosystem

A multi-organisation agentic banking demo (Bank North + Bank South). It ships two
MCP servers (customer data, product data), two Azure AI Search indexes (Financial
products, Compliance rules), and three agents:

- **compliance_agent** — Bank North, Foundry **hosted agent** (index-only,
  cross-org A2A service).
- **employee_advisory_agent** — Foundry **hosted agent** (product/customer/WorkIQ
  toolboxes + Financial products index).
- **customer_support_agent** — Bank South, Azure **Container App** + web UI
  (customer/product MCP + both indexes).

All commands run from the **repo root**. Configuration comes from `./.env`, which
`azd up` writes automatically. Use the project venv:

```bash
source .venv/bin/activate   # or prefix commands with: .venv/bin/python
```

---

## 0. Prerequisites

| Tool | Version | Install |
|---|---|---|
| Azure Developer CLI (`azd`) | latest | https://aka.ms/azd |
| Azure CLI (`az`) | ≥ 2.60 | https://aka.ms/azcli |
| Python | 3.13 + | |

Install Python deps (all services + scripts):
```bash
pip install -r requirements.txt
# script-only deps (agents/index tooling):
pip install -r scripts/requirements-agents.txt
```

---

## 1. Provision Infrastructure

Creates the long-lived Azure resources (AI Foundry project, Azure AI Search,
Container Apps environment, ACR, user-assigned managed identity) and writes all
outputs to `./.env`.

```bash
azd env set AZURE_LOCATION swedencentral
azd env set AZURE_PRINCIPAL_ID $(az ad signed-in-user show --query id -o tsv)
azd env set AZURE_PRINCIPAL_TYPE User
azd env set SKIP_CONNECTION_CREATION true
azd env set SKIP_ROLE_ASSIGNMENTS true
azd up
```

Provision only / deploy only / tear down:
```bash
azd provision
azd deploy
azd down
```

---

## 2. Generate Demo Data

The synthetic customer/transaction data is generated deterministically (seeded).
Regenerates `data/customers.md`, `data/customers.json`, `data/transactions.json`
and the per-customer files under `data/transactions/`.

```bash
python -m scripts.generate_data
# or: python3 scripts/generate_data.py
```

The knowledge markdown under `data/knowledge/` and the data model in
`data/products.md` are authored by hand (not generated).

---

## 3. Build the MCP Server Images

Builds the two MCP server images (`customer-data-mcp-server`,
`product-data-mcp-server`) in ACR (no local Docker). Only builds — does not
deploy. The resource group is read from `./.env` (`AZURE_RESOURCE_GROUP`, or
`rg-<AZURE_ENV_NAME>`); subscription and registry are discovered from it.

```bash
python -m scripts.build_containers                 # auto timestamp tag + :latest
python -m scripts.build_containers latest          # explicit tag
python -m scripts.build_containers --env <name>    # override rg-<name>
```

---

## 4. Deploy the MCP Servers

Deploys each MCP server as a Container App via `infra/core/host/app.bicep`. Pass
`--build` to build in ACR first (else deploys `:latest` or the `TAG` env var).
Add `--register` to also publish the server as a Foundry toolbox in the same run.

```bash
# customer data MCP server (customers, accounts, balances, transactions)
python -m scripts.deploy_customer_data_mcp_server --build --register

# product data MCP server (catalogue + per-customer holdings)
python -m scripts.deploy_product_data_mcp_server --build --register
```

Each prints the deployed `…/mcp` URL. Key overrides:
- `CUSTOMER_MCP_APP_NAME` / `PRODUCT_MCP_APP_NAME` — Container App name
- `CUSTOMER_MCP_PORT` (8092) / `PRODUCT_MCP_PORT` (8093)
- `CUSTOMER_MCP_EXTERNAL` / `PRODUCT_MCP_EXTERNAL` — public ingress (default: true)
- `CUSTOMER_TOOLBOX_NAME` / `PRODUCT_TOOLBOX_NAME` — toolbox names for `--register`

---

## 5. Register the Foundry Toolboxes

The MCP-server toolboxes are registered automatically with `--register` above.
Register any toolbox on its own (idempotent, re-runnable):

```bash
python -m scripts.register_customer_data_toolbox    # → customer-data-tools
python -m scripts.register_product_data_toolbox     # → product-data-tools
python -m scripts.register_workiq_toolbox           # → workiq-tools (employee agent)
```

Each prints the consumer endpoint
`{project}/toolboxes/{toolbox}/mcp?api-version=v1`. Key overrides:
- `CUSTOMER_TOOLBOX_NAME` / `PRODUCT_TOOLBOX_NAME` / `WORKIQ_TOOLBOX_NAME`
- `CUSTOMER_MCP_URL` / `PRODUCT_MCP_URL` — explicit MCP URL (else derived from the
  Container App FQDN via `AZURE_RESOURCE_GROUP`)
- `WORKIQ_MCP_URL` / `WORKIQ_CONNECTION_ID` — WorkIQ MCP URL / OAuth connection id

**WorkIQ auth (OAuth identity passthrough).** WorkIQ needs a custom-Entra OAuth
connection — static tokens are rejected. There is no `McpServers.WorkIQ.All`
scope / `mcp_WorkIQTools` server; use a granular capability (default:
`mcp_CalendarTools` / `McpServers.Calendar.All`, via `WORKIQ_MCP_SERVER` /
`WORKIQ_SCOPE`). Setup:
1. `python -m scripts.setup_workiq_oauth_app` — creates the Entra app + admin
   consent + secret and prints the Foundry connection values.
2. In the Foundry portal create a `workiq-connection` (Custom → MCP → OAuth
   Identity Passthrough → Custom OAuth); add the redirect URL it returns back to
   the app registration.
3. `WORKIQ_CONNECTION_NAME=workiq-connection python -m scripts.register_workiq_toolbox`.

---

## 6. Create & Populate the Search Indexes

Two Azure AI Search indexes: **Financial products** (`banking-products`) and
**Compliance rules** (`banking-compliance`), both with HNSW vector + semantic
search.

```bash
# create/update the two index schemas
python -m scripts.create_search_indexes

# parse data/products.md + data/knowledge/*.md, embed (if AZURE_OPENAI_ENDPOINT is
# set) and upload
python -m scripts.ingest_knowledge
```

Ingestion is embedding-optional: without `AZURE_OPENAI_ENDPOINT` the documents are
pushed without vectors and text/semantic search still works. Key overrides:
- `AZURE_SEARCH_PRODUCT_INDEX_NAME` (banking-products)
- `AZURE_SEARCH_COMPLIANCE_INDEX_NAME` (banking-compliance)
- `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` (text-embedding-3-small)
- `AZURE_OPENAI_EMBEDDING_DIMENSIONS` (1536)

---

## 7. Deploy the Agents

Prerequisites: MCP servers deployed + registered as toolboxes (§4–5), WorkIQ
toolbox registered (§5), and indexes created + ingested (§6).

### Compliance agent (Bank North, Foundry hosted agent — index-only)
```bash
python -m scripts.deploy_compliance_agent
```
Key overrides: `AZURE_AI_COMPLIANCE_AGENT_NAME` (compliance-agent),
`COMPLIANCE_BANK_ID` (bank-north). Enables RESPONSES + A2A + INVOCATIONS.

### Employee advisory agent (Foundry hosted agent — one per bank)
```bash
python -m scripts.deploy_employee_advisory_agent
```
Consumes the product/customer/WorkIQ toolboxes + Financial products index. Key
overrides: `AZURE_AI_EMPLOYEE_AGENT_NAME` (employee-advisory-agent),
`EMPLOYEE_BANK_ID` (bank-south), `EMPLOYEE_WORKIQ_ENABLED` (true),
`PRODUCT_TOOLBOX_NAME` / `CUSTOMER_TOOLBOX_NAME` / `WORKIQ_TOOLBOX_NAME`.

### Customer support agent (Bank South, Container App + web UI)
```bash
python -m scripts.deploy_customer_support_agent --build
```
Reaches the customer/product MCP servers directly (URLs auto-resolved) and grounds
on both indexes. Grants the managed identity **Cognitive Services User**,
**Search Index Data Reader** and **Monitoring Metrics Publisher**. Prints the
public web-UI URL. Key overrides: `CUSTOMER_SUPPORT_APP_NAME`
(customer-support-agent), `CUSTOMER_SUPPORT_PORT` (8090),
`CUSTOMER_SUPPORT_EXTERNAL` (true), `CUSTOMER_MCP_URL` / `PRODUCT_MCP_URL`.

### Deploy all three together
```bash
python -m scripts.deploy_banking_agents --build
python -m scripts.deploy_banking_agents --only customer-support --build
```
`--build` rebuilds the container-app image; `--only` accepts `compliance`,
`employee`, `customer-support` (repeatable).

---

## 8. Run Services Locally

### Customer data MCP server
```bash
python -m src.customer_data_mcp_server.server
# serves http://127.0.0.1:8092/mcp  (override CUSTOMER_MCP_HOST / CUSTOMER_MCP_PORT)
```

### Product data MCP server
```bash
python -m src.product_data_mcp_server.server
# serves http://127.0.0.1:8093/mcp  (override PRODUCT_MCP_HOST / PRODUCT_MCP_PORT)
```

### Compliance agent (RESPONSES host, port 8088)
```bash
export AZURE_AI_PROJECT_ENDPOINT="https://<project>.services.ai.azure.com/api/projects/<name>"
export AZURE_SEARCH_ENDPOINT="https://<search>.search.windows.net"
python -m src.compliance_agent.agent
```

### Employee advisory agent (RESPONSES host, port 8088)
```bash
# direct MCP URLs bypass the toolboxes for local dev:
export PRODUCT_MCP_URL="http://127.0.0.1:8093/mcp"
export CUSTOMER_MCP_URL="http://127.0.0.1:8092/mcp"
python -m src.employee_advisory_agent.agent
```

### Customer support agent (AG-UI web UI, port 8090)
```bash
export CUSTOMER_MCP_URL="http://127.0.0.1:8092/mcp"
export PRODUCT_MCP_URL="http://127.0.0.1:8093/mcp"
python -m src.customer_support_agent.server
# open http://localhost:8090
```

---

## 9. Cleanup

```bash
# Foundry hosted agents (compliance, employee advisory)
python -m scripts.delete_agents
python -m scripts.delete_agents --toolboxes   # also delete the toolboxes

# Container Apps (customer support agent + customer/product MCP servers)
python -m scripts.delete_container_apps

# the two Azure AI Search indexes (schema + data)
python -m scripts.delete_search_indexes

# tear down all Azure resources
azd down
```

---

## 10. Environment Variable Reference

Most variables are written to `./.env` by `azd up`.

| Variable | Source | Used by |
|---|---|---|
| `AZURE_RESOURCE_GROUP` | azd | all deploy scripts |
| `AZURE_REGISTRY` / `AZURE_CONTAINER_REGISTRY_ENDPOINT` | azd | build, deploy, hosted agents |
| `AZURE_CONTAINER_APPS_ENVIRONMENT_NAME` | azd | container-app deploy |
| `AZURE_IDENTITY_NAME` | azd | container-app deploy (managed identity) |
| `AZURE_AI_PROJECT_ENDPOINT` | azd | agents, toolboxes |
| `AZURE_SEARCH_ENDPOINT` | azd | indexing, ingestion, agents |
| `AZURE_SEARCH_ADMIN_KEY` | azd | indexing (optional; falls back to DefaultAzureCredential) |
| `AZURE_SEARCH_PRODUCT_INDEX_NAME` | manual | default: `banking-products` |
| `AZURE_SEARCH_COMPLIANCE_INDEX_NAME` | manual | default: `banking-compliance` |
| `AZURE_OPENAI_ENDPOINT` | azd | model + embedding calls |
| `AZURE_OPENAI_CHAT_DEPLOYMENT_NAME` | azd | default: `gpt-4.1-mini` |
| `AZURE_OPENAI_EMBEDDING_DEPLOYMENT_NAME` | azd | default: `text-embedding-3-small` |
| `AZURE_AI_MODEL_DEPLOYMENT_NAME` | azd | fallback model |
| `OPENAI_API_VERSION` | azd | default: `2024-05-01-preview` |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | azd | telemetry |
| `TAG` | manual | image tag for deploy (default: `latest`) |
| `CUSTOMER_MCP_APP_NAME` / `PRODUCT_MCP_APP_NAME` | manual | MCP Container App names |
| `CUSTOMER_MCP_PORT` / `PRODUCT_MCP_PORT` | manual | `8092` / `8093` |
| `CUSTOMER_MCP_EXTERNAL` / `PRODUCT_MCP_EXTERNAL` | manual | public ingress (default: true) |
| `CUSTOMER_MCP_URL` / `PRODUCT_MCP_URL` | manual | direct MCP URL (local dev / container app) |
| `CUSTOMER_TOOLBOX_NAME` | manual | default: `customer-data-tools` |
| `PRODUCT_TOOLBOX_NAME` | manual | default: `product-data-tools` |
| `WORKIQ_TOOLBOX_NAME` | manual | default: `workiq-tools` |
| `WORKIQ_MCP_URL` / `WORKIQ_CONNECTION_ID` | manual | WorkIQ MCP URL / OAuth connection id |
| `AZURE_AI_COMPLIANCE_AGENT_NAME` | manual | default: `compliance-agent` |
| `AZURE_AI_EMPLOYEE_AGENT_NAME` | manual | default: `employee-advisory-agent` |
| `EMPLOYEE_WORKIQ_ENABLED` | manual | attach WorkIQ tool (default: true) |
| `CUSTOMER_SUPPORT_APP_NAME` | manual | default: `customer-support-agent` |
| `CUSTOMER_SUPPORT_PORT` / `CUSTOMER_SUPPORT_EXTERNAL` | manual | `8090` / public (true) |
| `BANK_ID` / `COMPLIANCE_BANK_ID` / `EMPLOYEE_BANK_ID` | manual | owning bank id |

---

## 11. Conventions

- Run all scripts from the **repo root** as modules: `python -m scripts.<name>`.
- Scripts read `./.env` via `python-dotenv` — source it before manual CLI work.
- Image builds use `az acr build` (no local Docker). Both `:<timestamp>` and
  `:latest` tags are pushed on every build.
- Hosted agents (compliance, employee advisory) speak **RESPONSES + A2A +
  INVOCATIONS** on port `8088`; the customer support Container App serves the
  AG-UI web UI on port `8090`.
- Agents reach MCP servers through **Foundry toolboxes** by default; a direct
  `*_MCP_URL` override bypasses the toolbox for local dev.
- All write tools (`update_customer`, `order_product`, `update_holding`) are
  **human-in-the-loop** — preview, confirm, then commit.
- Each agent loads its domain flows from a `skills/` subfolder that ships inside
  its container image.

