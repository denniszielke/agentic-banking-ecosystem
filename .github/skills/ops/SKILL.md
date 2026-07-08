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
## 5b. Protect the MCP Servers with Entra ID

The two MCP servers validate Entra ID access tokens **natively inside the app**
via FastMCP's `AzureJWTVerifier` + `RemoteAuthProvider` — no Container Apps Easy
Auth, no auth sidecar, no client secret. Auth is on by default
(`ENTRA_AUTH_ENABLED=true`), so every request must present a valid token. Opt out
per deployment for anonymous ingress:

```bash
azd env set ENTRA_AUTH_ENABLED false   # (or export ENTRA_AUTH_ENABLED=false)
```

With auth enabled (the default), running the MCP deploy scripts (§4) will, for
each server:
- ensure an Entra **app registration** (`<app>-mcp-auth`) with an `Mcp.Invoke`
  app role — the token audience is `api://<appId>`;
- inject the auth config into the container (`ENTRA_AUTH_ENABLED`,
  `MCP_AUTH_CLIENT_ID`, `AZURE_TENANT_ID`, `MCP_PUBLIC_BASE_URL`) so the app
  verifies each token's **issuer**
  (`https://login.microsoftonline.com/<tenant>/v2.0`), **audience** (accepts both
  the bare `<appId>` GUID and `api://<appId>`) and **JWKS signature**; anonymous
  requests get **HTTP 401**. No required scope, so delegated (user) and app-only
  (managed identity) tokens are both accepted;
- print the audience callers must request a token for.

```bash
ENTRA_AUTH_ENABLED=true python -m scripts.deploy_customer_data_mcp_server --register
ENTRA_AUTH_ENABLED=true python -m scripts.deploy_product_data_mcp_server  --register
```

Wire the consumers:
- **Toolbox path (hosted agents, e.g. employee advisory).** The toolbox
  authenticates to the MCP server with the agent's **Entra Agent Identity** (no
  secret). One helper does both the role grant and the connection creation
  (needs the Foundry azd extension: `azd ext install microsoft.foundry`):

  ```bash
  # grants the agent identity Mcp.Invoke on both MCP apps, then creates a
  # remote-tool/agentic-identity connection per server (audience api://<appId>)
  python -m scripts.create_mcp_agent_identity_connections --grant
  ```

  It prints the `CUSTOMER_MCP_CONNECTION_ID` / `PRODUCT_MCP_CONNECTION_ID` lines
  to add to `./.env`; then re-register the toolboxes. Under the hood it runs
  `python -m scripts.grant_agent_identity_mcp_role` +
  `azd ai connection create <name> --kind remote-tool --auth-type
  agentic-identity --audience api://<appId>`. Without the connection the toolbox
  registration warns and tool calls return 401. Publishing an agent creates a
  new identity — re-run for it.

  > **IMPORTANT — agent identity rotation + Conditional Access (read this when
  > agentic-identity MCP calls fail).** Every agent **republish/redeploy can
  > rotate the hosted agent's Entra Agent Identity** (new service-principal
  > object id). After each deploy you MUST, for the *new* identity:
  > 1. **Re-grant `Mcp.Invoke`** on every MCP app registration —
  >    `python -m scripts.grant_agent_identity_mcp_role` (auto-discovers the
  >    current identity; covers customer/product/finbot).
  > 2. **Re-add the new identity object id to the Conditional Access policy
  >    `High Risk Agents` (id `974ed75d-23d4-4f1f-af57-c1daf9998505`)
  >    `excludeAgentIdServicePrincipals`.** That policy `blocks` **all** agent
  >    identities (`includeAgentIdServicePrincipals=["All"]`); an identity that
  >    is not excluded cannot mint a token and every agentic-identity MCP tool
  >    call fails with **`Failed to fetch agentic identity access token
  >    (status 400)`** / the A2A task stalls at `auth-required`. Patch it via
  >    Graph beta `PATCH /identity/conditionalAccess/policies/974ed75d…`
  >    (`conditions.clientApplications.excludeAgentIdServicePrincipals`). Changes
  >    take a few minutes to propagate.
  >
  > Symptom decoder: MCP tool calls succeed with a **user** token but fail from
  > the **agent** → identity not excluded from `High Risk Agents` (step 2).
- **Direct path (customer support agent).** `deploy_customer_support_agent`
  resolves the MCP audiences, grants the agent's managed identity the
  `Mcp.Invoke` role, and injects `CUSTOMER_MCP_AUDIENCE` / `PRODUCT_MCP_AUDIENCE`
  so the container attaches an Entra bearer token to its direct MCP calls.

The MCP servers expose `/health` as an unauthenticated custom route, so Container
Apps readiness probes stay green regardless of auth. Turn auth off by setting
`ENTRA_AUTH_ENABLED=false` and re-deploying the MCP servers — the app then runs
anonymously. Requires `az login` with rights to create app registrations and
app-role assignments.

---
## 5c. Finbot SQL MCP server (live Fabric SQL)

An extra MCP server, **`finbot-sql-mcp-server`**, exposes the finbot banking
data held in the **Fabric SQL Database `finbot-data-2`** (customers `Kunden`,
accounts `Konten`, transactions `Transaktionen`, products, monthly reports and
chat conversations). Unlike the customer/product servers it **bundles no data**:
it queries the Fabric SQL DB **live** via the container's user-assigned managed
identity (`id-banking`) using `pyodbc` + ODBC Driver 18. The banking data is
confidential and must **never** be committed to the repo or copied into the
image.

