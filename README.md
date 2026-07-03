

## Components

The ecosystem models two banks — **Bank North** and **Bank South** — that each run
their own agents, MCP servers and data, while sharing some agents across
organisations. Every MCP tool call and agent call is authenticated via Entra ID and
publishes OpenTelemetry to Application Insights. Source lives under `src/`, the
canonical data model under `data/products.md`, and deploy scripts under `scripts/`.

### Agents

| Agent | Owner | Hosting | What it does |
|-------|-------|---------|--------------|
| **Customer support agent** (`src/customer_support_agent`) | Bank South | Azure Container App + web UI | Consumer-facing chat: account balances, transactions, personal details, product discovery and branch info. |
| **Employee advisory agent** (`src/employee_advisory_agent`) | Bank North & Bank South (one instance per bank) | Foundry hosted agent | Internal channel for staff: full product catalogue, read-only customer context and WorkIQ (calendar/documents) while advising customers. |
| **Compliance agent** (`src/compliance_agent`) | Bank North (exposed cross-org to Bank South) | Foundry hosted agent | Regulatory guidance (KYC, AML, sanctions, fraud, escalation). Grounds on the Compliance rules index only; consumed as an A2A service. |

**Dependencies**

- **Customer support agent** → `customer_data_mcp_server`, `product_data_mcp_server`;
  Financial products + Compliance rules search indexes; grounding docs
  `data/knowledge/bank-south.md` and the product knowledge files.
- **Employee advisory agent** → `product_data_mcp_server`, `customer_data_mcp_server`,
  WorkIQ toolbox; Financial products index; grounding docs
  `data/knowledge/*-products.md` and the relevant branch directory.
- **Compliance agent** → Compliance rules index only (no MCP servers); grounds on
  `data/knowledge/compliance-regulatory.md`.

All hosted agents expose A2A and the Responses API through Foundry, and cite their
sources (file name + numbered hierarchy element) in every response.

### MCP servers

Both MCP servers run as Azure Container Apps, authenticate every tool call via Entra ID,
and are registered as Foundry toolboxes so agents can consume them.

| MCP server | What it serves | Tools |
|------------|----------------|-------|
| **Customer data** (`src/customer_data_mcp_server`) | Customers, accounts/holdings, balances and transactions | `list_customers`, `get_customer`, `list_accounts`, `get_account`, `list_transactions`, `get_balance` (read); `update_customer` (write, HITL) |
| **Product data** (`src/product_data_mcp_server`) | Product catalogue + per-customer product holdings and conditions | `list_products`, `get_product`, `list_holdings` (read); `order_product`, `update_holding` (write, HITL) |

**Dependencies**

- **Customer data** → `data/customers.json` and `data/transactions.json`.
- **Product data** → `data/products.md` / `product_catalogue.json`,
  `data/customers.json`, and the product knowledge files under `data/knowledge/`.

Both are built into ACR (`scripts/build_containers.py`), deployed via
`infra/core/host/app.bicep`, and registered as toolboxes
(`register_customer_data_toolbox.py` / `register_product_data_toolbox.py`).

### Container apps & search indexes

- **Container Apps** host the two MCP servers (customer/product data) and the
  customer support agent's web UI. All read configuration from `./.env` (written by
  `azd up`) and pull images from the Azure Container Registry.
- **Azure AI Search indexes** provide grounding over the markdown knowledge base:
  - **Financial products** (`banking-products`) — from `data/products.md` and the
    product knowledge docs; consumed by the customer support and employee advisory
    agents.
  - **Compliance rules** (`banking-compliance`) — from
    `data/knowledge/compliance-regulatory.md`; consumed by the compliance agent (and
    referenced by the customer support agent for guardrails).
- **WorkIQ** is an external MCP server (via Agent 365) registered as a toolbox for the
  employee advisory agent to reach calendar and documents in the user context.

Deployment order (see the sections below): `azd up` → build containers → deploy MCP
servers + register toolboxes → create & ingest search indexes → deploy agents.

## Documentation

### Initial deployment

```bash
azd env set AZURE_LOCATION swedencentral
azd env set AZURE_PRINCIPAL_ID $(az ad signed-in-user show --query id -o tsv)
azd env set AZURE_PRINCIPAL_TYPE User
azd env set SKIP_CONNECTION_CREATION true
azd env set SKIP_ROLE_ASSIGNMENTS true
azd up
```

### Building the MCP server containers

Build both MCP server images (`customer-data-mcp-server` and
`product-data-mcp-server`) in Azure Container Registry. This **only builds** the
images — it does not deploy anything. The target resource group is loaded
automatically from `./.env` (`AZURE_RESOURCE_GROUP`, or `rg-<AZURE_ENV_NAME>`);
the subscription and registry are discovered from it.

```bash
# build with an auto-generated timestamp tag (env from ./.env)
python -m scripts.build_containers

# build with an explicit tag
python -m scripts.build_containers latest

# override the environment name (resource group rg-<name>)
python -m scripts.build_containers --env <AZURE_ENV_NAME>
```

