"""Finbot SQL MCP server for the agentic banking ecosystem.

Exposes the finbot banking data — customers (``finbot_kunden``), accounts
(``finbot_konten``), transactions (``finbot_transaktionen``), products
(``finbot_produkte`` / ``finbot_kunde_produkte``), monthly reports
(``finbot_monatsberichte``) and chat conversations
(``finbot_chat_konversationen``) — over the Model Context Protocol so that
Foundry agents can read and (human-in-the-loop) write banking data.

Unlike the customer/product MCP servers, this server has **no bundled data**.
It queries the **Fabric SQL Database ``finbot-data-2`` live** via the container's
**user-assigned managed identity** (``id-banking``) — the banking data is
confidential and is never copied into the image or the repository.

Connection details come from the environment:

    FINBOT_SQL_SERVER        Fabric SQL server FQDN, e.g.
                             ``xxx.database.fabric.microsoft.com,1433``
    FINBOT_SQL_DATABASE      database name, e.g. ``finbot-data-2-<guid>``
    FINBOT_SQL_MI_CLIENT_ID  client id of the user-assigned managed identity to
                             authenticate with (falls back to
                             DefaultAzureCredential when unset — local dev / az)

Run it with::

    python -m src.finbot_sql_mcp_server.server

It serves the streamable-HTTP MCP transport on ``http://127.0.0.1:8094/mcp`` by
default (override with ``FINBOT_SQL_MCP_HOST`` / ``FINBOT_SQL_MCP_PORT``).
"""

from __future__ import annotations

import datetime as _dt
import os
import struct
from decimal import Decimal
from typing import Any, Optional

import pyodbc
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

