FROM python:3.13-slim
WORKDIR /app

# Install the Microsoft ODBC Driver 18 for SQL Server (required by pyodbc to
# reach the Fabric SQL database) plus the build deps pyodbc needs.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl gnupg apt-transport-https ca-certificates gcc g++ unixodbc-dev \
    && curl -sSL https://packages.microsoft.com/keys/microsoft.asc \
        | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && echo "deb [arch=amd64,arm64 signed-by=/usr/share/keyrings/microsoft-prod.gpg] https://packages.microsoft.com/debian/12/prod bookworm main" \
        > /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y --no-install-recommends msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

COPY ./src/finbot_sql_mcp_server/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# Only the source is copied — the banking data is queried live from the Fabric
# SQL database via managed identity and is NEVER bundled into the image.
COPY ./src /app/src

ENV FINBOT_SQL_MCP_HOST=0.0.0.0
ENV FINBOT_SQL_MCP_PORT=8094
EXPOSE 8094
CMD ["python", "-m", "src.finbot_sql_mcp_server.server"]
