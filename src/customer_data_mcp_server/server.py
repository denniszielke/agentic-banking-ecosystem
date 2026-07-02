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

from mcp.server.fastmcp import FastMCP
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


mcp = FastMCP(
    name="customer_data",
    instructions=(
        "Bank customer master data. Use these tools to look up customers, their "
        "accounts and credit cards (product holdings), balances and "
        "transactions. All monetary values are in EUR. Customer data is "
        "confidential — only surface details for the customer in context and "
        "never expose one customer's data to another. The 'update_customer' tool "
        "is a write operation and requires explicit human approval "
        "(human-in-the-loop) before it commits."
    ),
    host=os.getenv("CUSTOMER_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("CUSTOMER_MCP_PORT", "8092")),
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
    mcp.run(transport="streamable-http")


if __name__ == "__main__":
    main()