_HOST = os.getenv("FINBOT_SQL_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("FINBOT_SQL_MCP_PORT", "8094"))

_SERVER = os.getenv("FINBOT_SQL_SERVER", "").strip()
_DATABASE = os.getenv("FINBOT_SQL_DATABASE", "").strip()
_MI_CLIENT_ID = os.getenv("FINBOT_SQL_MI_CLIENT_ID", "").strip()

# ODBC connection attribute id for an Entra access token (mssql-python / msodbcsql).
_SQL_COPT_SS_ACCESS_TOKEN = 1256
_TOKEN_RESOURCE = "https://database.windows.net/.default"
_DRIVER = os.getenv("FINBOT_SQL_ODBC_DRIVER", "ODBC Driver 18 for SQL Server")

# Maximum rows any single query/tool returns, to protect the agent context.
_MAX_ROWS = int(os.getenv("FINBOT_SQL_MAX_ROWS", "500"))


# --------------------------------------------------------------------------- #
# Database access (live, managed-identity authenticated)
# --------------------------------------------------------------------------- #

def _access_token() -> bytes:
    """Acquire an Entra access token for Azure SQL and pack it for ODBC.

    Uses the container's user-assigned managed identity when
    ``FINBOT_SQL_MI_CLIENT_ID`` is set, otherwise ``DefaultAzureCredential``
    (local dev / ``az login``).
    """
    if _MI_CLIENT_ID:
        from azure.identity import ManagedIdentityCredential

        cred = ManagedIdentityCredential(client_id=_MI_CLIENT_ID)
    else:
        from azure.identity import DefaultAzureCredential

        cred = DefaultAzureCredential()
    raw = cred.get_token(_TOKEN_RESOURCE).token.encode("utf-16-le")
    return struct.pack(f"<I{len(raw)}s", len(raw), raw)


def _connect() -> pyodbc.Connection:
    """Open a fresh, token-authenticated connection to the Fabric SQL DB."""
    if not _SERVER or not _DATABASE:
        raise RuntimeError(
            "FINBOT_SQL_SERVER and FINBOT_SQL_DATABASE must be set to reach the "
            "Fabric SQL database."
        )
    conn_str = (
        f"Driver={{{_DRIVER}}};Server={_SERVER};Database={_DATABASE};"
        "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
    )
    token = _access_token()
    return pyodbc.connect(conn_str, attrs_before={_SQL_COPT_SS_ACCESS_TOKEN: token})


def _jsonable(value: Any) -> Any:
    """Convert SQL types to JSON-serialisable Python values."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (_dt.datetime, _dt.date, _dt.time)):
        return value.isoformat()
    if isinstance(value, (bytes, bytearray)):
        return value.hex()
    return value


def _rows(sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
    """Run a parameterised SELECT and return up to ``_MAX_ROWS`` rows as dicts."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        columns = [c[0] for c in cur.description]
        out: list[dict[str, Any]] = []
        for row in cur.fetchmany(_MAX_ROWS):
            out.append({col: _jsonable(val) for col, val in zip(columns, row)})
        return out


def _execute(sql: str, params: tuple[Any, ...] = ()) -> int:
    """Run a parameterised DML statement and return the affected row count."""
    with _connect() as conn:
        cur = conn.cursor()
        cur.execute(sql, params)
        affected = cur.rowcount
        conn.commit()
        return affected


# --------------------------------------------------------------------------- #
# Auth (FastMCP Entra JWT verifier — identical pattern to the other MCP servers)
# --------------------------------------------------------------------------- #

def _build_auth():
    """Build the FastMCP Microsoft Entra ID JWT auth provider, or ``None``.

    Enabled only when ``ENTRA_AUTH_ENABLED`` is truthy and both the API audience
    (``MCP_AUTH_CLIENT_ID``) and ``AZURE_TENANT_ID`` are set. Validates incoming
    Entra access tokens (issuer, audience, JWKS signature) in-app — no Container
    Apps Easy Auth, no client secret. No scope required, so both delegated (user)
    and app-only (managed identity) tokens are accepted.
    """
    enabled = os.getenv("ENTRA_AUTH_ENABLED", "false").strip().lower() in {
        "1", "true", "yes", "on",
    }
    client_id = os.getenv("MCP_AUTH_CLIENT_ID", "").strip()
    tenant_id = os.getenv("AZURE_TENANT_ID", "").strip()
    if not (enabled and client_id and tenant_id):
        return None
    from fastmcp.server.auth import RemoteAuthProvider
    from fastmcp.server.auth.providers.azure import AzureJWTVerifier
    from pydantic import AnyHttpUrl

    base_url = os.getenv("MCP_PUBLIC_BASE_URL", "").strip() or f"http://{_HOST}:{_PORT}"
    verifier = AzureJWTVerifier(client_id=client_id, tenant_id=tenant_id)
    return RemoteAuthProvider(
        token_verifier=verifier,
        authorization_servers=[
            AnyHttpUrl(f"https://login.microsoftonline.com/{tenant_id}/v2.0")
        ],
        base_url=base_url,
    )


mcp = FastMCP(
    name="finbot_sql",
    instructions=(
        "Finbot banking data held in a Fabric SQL database. Use these tools to "
        "look up customers (Kunden), accounts (Konten), transactions "
        "(Transaktionen), products (Produkte), a customer's product holdings "
        "and monthly reports (Monatsberichte), and to read/write chat "
        "conversations. The data is multi-tenant: every entity is scoped by "
        "'id_mandant', so always pass the mandant id together with the entity "
        "id. All monetary values are in EUR. Customer data is confidential — "
        "only surface details for the customer in context. The write tools "
        "('update_konto', 'insert_chat_konversation') require explicit human "
        "approval (human-in-the-loop): call once with confirm=false to preview, "
        "then again with confirm=true once approved."
    ),
    auth=_build_auth(),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    """Readiness probe endpoint — returns 200 OK without touching the database."""
    return JSONResponse({"status": "ok"})


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def list_mandanten() -> list[dict[str, Any]]:
    """List all tenants (Mandanten) — id, name and region.

    Returns one row per mandant from ``finbot_mandanten``.
    """
    return _rows(
        "SELECT id_mandant, nam_mandant, bez_region FROM dbo.finbot_mandanten "
        "ORDER BY id_mandant"
    )


@mcp.tool()
def get_kunde(id_mandant: str, id_kunde: str) -> dict[str, Any]:
    """Get a single customer's full profile.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant.

    Returns the customer's profile fields, or an ``error`` field if no customer
    matches.
    """
    rows = _rows(
        "SELECT * FROM dbo.finbot_kunden WHERE id_mandant = ? AND id_kunde = ?",
        (id_mandant, id_kunde),
    )
    if not rows:
        return {"error": f"No customer matched id_mandant={id_mandant}, id_kunde={id_kunde}."}
    return rows[0]


@mcp.tool()
def list_konten(id_mandant: str, id_kunde: str) -> list[dict[str, Any]]:
    """List the accounts (Konten) of a customer.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant.

    Each row includes the account id, type, IBAN, balance (saldo), interest
    rate, overdraft limit, currency and status.
    """
    return _rows(
        "SELECT * FROM dbo.finbot_konten WHERE id_mandant = ? AND id_kunde = ? "
        "ORDER BY id_konto",
        (id_mandant, id_kunde),
    )


@mcp.tool()
def get_konto(id_mandant: str, id_konto: str) -> dict[str, Any]:
    """Get a single account (Konto) by its id.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_konto: Account id (part of the primary key).

    Returns the account row, or an ``error`` field if none matches.
    """
    rows = _rows(
        "SELECT * FROM dbo.finbot_konten WHERE id_mandant = ? AND id_konto = ?",
        (id_mandant, id_konto),
    )
    if not rows:
        return {"error": f"No account matched id_mandant={id_mandant}, id_konto={id_konto}."}
    return rows[0]


@mcp.tool()
def list_transaktionen(
    id_mandant: str,
    id_konto: Optional[str] = None,
    id_kunde: Optional[str] = None,
    datum_von: Optional[str] = None,
    datum_bis: Optional[str] = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """List transactions for an account or across a customer's accounts.

    Provide ``id_konto`` (transactions on one account) or ``id_kunde``
    (transactions across every account of that customer). ``id_mandant`` is
    always required. If both id_konto and id_kunde are given, id_konto wins.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_konto: Optional account id.
        id_kunde: Optional customer id.
        datum_von: Optional inclusive lower bound date ``YYYY-MM-DD``.
        datum_bis: Optional inclusive upper bound date ``YYYY-MM-DD``.
        limit: Maximum rows to return (default 100, capped by the server).

    Transactions are returned newest first with amount, category, type,
    counterparty and purpose.
    """
    where = ["id_mandant = ?"]
    params: list[Any] = [id_mandant]
    if id_konto:
        where.append("id_konto = ?")
        params.append(id_konto)
    elif id_kunde:
        where.append("id_kunde = ?")
        params.append(id_kunde)
    else:
        return [{"error": "Provide either 'id_konto' or 'id_kunde' (plus id_mandant)."}]
    if datum_von:
        where.append("datum >= ?")
        params.append(datum_von)
    if datum_bis:
        where.append("datum <= ?")
        params.append(datum_bis)
    top = max(1, min(int(limit), _MAX_ROWS))
    sql = (
        f"SELECT TOP {top} * FROM dbo.finbot_transaktionen "
        f"WHERE {' AND '.join(where)} ORDER BY datum DESC"
    )
    return _rows(sql, tuple(params))


@mcp.tool()
def list_produkte(id_mandant: str) -> list[dict[str, Any]]:
    """List the product catalogue (Produkte) of a tenant.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.

    Each row includes the product id, name, category, description, monthly cost
    and target group.
    """
    return _rows(
        "SELECT * FROM dbo.finbot_produkte WHERE id_mandant = ? ORDER BY id_produkt",
        (id_mandant,),
    )


@mcp.tool()
def list_kunde_produkte(id_mandant: str, id_kunde: str) -> list[dict[str, Any]]:
    """List the products a customer holds (Kunde-Produkte).

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant.

    Each row includes the product id/name, contract date, status and monthly
    contribution.
    """
    return _rows(
        "SELECT * FROM dbo.finbot_kunde_produkte WHERE id_mandant = ? AND id_kunde = ? "
        "ORDER BY id_produkt",
        (id_mandant, id_kunde),
    )


@mcp.tool()
def get_kunde_produkt(id_mandant: str, id_kunde: str, id_produkt: str) -> dict[str, Any]:
    """Get a single customer-product assignment by its primary key.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant, e.g. ``K000006``.
        id_produkt: Product id, e.g. ``PRD001``.

    Returns the record including status, contract date and monthly contribution,
    or an ``error`` field if no record matches.
    """
    rows = _rows(
        "SELECT * FROM dbo.finbot_kunde_produkte "
        "WHERE id_mandant = ? AND id_kunde = ? AND id_produkt = ?",
        (id_mandant, id_kunde, id_produkt),
    )
    if not rows:
        return {
            "error": (
                f"No record matched (id_mandant={id_mandant}, "
                f"id_kunde={id_kunde}, id_produkt={id_produkt})."
            )
        }
    return rows[0]


@mcp.tool()
def list_monatsberichte(
    id_mandant: str, id_kunde: str, limit: int = 24
) -> list[dict[str, Any]]:
    """List a customer's monthly financial reports (Monatsberichte).

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant.
        limit: Maximum number of months to return (default 24).

    Returns income/expense breakdowns per month, newest first.
    """
    top = max(1, min(int(limit), _MAX_ROWS))
    return _rows(
        f"SELECT TOP {top} * FROM dbo.finbot_monatsberichte "
        "WHERE id_mandant = ? AND id_kunde = ? ORDER BY monat DESC",
        (id_mandant, id_kunde),
    )


@mcp.tool()
def list_chat_konversationen(
    id_mandant: str, id_kunde: str, limit: int = 50
) -> list[dict[str, Any]]:
    """List a customer's chat conversations (Chat-Konversationen).

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant.
        limit: Maximum conversations to return (default 50).

    Returns the question, bot answer, category and satisfaction per turn.
    """
    top = max(1, min(int(limit), _MAX_ROWS))
    return _rows(
        f"SELECT TOP {top} * FROM dbo.finbot_chat_konversationen "
        "WHERE id_mandant = ? AND id_kunde = ? ORDER BY [timestamp] DESC",
        (id_mandant, id_kunde),
    )


# Statement prefixes / keywords rejected by the read-only query tool.
_READ_ONLY_BLOCK = (
    "insert", "update", "delete", "merge", "drop", "alter", "create",
    "truncate", "exec", "execute", "grant", "revoke", "sp_", "xp_",
)


@mcp.tool()
def run_read_query(sql: str) -> list[dict[str, Any]]:
    """Run an ad-hoc **read-only** SQL query against the finbot database.

    Only a single ``SELECT`` (or ``WITH ... SELECT``) statement is allowed; any
    data-modifying or DDL statement is rejected. Results are capped by the
    server's row limit. Use this for flexible lookups the typed tools don't
    cover; prefer the typed tools when they fit.

    Args:
        sql: A single read-only SELECT statement.
    """
    stripped = sql.strip().rstrip(";").strip()
    lowered = stripped.lower()
    if not (lowered.startswith("select") or lowered.startswith("with")):
        return [{"error": "Only a single SELECT/WITH statement is allowed."}]
    if ";" in stripped:
        return [{"error": "Multiple statements are not allowed."}]
    if any(tok in lowered for tok in _READ_ONLY_BLOCK):
        return [{"error": "Data-modifying or DDL keywords are not allowed in run_read_query."}]
    return _rows(stripped)


# --------------------------------------------------------------------------- #
# Write tools (human-in-the-loop)
# --------------------------------------------------------------------------- #

_EDITABLE_KONTO_FIELDS = {"saldo", "status", "dispo_limit", "zinssatz"}


@mcp.tool()
def update_konto(
    id_mandant: str,
    id_konto: str,
    fields: dict[str, Any],
    confirm: bool = False,
) -> dict[str, Any]:
    """Update an account (write — human-in-the-loop).

    This is a **write** operation and requires explicit human approval. Call it
    first with ``confirm=false`` (default) to receive a preview of the proposed
    change; present that preview to the human and only re-call with
    ``confirm=true`` once approval has been granted. Only ``saldo``, ``status``,
    ``dispo_limit`` and ``zinssatz`` may be changed.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_konto: Account id to update (part of the primary key).
        fields: Mapping of field name to new value (subset of the editable set).
        confirm: Set to ``true`` only after a human approved the preview.
    """
    invalid = set(fields) - _EDITABLE_KONTO_FIELDS
    if invalid:
        return {
            "error": f"Fields not editable: {sorted(invalid)}.",
            "editable_fields": sorted(_EDITABLE_KONTO_FIELDS),
        }
    if not fields:
        return {"error": "No fields supplied to update."}

    current = _rows(
        "SELECT * FROM dbo.finbot_konten WHERE id_mandant = ? AND id_konto = ?",
        (id_mandant, id_konto),
    )
    if not current:
        return {"error": f"No account matched id_mandant={id_mandant}, id_konto={id_konto}."}
    before = current[0]
    changes = {k: {"from": before.get(k), "to": v} for k, v in fields.items()}

    if not confirm:
        return {
            "status": "pending_approval",
            "id_mandant": id_mandant,
            "id_konto": id_konto,
            "requires": "human approval (call again with confirm=true)",
            "changes": changes,
        }

    set_cols = ", ".join(f"[{k}] = ?" for k in fields)
    params = tuple(fields.values()) + (id_mandant, id_konto)
    affected = _execute(
        f"UPDATE dbo.finbot_konten SET {set_cols} "
        "WHERE id_mandant = ? AND id_konto = ?",
        params,
    )
    return {"status": "committed", "rows_affected": affected, "changes": changes}


@mcp.tool()
def insert_chat_konversation(
    id_mandant: str,
    id_konversation: str,
    id_kunde: str,
    frage_kunde: str,
    antwort_bot: str,
    kanal: Optional[str] = None,
    typ: Optional[str] = None,
    kategorie: Optional[str] = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Insert a new chat conversation record (write — human-in-the-loop).

    Logs a customer interaction into ``finbot_chat_konversationen``. Requires
    explicit human approval: call with ``confirm=false`` to preview, then
    ``confirm=true`` to commit. ``id_mandant`` + ``id_konversation`` form the
    primary key and must be unique.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_konversation: Unique conversation id within the tenant.
        id_kunde: Customer id the conversation belongs to.
        frage_kunde: The customer's question.
        antwort_bot: The bot's answer.
        kanal: Optional channel (e.g. ``app``, ``web``).
        typ: Optional conversation type.
        kategorie: Optional category.
        confirm: Set to ``true`` only after a human approved the preview.
    """
    record = {
        "id_mandant": id_mandant,
        "id_konversation": id_konversation,
        "id_kunde": id_kunde,
        "frage_kunde": frage_kunde,
        "antwort_bot": antwort_bot,
        "kanal": kanal,
        "typ": typ,
        "kategorie": kategorie,
    }

    if not confirm:
        return {
            "status": "pending_approval",
            "requires": "human approval (call again with confirm=true)",
            "record": record,
        }

    cols = [k for k, v in record.items() if v is not None]
    placeholders = ", ".join("?" for _ in cols)
    col_list = ", ".join(f"[{c}]" for c in cols)
    params = tuple(record[c] for c in cols)
    try:
        affected = _execute(
            f"INSERT INTO dbo.finbot_chat_konversationen ({col_list}) "
            f"VALUES ({placeholders})",
            params,
        )
    except pyodbc.IntegrityError:
        return {
            "error": (
                f"A conversation with id_mandant={id_mandant}, "
                f"id_konversation={id_konversation} already exists."
            )
        }
    return {"status": "committed", "rows_affected": affected, "record": record}


_ALLOWED_PRODUKT_STATUS = {"aktiv", "gekuendigt", "ruhend"}
_KUNDE_PRODUKTE_TABLE = "dbo.finbot_kunde_produkte"


@mcp.tool()
def write_kunde_produkt(
    id_mandant: str,
    id_kunde: str,
    id_produkt: str,
    bez_produkt: Optional[str] = None,
    abschluss_datum: Optional[str] = None,
    status: Optional[str] = None,
    monatl_beitrag: Optional[float] = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Order a product for a customer — insert a customer-product assignment
    (write — human-in-the-loop).

    Inserts a new record into ``finbot_kunde_produkte``. The primary key is
    (id_mandant, id_kunde, id_produkt). If it already exists no insert is
    performed. Requires explicit human approval: call with ``confirm=false``
    to preview, then ``confirm=true`` to commit.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant, e.g. ``K000006``.
        id_produkt: Product id, e.g. ``PRD001``.
        bez_produkt: Product name (optional), e.g. ``VR-MeinKonto``.
        abschluss_datum: Contract start date ``YYYY-MM-DD`` (optional).
        status: Contract status — ``aktiv``, ``gekuendigt`` or ``ruhend`` (optional).
        monatl_beitrag: Monthly contribution in EUR (optional).
        confirm: Set to ``true`` only after a human approved the preview.
    """
    for name, val in (
        ("id_mandant", id_mandant), ("id_kunde", id_kunde), ("id_produkt", id_produkt)
    ):
        if not val or not str(val).strip():
            return {"error": f"Required field '{name}' must not be empty."}

    if status is not None and status not in _ALLOWED_PRODUKT_STATUS:
        return {"error": f"Invalid status '{status}'. Allowed: {sorted(_ALLOWED_PRODUKT_STATUS)}."}

    record: dict[str, Any] = {
        "id_mandant": id_mandant,
        "id_kunde": id_kunde,
        "id_produkt": id_produkt,
    }
    if bez_produkt is not None:
        record["bez_produkt"] = bez_produkt
    if abschluss_datum is not None:
        record["abschluss_datum"] = abschluss_datum
    if status is not None:
        record["status"] = status
    if monatl_beitrag is not None:
        record["monatl_beitrag"] = float(monatl_beitrag)

    if not confirm:
        return {
            "status": "pending_approval",
            "requires": "human approval (call again with confirm=true)",
            "record": record,
        }

    existing = _rows(
        f"SELECT 1 FROM {_KUNDE_PRODUKTE_TABLE} "
        "WHERE id_mandant = ? AND id_kunde = ? AND id_produkt = ?",
        (id_mandant, id_kunde, id_produkt),
    )
    if existing:
        return {
            "error": (
                f"Record already exists: (id_mandant={id_mandant}, "
                f"id_kunde={id_kunde}, id_produkt={id_produkt}). No insert performed."
            )
        }

    cols = list(record.keys())
    col_list = ", ".join(f"[{c}]" for c in cols)
    placeholders = ", ".join("?" for _ in cols)
    params = tuple(record[c] for c in cols)
    try:
        affected = _execute(
            f"INSERT INTO {_KUNDE_PRODUKTE_TABLE} ({col_list}) VALUES ({placeholders})",
            params,
        )
    except pyodbc.IntegrityError as exc:
        return {"error": f"Insert failed (integrity): {exc}"}
    return {"status": "committed", "rows_affected": affected, "record": record}


@mcp.tool()
def kuendige_produkt(
    id_mandant: str,
    id_kunde: str,
    id_produkt: str,
    confirm: bool = False,
) -> dict[str, Any]:
    """Cancel (kündigen) a customer-product assignment (write — human-in-the-loop).

    Sets the status of an existing record in ``finbot_kunde_produkte`` to
    ``gekuendigt``. Requires explicit human approval: call with ``confirm=false``
    to preview, then ``confirm=true`` to commit.

    If the record does not exist or is already ``gekuendigt`` an error is returned.

    Args:
        id_mandant: Tenant id, e.g. ``M001``.
        id_kunde: Customer id within the tenant, e.g. ``K000006``.
        id_produkt: Product id, e.g. ``PRD001``.
        confirm: Set to ``true`` only after a human approved the preview.
    """
    for name, val in (
        ("id_mandant", id_mandant), ("id_kunde", id_kunde), ("id_produkt", id_produkt)
    ):
        if not val or not str(val).strip():
            return {"error": f"Required field '{name}' must not be empty."}

    rows = _rows(
        f"SELECT status FROM {_KUNDE_PRODUKTE_TABLE} "
        "WHERE id_mandant = ? AND id_kunde = ? AND id_produkt = ?",
        (id_mandant, id_kunde, id_produkt),
    )
    if not rows:
        return {
            "error": (
                f"Record not found: (id_mandant={id_mandant}, "
                f"id_kunde={id_kunde}, id_produkt={id_produkt})."
            )
        }
    current_status = rows[0].get("status")
    if current_status == "gekuendigt":
        return {
            "error": (
                f"Record is already 'gekuendigt': (id_mandant={id_mandant}, "
                f"id_kunde={id_kunde}, id_produkt={id_produkt})."
            )
        }

    if not confirm:
        return {
            "status": "pending_approval",
            "requires": "human approval (call again with confirm=true)",
            "transition": {"from": current_status, "to": "gekuendigt"},
            "id_mandant": id_mandant,
            "id_kunde": id_kunde,
            "id_produkt": id_produkt,
        }

    affected = _execute(
        f"UPDATE {_KUNDE_PRODUKTE_TABLE} SET [status] = 'gekuendigt' "
        "WHERE id_mandant = ? AND id_kunde = ? AND id_produkt = ?",
        (id_mandant, id_kunde, id_produkt),
    )
    return {
        "status": "committed",
        "rows_affected": affected,
        "id_mandant": id_mandant,
        "id_kunde": id_kunde,
        "id_produkt": id_produkt,
        "new_status": "gekuendigt",
    }


def main() -> None:
    """Entry point — serve the finbot SQL data over streamable-HTTP MCP."""
    mcp.run(
        transport="http",
        host=_HOST,
        port=_PORT,
        host_origin_protection=False,
    )


if __name__ == "__main__":
    main()
