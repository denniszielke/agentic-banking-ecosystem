"""Customer data MCP server for the agentic banking ecosystem.

Exposes a bank's **customer** master data — customers, their product holdings
(accounts and credit cards) and the transactions on each holding — over the
Model Context Protocol so that the banking agents (``customer_support_agent``,
``employee_advisory_agent``, ``credit_card_agent``) can answer questions such as
"what is my balance?" or "list my transactions from last month".

All data is **synthetic** and loaded once at startup from the shared ``data/``
directory at the repository root (``customers.json`` + ``transactions.json``),
which is generated deterministically by ``scripts/generate_data.py``. There is
no database — the JSON files *are* the source of truth, mirroring the real-world
boundary where customer data is sensitive and only ever reachable through this
controlled, Entra ID authenticated MCP surface.

The canonical entities and tool surface are defined in ``data/products.md``.

Run it with::

    python -m src.customer_data_mcp_server.server

It serves the streamable-HTTP MCP transport on ``http://127.0.0.1:8092/mcp`` by
default (override with ``CUSTOMER_MCP_HOST`` / ``CUSTOMER_MCP_PORT``).
"""

from __future__ import annotations

import copy
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import json

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse


def _data_dir() -> Path:
    """Resolve the shared ``data/`` directory (repo root or ``BANK_DATA_DIR``)."""
    override = os.getenv("BANK_DATA_DIR")
    if override:
        return Path(override)
    # server.py -> customer_data_mcp_server -> src -> <repo root>/data
    return Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=1)