Files: `src/finbot_sql_mcp_server/{server.py,Dockerfile,requirements.txt}`,
`scripts/deploy_finbot_sql_mcp_server.py`, `scripts/register_finbot_sql_toolbox.py`.
Read tools (`list_mandanten`, `get_kunde`, `list_konten`, `get_konto`,
`list_transaktionen`, `list_produkte`, `list_kunde_produkte`,
`list_monatsberichte`, `list_chat_konversationen`, `run_read_query`) plus
human-in-the-loop write tools (`update_konto`, `insert_chat_konversation`).

```bash
# build the image in ACR, deploy the Container App, register the Foundry toolbox
python -m scripts.deploy_finbot_sql_mcp_server --build --register
```

Key overrides: `FINBOT_SQL_SERVER` / `FINBOT_SQL_DATABASE` (default to the
`finbot-data-2` endpoint), `FINBOT_SQL_MI_CLIENT_ID` (auto-resolved from
`AZURE_IDENTITY_NAME`), `FINBOT_SQL_MCP_APP_NAME` (default
`finbot-sql-mcp-server`), `FINBOT_SQL_MCP_PORT` (8094),
`FINBOT_SQL_TOOLBOX_NAME` (default `finbot-sql-tools`). Auth (Entra JWT) and the
toolbox agent-identity connection work exactly like the other MCP servers —
`create_mcp_agent_identity_connections` / `grant_agent_identity_mcp_role` accept
the `finbot` label; set `FINBOT_SQL_MCP_CONNECTION_ID` and re-register with
`python -m scripts.register_finbot_sql_toolbox`. The employee advisory agent
consumes it via the `finbot-sql-tools` toolbox (toggle
`EMPLOYEE_FINBOT_SQL_ENABLED`, default true).

**Fabric prerequisites (do this once).** The managed identity used by the
container (`id-banking`, and any consumer such as the Logic App `finbot-app`)
needs **both** of the following on `finbot-data-2`, or the connection fails:
- a **Fabric workspace role** (Contributor) on the "Banking" workspace — grant
  via Fabric REST `POST /v1/workspaces/<ws>/roleAssignments`; without it a query
  fails with `Login failed … Verify the user has the Read item permission`;
- the T-SQL roles `db_datareader` / `db_datawriter` — grant with
  `ALTER ROLE db_datareader ADD MEMBER [<identity-name>]` (Fabric SQL DBs also
  support `CREATE USER … FROM EXTERNAL PROVIDER`; the read-only lakehouse
  endpoint does **not**).

> **GOTCHA — error `42131 'This SQL database has been disabled'`.** This is
> **not** an MCP/auth bug: the backing **Fabric capacity `fabricbanking` (F32,
> rg-banking)** is **paused/Inactive**. All its SQL DBs go offline until it is
> resumed. Check `az rest GET
> …/providers/Microsoft.Fabric/capacities/fabricbanking?api-version=2023-11-01`
> (or the Fabric `/v1/capacities` API) and resume the capacity before debugging
> anything else. (`az resource list --resource-type Microsoft.Fabric/capacities`
> can wrongly return `[]` — use `az rest` against the ARM provider instead.)

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

### Grant Agent 365 observability permissions (hosted agents)
The Foundry hosted agents export OpenTelemetry spans to the Agent 365 ingestion
service using their **Entra Agent Identity**. Recent observability package
versions require that identity to hold the `Agent365.Observability.OtelWrite`
app role, otherwise export fails with `HTTP 403 … missing the required
'Agent365.Observability.OtelWrite' app role`. Run this once per hosted agent
**after** it is deployed (idempotent):

```bash
# auto-discover the compliance + employee advisory agent identities
python -m scripts.grant_observability_permissions

# or target explicit agent identity object ids (from the 403 message / portal)
python -m scripts.grant_observability_permissions \
    --agent-id <agent-identity-object-id> --agent-id <agent-identity-object-id>
```

Requires `az login` as **Global Administrator** or **Application
Administrator**. Key overrides: `A365_OBSERVABILITY_AGENT_IDS` (comma-separated
object ids, overrides discovery), `AZURE_AI_COMPLIANCE_AGENT_NAME` /
`AZURE_AI_EMPLOYEE_AGENT_NAME` (names used for auto-discovery). Assignments can
take 2–5 minutes to propagate. See https://aka.ms/foundry-grant-agent-365-permissions.

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
python -m scripts.delete_container_apps --purge-auth   # also delete the
                                                      # <app>-mcp-auth Entra
                                                      # app registrations

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
| `ENTRA_AUTH_ENABLED` | manual | validate Entra JWT in-app on MCP servers (default: true) |
| `CUSTOMER_MCP_CONNECTION_ID` / `PRODUCT_MCP_CONNECTION_ID` | manual | AgenticIdentityToken (agent identity) Foundry connection id the toolbox uses to reach the MCP server |
| `AGENT_IDENTITY_MCP_IDS` | manual | Entra Agent Identity object ids to grant `Mcp.Invoke` (overrides auto-discovery) |
| `CUSTOMER_MCP_AUDIENCE` / `PRODUCT_MCP_AUDIENCE` | auto (deploy) | `api://<appId>` audience for direct MCP bearer tokens |
| `AZURE_AI_COMPLIANCE_AGENT_NAME` | manual | default: `compliance-agent` |
| `AZURE_AI_EMPLOYEE_AGENT_NAME` | manual | default: `employee-advisory-agent` |
| `A365_OBSERVABILITY_AGENT_IDS` | manual | agent identity object ids to grant OtelWrite (overrides discovery) |
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