### Deploying the MCP servers

Deploy each MCP server as an Azure Container App via
`infra/core/host/app.bicep`. Pass `--build` to build the image in ACR first, or
omit it to deploy an image already in the registry (uses `:latest`, or the `TAG`
env var). All configuration is sourced from `./.env` (written by `azd up`).

```bash
# customer data MCP server (customers, accounts, balances, transactions)
python -m scripts.deploy_customer_data_mcp_server --build

# product data MCP server (product catalogue + per-customer holdings)
python -m scripts.deploy_product_data_mcp_server --build
```

Each script prints the deployed `…/mcp` URL on success. Override the app name,
port or ingress with `CUSTOMER_MCP_*` / `PRODUCT_MCP_*` (see `.env.example`).

Add `--register` to also publish the server as a Foundry toolbox in the same run
(the agents consume the MCP servers through these toolboxes):

```bash
python -m scripts.deploy_customer_data_mcp_server --build --register
python -m scripts.deploy_product_data_mcp_server  --build --register
```

### Creating and populating the search indexes

Create the two Azure AI Search indexes — **Financial products**
(`banking-products`) and **Compliance rules** (`banking-compliance`) — then
ingest the knowledge base (`data/products.md` + `data/knowledge/*.md`). Both
read `./.env`.

```bash
# create/update the two index schemas (HNSW vector + semantic search)
python -m scripts.create_search_indexes

# parse the markdown, embed (if AZURE_OPENAI_ENDPOINT is set) and upload
python -m scripts.ingest_knowledge
```

### Registering the Foundry toolboxes

The MCP-server toolboxes are registered automatically with `--register` above.
You can also register any toolbox on its own (idempotent, re-runnable):

```bash
# customer / product MCP servers as toolboxes
python -m scripts.register_customer_data_toolbox
python -m scripts.register_product_data_toolbox

# WorkIQ (Microsoft Agent 365) MCP server as a toolbox (employee agent)
python -m scripts.register_workiq_toolbox
```

Each prints the consumer endpoint
`{project}/toolboxes/{toolbox}/mcp?api-version=v1`. Override the toolbox name or
MCP URL with `CUSTOMER_TOOLBOX_NAME` / `PRODUCT_TOOLBOX_NAME` /
`WORKIQ_TOOLBOX_NAME` and `*_MCP_URL` (see `.env.example`).

#### WorkIQ authentication (OAuth identity passthrough)

The WorkIQ (Agent 365) MCP server backs the employee advisory agent's calendar
and document capabilities. Setting it up is more involved than the customer /
product toolboxes because WorkIQ is a governed Microsoft 365 service that runs in
the **user's own context**, so it needs a real delegated-OAuth flow rather than a
shared key.

**Prerequisites**

- A **Microsoft 365 Copilot** licence on the tenant (required to call WorkIQ).
- The **Agent 365 Tools** service principal in the tenant (appId
  `ea9ffc3e-8a23-4a7d-836d-234d7c7565c1`). Verify with
  `az ad sp show --id ea9ffc3e-8a23-4a7d-836d-234d7c7565c1`. If missing, an admin
  provisions it with
  `python -m scripts.create_agent365_tools_service_principals`.
- **Tenant admin** rights to grant admin consent in step 1.

**Why OAuth passthrough (and not a token)?** Foundry refuses to forward a
Microsoft-audience bearer token to the WorkIQ endpoint
(`Cannot pass Microsoft token to untrusted MCP endpoint`), so a "custom keys"
connection cannot work. WorkIQ must use a custom Entra app you own. Also note
there is **no** `McpServers.WorkIQ.All` scope or `mcp_WorkIQTools` server — WorkIQ
is split into granular capabilities. The employee agent defaults to **Calendar**
(`mcp_CalendarTools` / `McpServers.Calendar.All`); override with
`WORKIQ_MCP_SERVER` / `WORKIQ_SCOPE` (see `.env.example`) for Mail,
OneDrive/SharePoint, etc.

**Step 1 — create the custom OAuth app**

```bash
python -m scripts.setup_workiq_oauth_app
```

This creates (idempotently) an Entra app registration
(`WORKIQ_OAUTH_APP_NAME`, default `banking-workiq-oauth`), adds the WorkIQ
delegated permission on the Agent 365 Tools app, grants tenant admin consent,
mints a client secret, and prints the exact connection values for step 2. The
client secret is shown once — copy it now.

**Step 2 — create the Foundry connection**

