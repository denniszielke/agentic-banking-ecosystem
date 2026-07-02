

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

### Deploying agents