def _customers() -> list[dict[str, Any]]:
    """Load and cache the customers (with nested product holdings)."""
    with (_data_dir() / "customers.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)["customers"]


@lru_cache(maxsize=1)
def _transactions_tree() -> list[dict[str, Any]]:
    """Load and cache the customer -> products -> transactions tree."""
    with (_data_dir() / "transactions.json").open("r", encoding="utf-8") as fh:
        return json.load(fh)["customers"]


def _customer_summary(customer: dict[str, Any]) -> dict[str, Any]:
    """Return the customer's core fields (without nested holdings)."""
    return {k: v for k, v in customer.items() if k != "products"}


def _find_customer(customer_id: str) -> Optional[dict[str, Any]]:
    cid = customer_id.strip().upper()
    return next((c for c in _customers() if c["customer_id"].upper() == cid), None)


def _find_account(account_id: str) -> Optional[dict[str, Any]]:
    """Return a (holding, customer_id) view for the given account id."""
    aid = account_id.strip().upper()
    for customer in _customers():
        for holding in customer.get("products", []):
            if holding["account_id"].upper() == aid:
                return {**holding, "customer_id": customer["customer_id"]}
    return None


def _account_transactions(account_id: str) -> list[dict[str, Any]]:
    aid = account_id.strip().upper()
    result: list[dict[str, Any]] = []
    for customer in _transactions_tree():
        for holding in customer.get("products", []):
            if holding["account_id"].upper() != aid:
                continue
            for txn in holding.get("transactions", []):
                result.append({**txn, "account_id": holding["account_id"],
                               "customer_id": customer["customer_id"]})
    return result


def _customer_transactions(customer_id: str) -> list[dict[str, Any]]:
    cid = customer_id.strip().upper()
    result: list[dict[str, Any]] = []
    for customer in _transactions_tree():
        if customer["customer_id"].upper() != cid:
            continue
        for holding in customer.get("products", []):
            for txn in holding.get("transactions", []):
                result.append({**txn, "account_id": holding["account_id"],
                               "customer_id": customer["customer_id"]})
    return result


def _within_range(txn: dict[str, Any], date_from: Optional[str],
                  date_to: Optional[str]) -> bool:
    date = txn.get("date", "")
    if date_from and date < date_from:
        return False
    if date_to and date > date_to:
        return False
    return True


_HOST = os.getenv("CUSTOMER_MCP_HOST", "127.0.0.1")
_PORT = int(os.getenv("CUSTOMER_MCP_PORT", "8092"))


def _build_auth():
    """Build the FastMCP Microsoft Entra ID JWT auth provider, or ``None``.

    Enabled only when ``ENTRA_AUTH_ENABLED`` is truthy and both the API audience
    (``MCP_AUTH_CLIENT_ID``) and ``AZURE_TENANT_ID`` are set. The provider
    validates incoming Entra access tokens (issuer, audience and JWKS signature)
    inside the app itself — no Container Apps Easy Auth and no client secret.
    No scope is required, so both delegated (user) and app-only (managed
    identity) tokens are accepted. Returns ``None`` to run anonymously (local
    development, or auth toggled off).
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
    name="customer_data",
    instructions=(
        "Bank customer master data. Use these tools to look up customers, their "
        "accounts and credit cards (product holdings), balances and "
        "transactions. Use 'summarize_spending' to answer spending questions "
        "(total, breakdown by category and top merchants, largest single "
        "transaction) and 'get_net_worth' for a balance overview across all of a "
        "customer's holdings. All monetary values are in EUR. Customer data is "
        "confidential — only surface details for the customer in context and "
        "never expose one customer's data to another. The 'update_customer' tool "
        "is a write operation and requires explicit human approval "
        "(human-in-the-loop) before it commits."
    ),
    auth=_build_auth(),
)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(_: Request) -> JSONResponse:
    """Readiness probe endpoint — returns 200 OK when the server is up."""
    return JSONResponse({"status": "ok"})


@mcp.tool()
def list_customers(bank: Optional[str] = None) -> list[dict[str, Any]]:
    """List customers, optionally filtered by bank.

    Args:
        bank: Optional bank filter, ``Bank North`` or ``Bank South``
            (case-insensitive). Omit to list customers of all banks.

    Returns one entry per customer with the core profile fields (id, bank,
    name, contact details, KYC status and segment). Product holdings are not
    included — use ``list_accounts`` for a specific customer.
    """
    customers = _customers()
    if bank:
        needle = bank.strip().lower()
        customers = [c for c in customers if c["bank"].lower() == needle]
    return [_customer_summary(c) for c in customers]


@mcp.tool()
def get_customer(customer_id: str) -> dict[str, Any]:
    """Get a single customer's full profile including their product holdings.

    Args:
        customer_id: The customer id, format ``CUST-1001``.

    Returns the customer's profile fields plus the list of product holdings
    (accounts and credit cards). If no customer matches, an ``error`` field is
    returned instead.
    """
    customer = _find_customer(customer_id)
    if customer is None:
        return {"error": f"No customer matched '{customer_id}'."}
    return copy.deepcopy(customer)


@mcp.tool()
def list_accounts(customer_id: str) -> list[dict[str, Any]]:
    """List the product holdings (accounts and credit cards) of a customer.

    Args:
        customer_id: The customer id, format ``CUST-1001``.

    Each holding includes the account id, product, IBAN or masked card number,
    balance, credit limit (cards) and status. Returns an empty list if the
    customer has no holdings or does not exist.
    """
    customer = _find_customer(customer_id)
    if customer is None:
        return []
    return copy.deepcopy(customer.get("products", []))


@mcp.tool()
def get_account(account_id: str) -> dict[str, Any]:
    """Get a single product holding (account or credit card) by its id.

    Args:
        account_id: The account id, format ``ACC-100001``.

    Returns the holding with its owning ``customer_id``. If no holding matches,
    an ``error`` field is returned instead.
    """
    holding = _find_account(account_id)
    if holding is None:
        return {"error": f"No account matched '{account_id}'."}
    return holding


@mcp.tool()
def list_transactions(account_id: Optional[str] = None,
                      customer_id: Optional[str] = None,
                      date_from: Optional[str] = None,
                      date_to: Optional[str] = None,
                      limit: int = 100) -> list[dict[str, Any]]:
    """List transactions for one account or across all of a customer's holdings.

    Provide either ``account_id`` (transactions on a single holding) or
    ``customer_id`` (transactions across every holding of that customer). If both
    are supplied ``account_id`` takes precedence.

    Args:
        account_id: Optional account id, format ``ACC-100001``.
        customer_id: Optional customer id, format ``CUST-1001``.
        date_from: Optional inclusive lower bound date ``YYYY-MM-DD``.
        date_to: Optional inclusive upper bound date ``YYYY-MM-DD``.
        limit: Maximum number of transactions to return (default 100).

    Transactions are returned sorted by date ascending. Each entry carries the
    amount, direction (``debit``/``credit``), category, merchant and the balance
    after the movement.
    """
    if account_id:
        txns = _account_transactions(account_id)
    elif customer_id:
        txns = _customer_transactions(customer_id)
    else:
        return [{"error": "Provide either 'account_id' or 'customer_id'."}]

    txns = [t for t in txns if _within_range(t, date_from, date_to)]
    txns.sort(key=lambda t: t.get("date", ""))
    return txns[: max(0, limit)]


@mcp.tool()
def get_balance(account_id: str) -> dict[str, Any]:
    """Get the current balance and currency of a single product holding.

    Args:
        account_id: The account id, format ``ACC-100001``.

    Returns ``{account_id, balance, currency}``. For a credit card the balance
    is negative when there is an amount owed. If no holding matches, an
    ``error`` field is returned instead.
    """
    holding = _find_account(account_id)
    if holding is None:
        return {"error": f"No account matched '{account_id}'."}
    return {
        "account_id": holding["account_id"],
        "balance": holding["balance"],
        "currency": holding.get("currency", "EUR"),
    }


def _round2(value: float) -> float:
    """Round a monetary amount to 2 decimal places."""
    return round(float(value), 2)


@mcp.tool()
def summarize_spending(customer_id: str,
                       date_from: Optional[str] = None,
                       date_to: Optional[str] = None,
                       account_id: Optional[str] = None,
                       category: Optional[str] = None,
                       top_merchants: int = 5) -> dict[str, Any]:
    """Summarise a customer's spending over a period (categories + top posts).

    Aggregates the customer's transactions so the agent can answer questions
    like "what did I spend on leisure last month?" with a concrete total plus a
    breakdown by category and by the largest merchants — and can name the single
    biggest transaction. Spending means ``debit`` movements; incoming ``credit``
    movements (salary, transfers in) are reported separately as income.

    Args:
        customer_id: The customer id, format ``CUST-1001``.
        date_from: Optional inclusive lower bound date ``YYYY-MM-DD``.
        date_to: Optional inclusive upper bound date ``YYYY-MM-DD``.
        account_id: Optional — restrict to a single holding, format
            ``ACC-100001``. Omit to summarise across all of the customer's
            holdings.
        category: Optional — restrict spending to one category (e.g. ``dining``,
            ``travel``, ``groceries``, ``online_shopping``, ``utilities``).
            Matched case-insensitively.
        top_merchants: How many of the biggest-spend merchants to return
            (default 5).

    Returns a dict with the resolved ``period``, ``total_spending``,
    ``total_income``, ``net`` (income − spending), ``transaction_count``, a
    ``by_category`` breakdown (total + count per category, largest first), the
    ``top_merchants`` by total spend, and the single ``largest_transaction``
    (biggest debit). If the customer does not exist an ``error`` is returned.
    """
    if _find_customer(customer_id) is None:
        return {"error": f"No customer matched '{customer_id}'."}

    if account_id:
        txns = _account_transactions(account_id)
    else:
        txns = _customer_transactions(customer_id)
    txns = [t for t in txns if _within_range(t, date_from, date_to)]

    needle = category.strip().lower() if category else None

    total_spending = 0.0
    total_income = 0.0
    by_category: dict[str, dict[str, Any]] = {}
    by_merchant: dict[str, dict[str, Any]] = {}
    largest: Optional[dict[str, Any]] = None
    counted = 0

    for txn in txns:
        amount = float(txn.get("amount", 0.0))
        direction = txn.get("direction", "debit")
        if direction == "credit":
            total_income += amount
            continue
        # debit (spending)
        cat = (txn.get("category") or "uncategorised").lower()
        if needle and cat != needle:
            continue
        counted += 1
        total_spending += amount

        cat_entry = by_category.setdefault(cat, {"category": cat, "total": 0.0, "count": 0})
        cat_entry["total"] += amount
        cat_entry["count"] += 1

        merchant = txn.get("merchant") or "unknown"
        m_entry = by_merchant.setdefault(merchant, {"merchant": merchant, "total": 0.0, "count": 0})
        m_entry["total"] += amount
        m_entry["count"] += 1

        if largest is None or amount > float(largest.get("amount", 0.0)):
            largest = txn

    by_category_list = sorted(
        ({**e, "total": _round2(e["total"])} for e in by_category.values()),
        key=lambda e: e["total"], reverse=True,
    )
    top_merchant_list = sorted(
        ({**e, "total": _round2(e["total"])} for e in by_merchant.values()),
        key=lambda e: e["total"], reverse=True,
    )[: max(0, top_merchants)]

    return {
        "customer_id": customer_id.strip().upper(),
        "period": {"from": date_from, "to": date_to},
        "account_id": account_id,
        "category_filter": needle,
        "total_spending": _round2(total_spending),
        "total_income": _round2(total_income),
        "net": _round2(total_income - total_spending),
        "transaction_count": counted,
        "by_category": by_category_list,
        "top_merchants": top_merchant_list,
        "largest_transaction": largest,
        "currency": "EUR",
    }


@mcp.tool()
def get_net_worth(customer_id: str) -> dict[str, Any]:
    """Get a customer's total net worth and a breakdown by product type.

    Sums the balances of every holding the customer has so the agent can give a
    "balance overview across all accounts" answer — current accounts, savings
    (e.g. instant-access / notice), children's savings and credit cards — plus
    the overall total. Credit-card balances are typically negative (amount
    owed), so they reduce the total. Annual interest rates are documented in the
    product catalogue (product data server) — combine with those to show rates.

    Args:
        customer_id: The customer id, format ``CUST-1001``.

    Returns ``total_net_worth``, a ``by_category`` breakdown (total balance +
    holding count per product category) and the per-holding ``accounts`` list.
    If the customer does not exist an ``error`` is returned.
    """
    customer = _find_customer(customer_id)
    if customer is None:
        return {"error": f"No customer matched '{customer_id}'."}

    total = 0.0
    by_category: dict[str, dict[str, Any]] = {}
    accounts: list[dict[str, Any]] = []
    for holding in customer.get("products", []):
        balance = float(holding.get("balance", 0.0))
        total += balance
        cat = holding.get("category", "uncategorised")
        entry = by_category.setdefault(cat, {"category": cat, "total": 0.0, "count": 0})
        entry["total"] += balance
        entry["count"] += 1
        accounts.append({
            "account_id": holding["account_id"],
            "product_code": holding.get("product_code"),
            "product_name": holding.get("product_name"),
            "category": cat,
            "balance": _round2(balance),
            "currency": holding.get("currency", "EUR"),
        })

    by_category_list = sorted(
        ({**e, "total": _round2(e["total"])} for e in by_category.values()),
        key=lambda e: e["total"], reverse=True,
    )
    return {
        "customer_id": customer["customer_id"],
        "total_net_worth": _round2(total),
        "by_category": by_category_list,
        "accounts": accounts,
        "currency": "EUR",
    }


# Fields a customer is allowed to change through the advisory channel. Identity
# and compliance fields (id, bank, kyc_status, segment) are intentionally not
# editable through this tool.
_EDITABLE_CUSTOMER_FIELDS = {"email", "phone", "address"}


@mcp.tool()
def update_customer(customer_id: str, fields: dict[str, Any],
                    confirm: bool = False) -> dict[str, Any]:
    """Update a customer's contact details (write — human-in-the-loop).

    This is a **write** operation and requires explicit human approval. Call it
    first with ``confirm=False`` (the default) to receive a preview of the
    proposed change; present that preview to the human and only re-call with
    ``confirm=True`` once approval has been granted. Only ``email``, ``phone``
    and ``address`` may be changed.

    Args:
        customer_id: The customer id, format ``CUST-1001``.
        fields: Mapping of field name to new value (subset of ``email``,
            ``phone``, ``address``).
        confirm: Set to ``True`` only after a human has approved the preview.

    Returns a ``pending_approval`` preview when ``confirm`` is ``False``, or the
    updated customer profile once committed.
    """
    customer = _find_customer(customer_id)
    if customer is None:
        return {"error": f"No customer matched '{customer_id}'."}

    invalid = set(fields) - _EDITABLE_CUSTOMER_FIELDS
    if invalid:
        return {
            "error": f"Fields not editable: {sorted(invalid)}.",
            "editable_fields": sorted(_EDITABLE_CUSTOMER_FIELDS),
        }
    if not fields:
        return {"error": "No fields supplied to update."}

    changes = {
        key: {"from": customer.get(key), "to": value}
        for key, value in fields.items()
    }

    if not confirm:
        return {
            "status": "pending_approval",
            "customer_id": customer["customer_id"],
            "requires": "human approval (call again with confirm=true)",
            "changes": changes,
        }

    # Commit against the in-memory cache. The change lives for the life of the
    # process — deliberately not persisted to disk in this demo.
    customer.update(fields)
    return {
        "status": "committed",
        "customer": _customer_summary(customer),
        "changes": changes,
    }


def main() -> None:
    """Entry point — serve the customer data over streamable-HTTP MCP."""
    # ``host_origin_protection`` is FastMCP's DNS-rebinding guard for browser
    # clients hitting localhost dev servers; it rejects any Host header outside
    # 127.0.0.1/localhost with HTTP 421. This server runs behind the Container
    # Apps ingress (which routes by host) and is protected by Entra JWT auth, so
    # the guard is both unnecessary and would block the public FQDN + health
    # probe. Disable it and rely on the ingress + JWT verification instead.
    mcp.run(
        transport="http",
        host=_HOST,
        port=_PORT,
        host_origin_protection=False,
    )


if __name__ == "__main__":
    main()
