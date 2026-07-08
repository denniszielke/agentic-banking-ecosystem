"""Mock CRM system — command-line entry point for the submit_product_recommendation tool.

Simulates submitting a product recommendation record to a CRM system. In
production this would call a real CRM API (e.g. Dynamics 365). Here it writes
a JSON record to ``crm_recommendations.jsonl`` in the agent's working directory
and prints a confirmation.

Usage (called by the agent tool as a subprocess):

    python -m src.recommender_agent.mock_crm \\
        --customer-id <id> \\
        --product-code <code> \\
        --product-name "<name>" \\
        --reason "<reason>" \\
        [--advisor-note "<note>"]

Exit codes:
  0  — success
  1  — validation error
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_OUTPUT_FILE = Path(__file__).parent / "crm_recommendations.jsonl"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mock CRM: submit a product recommendation record."
    )
    parser.add_argument("--customer-id", required=True, help="CRM customer identifier")
    parser.add_argument("--product-code", required=True, help="Product code / SKU")
    parser.add_argument("--product-name", required=True, help="Human-readable product name")
    parser.add_argument(
        "--reason",
        required=True,
        help="Short explanation of why this product fits the customer",
    )
    parser.add_argument(
        "--advisor-note",
        default="",
        help="Optional free-text note from the advisor / agent",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()

    # Basic validation
    for field_name, value in [
        ("customer-id", args.customer_id),
        ("product-code", args.product_code),
        ("product-name", args.product_name),
        ("reason", args.reason),
    ]:
        if not value.strip():
            print(f"ERROR: --{field_name} must not be empty.", file=sys.stderr)
            sys.exit(1)

    record = {
        "crm_record_id": f"REC-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}",
        "customer_id": args.customer_id.strip(),
        "product_code": args.product_code.strip(),
        "product_name": args.product_name.strip(),
        "reason": args.reason.strip(),
        "advisor_note": args.advisor_note.strip(),
        "submitted_at": datetime.now(timezone.utc).isoformat(),
        "status": "pending_review",
    }

    # Append to the local JSONL log (simulates CRM persistence).
    with _OUTPUT_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    print(json.dumps({"success": True, "crm_record_id": record["crm_record_id"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