In the [Foundry portal](https://ai.azure.com), open your project and go to
**Tools → Add tool → Custom → MCP → OAuth Identity Passthrough → Custom OAuth**.
Create a connection named `workiq-connection` with the values printed in step 1:

| Field | Value |
| --- | --- |
| Connection name | `workiq-connection` |
| MCP server URL | the tenant-scoped WorkIQ URL (printed by `register_workiq_toolbox`) |
| Client ID | the app's `appId` |
| Client secret | the secret from step 1 |
| Auth URL | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/authorize` |
| Token URL | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token` |
| Refresh URL | `https://login.microsoftonline.com/{tenantId}/oauth2/v2.0/token` |
| Scopes | `ea9ffc3e-8a23-4a7d-836d-234d7c7565c1/McpServers.Calendar.All offline_access` |

Save the connection. Foundry then shows a **redirect URL** — copy it and add it to
the app registration under **Authentication → Add a platform → Web → Redirect
URIs** (Entra admin center), so Foundry can complete the OAuth handshake. Keep
`offline_access` in the scopes so tokens refresh automatically.

**Step 3 — register the toolbox against the connection**

```bash
WORKIQ_CONNECTION_NAME=workiq-connection python -m scripts.register_workiq_toolbox
```

The script resolves the connection by name (or set `WORKIQ_CONNECTION_ID`
directly) and attaches it to the `workiq-tools` toolbox. It prints the resolved
`OAuth connection:` line on success.

**First use — per-user consent.** The first time each employee invokes WorkIQ,
the agent returns an `oauth_consent_request` with a consent link; after the user
signs in and consents once, subsequent calls succeed silently.

**Troubleshooting**

| Symptom | Cause | Fix |
| --- | --- | --- |
| `400 … TenantIdInvalid` on `tools/list` | MCP URL missing the tenant segment | Ensure `AZURE_TENANT_ID` is set; `register_workiq_toolbox` builds `…/agents/tenants/{tenantId}/servers/…` |
| `401 Unauthorized` from the WorkIQ endpoint | No OAuth connection attached, or the app lacks consent / the redirect URL | Complete steps 1–3; confirm admin consent and the redirect URL are in place |
| Scope not found error from `setup_workiq_oauth_app` | `WORKIQ_SCOPE` isn't exposed by the Agent 365 Tools app | Pick a valid capability scope (the script lists the available ones) |

### Deploying agents

Prerequisites: the MCP servers are deployed and registered as toolboxes, the
WorkIQ toolbox is registered, and the search indexes are created and ingested
(the steps above).

**Compliance agent** (Bank North, Foundry hosted agent — index-only, cross-org
A2A service). Grounds on the Compliance rules index:

```bash
python -m scripts.deploy_compliance_agent --build
```

**Employee advisory agent** (Foundry hosted agent — one instance per bank).
Consumes the Financial products index plus the product / customer / WorkIQ
toolboxes:

```bash
python -m scripts.deploy_employee_advisory_agent --build
```

**Customer support agent** (Bank South, Azure Container App + web UI). Reaches
the customer / product MCP servers and grounds on both search indexes. Pass
`--build` to build the image in ACR first:

```bash
python -m scripts.deploy_customer_support_agent --build
```

It prints the public web-UI URL on success.

**Deploy all three at once** (assumes the prerequisites above). `--build`
rebuilds the container-app image; `--only <name>` limits the run to
`compliance`, `employee` or `customer-support`:

```bash
python -m scripts.deploy_banking_agents --build
python -m scripts.deploy_banking_agents --only customer-support --build
```

### Granting Agent 365 observability permissions

The Foundry hosted agents (compliance, employee advisory) export OpenTelemetry
spans to the Agent 365 ingestion service using their **Entra Agent Identity**.
Recent observability package versions require that identity to hold the
`Agent365.Observability.OtelWrite` app role — without it, telemetry export fails
with `HTTP 403 … missing the required 'Agent365.Observability.OtelWrite' app
role`. Run this once per hosted agent **after** it is deployed (idempotent):

```bash
# auto-discover the compliance + employee advisory agent identities
python -m scripts.grant_observability_permissions

# or target explicit agent identity object ids (from the 403 message / portal)
python -m scripts.grant_observability_permissions \
  --agent-id <agent-identity-object-id> --agent-id <agent-identity-object-id>
```

Requires `az login` as a **Global Administrator** or **Application
Administrator** (needed to create app role assignments). Auto-discovery matches
the hosted-agent names (`AZURE_AI_COMPLIANCE_AGENT_NAME` /
`AZURE_AI_EMPLOYEE_AGENT_NAME`) against the tenant's agent identities; override
with `A365_OBSERVABILITY_AGENT_IDS` (comma-separated object ids) or `--agent-id`.
Assignments can take 2–5 minutes to propagate. See
[the Foundry docs](https://aka.ms/foundry-grant-agent-365-permissions).

### Cleaning up

Delete the Foundry hosted agents (and optionally their toolboxes), the Container
Apps, and the search indexes:

```bash
# Foundry hosted agents (compliance, employee advisory); add --toolboxes to also
# remove the customer/product/WorkIQ toolboxes
python -m scripts.delete_agents
python -m scripts.delete_agents --toolboxes

# Container Apps (customer support agent + customer/product MCP servers)
python -m scripts.delete_container_apps

# the two Azure AI Search indexes (schema + data)
python -m scripts.delete_search_indexes

# tear down all Azure resources
azd down
```

