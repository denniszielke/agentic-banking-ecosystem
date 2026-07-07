FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock ./

# override nexus pypi with official pyi.
RUN UV_INDEX_URL=https://pypi.org/simple/ uv sync --no-dev

COPY src/ src/
COPY data/ data/

EXPOSE 8000

# Use the package entrypoint (not `fastmcp run`) so authentication is enforced:
# main() refuses to start a network transport unless auth is configured via
# MCP_JWT_* or MCP_AUTH_TOKEN. Cloud Run injects $PORT; main() honours it.
ENV MCP_TRANSPORT=streamable-http
CMD ["uv", "run", "fastmcp", "run", "src/finance_mcp/server.py:mcp", "--transport", "streamable-http", "--host", "0.0.0.0", "--port", "8000"]
