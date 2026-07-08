#!/usr/bin/env python3
"""Deterministic generator for the fictional banking demo data.

Produces:
  - data/customers.md                              (20 customers + product holdings)
  - data/customers.json                            (customers with nested product holdings)
  - data/transactions.json                         (customer -> products -> transactions)
  - data/transactions/<customer_id>_transactions.md (one transaction file per customer)

Run from the repository root:
    python scripts/generate_data.py

The generator is seeded so output is stable across runs.
"""
from __future__ import annotations

import json
import random
from datetime import date, timedelta
from pathlib import Path

SEED = 20260701
random.seed(SEED)

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# --- Product catalogue -----------------------------------------------------

PRODUCTS = {
    "CURRENTPLUS": ("Current Account Plus", "current_account"),
    "FLEXSAVE": ("FlexSave", "savings"),
    "GROWTHSAVER": ("GrowthSaver", "savings"),
    "FIXEDPLUS": ("FixedDeposit Plus", "savings"),
    "KIDSSAVE": ("KidsSave", "childrens_savings"),
    "TEENSAVER": ("TeenSaver", "childrens_savings"),
    "FUTUREBUILDER": ("FutureBuilder", "childrens_savings"),
    "SECURITIESDEPOT": ("Securities Depot", "securities"),
    "WEALTHDEPOT": ("Wealth Depot", "securities"),
    "CLASSICCARD": ("ClassicCard", "credit_card"),
    "GOLDCARD": ("GoldCard", "credit_card"),
    "PLATINUMCARD": ("PlatinumCard", "credit_card"),
}

CARD_LIMITS = {"CLASSICCARD": 5000, "GOLDCARD": 15000, "PLATINUMCARD": 50000}

# --- Fictional customers ---------------------------------------------------

CUSTOMERS = [
    # (name, bank, dob, nationality, segment)
    ("Amelia Rowan", "Bank North", "1988-03-14", "German", "retail"),
    ("Benedikt Vogl", "Bank North", "1975-11-02", "Austrian", "premium"),
    ("Clara Hoffmann", "Bank North", "1993-07-29", "German", "retail"),
    ("Dominik Reuter", "Bank North", "2007-01-18", "German", "youth"),
    ("Elena Soriano", "Bank North", "1982-09-05", "Spanish", "retail"),
    ("Felix Baumann", "Bank North", "1969-12-21", "Swiss", "premium"),
    ("Greta Lindqvist", "Bank North", "1996-04-11", "Swedish", "retail"),
    ("Henrik Dahl", "Bank North", "2010-06-30", "Danish", "youth"),
    ("Ingrid Moser", "Bank North", "1978-02-08", "German", "retail"),
    ("Jonas Weaver", "Bank North", "1985-10-17", "British", "premium"),
    ("Katarina Novak", "Bank South", "1991-05-23", "Czech", "retail"),
    ("Lukas Brenner", "Bank South", "1973-08-14", "German", "premium"),
    ("Mia Fontaine", "Bank South", "1999-12-01", "French", "retail"),
    ("Nils Osterberg", "Bank South", "2009-03-09", "Norwegian", "youth"),
    ("Olivia Kraus", "Bank South", "1986-07-19", "German", "retail"),
    ("Pavel Istvan", "Bank South", "1980-01-27", "Hungarian", "premium"),
    ("Quentin Marsh", "Bank South", "1994-09-13", "British", "retail"),
    ("Rosa Delgado", "Bank South", "2008-11-04", "Spanish", "youth"),
    ("Sven Larsson", "Bank South", "1977-04-25", "Swedish", "retail"),
    ("Tara Windsor", "Bank South", "1990-06-16", "Irish", "premium"),
]

MERCHANTS = {
    "supplies": ["Office Depot", "Staples Direct", "PaperPlus", "TonerHub", "DeskMart"],
    "online_shopping": ["Amazonia", "eBuy", "Zalarno", "TechNest", "HomeStyle Online"],
    "travel": ["Lufthansa", "FlixExpress", "Deutsche Bahn", "Booking Nest", "RentACar EU",
               "Airbnb Stays", "Hotel Meridian"],
    "groceries": ["EDEKA", "REWE", "Lidl", "Aldi Nord", "Carrefour"],
    "dining": ["Cafe Central", "Trattoria Roma", "Sushi Bar Ken", "Burger Loft",
               "Green Bowl"],
    "utilities": ["Vattenfall", "Telekom", "Vodafone", "Stadtwerke", "AquaCity"],
    "salary": ["ACME Payroll", "Globex GmbH", "Initech AG", "Umbrella Corp"],
    "transfer": ["Transfer to Savings", "Rent Payment", "P2P Transfer", "Standing Order"],
}


def iban(bank: str, n: int) -> str:
    prefix = "DE89" if bank == "Bank North" else "DE44"
    return f"{prefix} {3700 + n:04d} 0000 {1000 + n:04d} {2000 + n:04d} 00"


def _luhn_check_digit(number_without_check: str) -> int:
    digits = [int(d) for d in number_without_check]
    # The check digit position is even from the right (0-indexed from the check digit),
    # so starting from the rightmost body digit we double every second digit.
    total = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 0:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return (10 - (total % 10)) % 10


def card_number(n: int) -> str:
    # Deterministic Visa-style 16-digit PAN: BIN 4539 + 11 derived digits + Luhn check.
    body = f"4539{((1000 + n) * 1000003) % 10**11:011d}"
    pan = body + str(_luhn_check_digit(body))
    return " ".join(pan[i : i + 4] for i in range(0, 16, 4))


def pick_products(segment: str, rng: random.Random) -> list[str]:
    """Assign 1-3 products consistent with the customer's segment."""
    if segment == "youth":
        pool = ["KIDSSAVE", "TEENSAVER", "FUTUREBUILDER", "CURRENTPLUS"]
    elif segment == "premium":
        pool = ["CURRENTPLUS", "GROWTHSAVER", "FIXEDPLUS", "WEALTHDEPOT",
                "SECURITIESDEPOT", "PLATINUMCARD", "GOLDCARD"]
    else:  # retail
        pool = ["CURRENTPLUS", "FLEXSAVE", "GROWTHSAVER", "SECURITIESDEPOT",
                "CLASSICCARD", "GOLDCARD"]
    count = rng.randint(1, 3)
    # Always ensure a current account is present if more than one product.
    chosen = rng.sample(pool, k=min(count, len(pool)))
    return chosen


def make_transactions(account_id: str, customer_id: str, category_bias: str,
                      is_card: bool, end_balance: float, rng: random.Random):
    n = rng.randint(4, 30)
    txns = []
    current = date(2026, 6, 30)
    for i in range(n):
        current -= timedelta(days=rng.randint(1, 6))
        cat = rng.choices(
            population=["supplies", "online_shopping", "travel", "groceries",
                        "dining", "utilities", "salary", "transfer"],
            weights=[2, 4, 4, 3, 3, 2, 1, 2],
        )[0]
        merchant = rng.choice(MERCHANTS[cat])
        if cat == "salary" and not is_card:
            direction = "credit"
            amount = round(rng.uniform(1800, 5200), 2)
        elif cat == "transfer" and not is_card:
            direction = rng.choice(["debit", "credit"])
            amount = round(rng.uniform(50, 1200), 2)
        else:
            direction = "debit"
            ranges = {
                "supplies": (12, 220),
                "online_shopping": (15, 480),
                "travel": (40, 950),
                "groceries": (8, 160),
                "dining": (9, 120),
                "utilities": (25, 210),
            }
            lo, hi = ranges.get(cat, (10, 200))
            amount = round(rng.uniform(lo, hi), 2)
        txns.append({
            "transaction_id": f"TXN-{rng.randint(10_000_000, 99_999_999)}",
            "account_id": account_id,
            "customer_id": customer_id,
            "date": current.isoformat(),
            "direction": direction,
            "amount": amount,
            "category": cat,
            "merchant": merchant,
        })
    txns.sort(key=lambda t: t["date"])
    # Walk forward chronologically so balance_after is consistent and the final
    # balance matches the holding's current balance.
    signed = [t["amount"] if t["direction"] == "credit" else -t["amount"] for t in txns]
    balance = round(end_balance - sum(signed), 2)
    for t, delta in zip(txns, signed):
        balance = round(balance + delta, 2)
        t["balance_after"] = balance
    return txns


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    tx_dir = DATA_DIR / "transactions"
    tx_dir.mkdir(parents=True, exist_ok=True)
    acc_counter = 100000
    customers_out = ["# Customers", "",
                     "> Fictional demo data generated by `scripts/generate_data.py`.",
                     ""]
    customers_json: list[dict] = []
    transactions_json: list[dict] = []

    for idx, (name, bank, dob, nat, segment) in enumerate(CUSTOMERS, start=1):
        rng = random.Random(SEED + idx)
        customer_id = f"CUST-{1000 + idx:04d}"
        first = name.split()[0].lower()
        last = name.split()[-1].lower()
        domain = "banknorth.demo" if bank == "Bank North" else "banksouth.demo"
        email = f"{first}.{last}@{domain}"
        phone = f"+49 170 {rng.randint(1000000, 9999999)}"
        address = f"{rng.randint(1, 199)} {rng.choice(['Lindenstr.', 'Hauptstr.', 'Bahnhofstr.', 'Gartenweg', 'Ringstr.'])}, {rng.choice(['North City', 'South City'])}"
        created = f"20{rng.randint(15, 24)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}"

        product_codes = pick_products(segment, rng)
        holdings = []
        for code in product_codes:
            acc_counter += 1
            pname, category = PRODUCTS[code]
            is_card = category == "credit_card"
            if is_card:
                start_balance = -round(rng.uniform(120, CARD_LIMITS[code] * 0.4), 2)
                holdings.append({
                    "account_id": f"ACC-{acc_counter}",
                    "product_code": code,
                    "product_name": pname,
                    "category": category,
                    "iban": None,
                    "card_number": card_number(acc_counter % 10000),
                    "balance": start_balance,
                    "credit_limit": CARD_LIMITS[code],
                    "is_card": True,
                })
            elif category == "securities":
                # A depot holds investments; its balance is the market value of
                # the portfolio. It has no IBAN or card — it is identified by its
                # account id and carries no cash-style transaction ledger.
                start_balance = round(rng.uniform(8000, 120000), 2)
                holdings.append({
                    "account_id": f"ACC-{acc_counter}",
                    "product_code": code,
                    "product_name": pname,
                    "category": category,
                    "iban": None,
                    "card_number": None,
                    "balance": start_balance,
                    "credit_limit": None,
                    "is_card": False,
                })
            else:
                start_balance = round(rng.uniform(500, 45000), 2)
                holdings.append({
                    "account_id": f"ACC-{acc_counter}",
                    "product_code": code,
                    "product_name": pname,
                    "category": category,
                    "iban": iban(bank, acc_counter % 10000),
                    "card_number": None,
                    "balance": start_balance,
                    "credit_limit": None,
                    "is_card": False,
                })

        # --- customers.md section ---
        customers_out.append(f"## {customer_id} — {name}")
        customers_out.append("")
        customers_out.append("| Field | Value |")
        customers_out.append("|-------|-------|")
        customers_out.append(f"| customer_id | {customer_id} |")
        customers_out.append(f"| bank | {bank} |")
        customers_out.append(f"| full_name | {name} |")
        customers_out.append(f"| date_of_birth | {dob} |")
        customers_out.append(f"| email | {email} |")
        customers_out.append(f"| phone | {phone} |")
        customers_out.append(f"| address | {address} |")
        customers_out.append(f"| nationality | {nat} |")
        customers_out.append(f"| tax_residency | {nat} |")
        customers_out.append(f"| kyc_status | verified |")
        customers_out.append(f"| segment | {segment} |")
        customers_out.append(f"| created_at | {created} |")
        customers_out.append("")
        customers_out.append("### Product Holdings")
        customers_out.append("")
        customers_out.append("| account_id | product | category | iban / card | balance (EUR) | credit_limit |")
        customers_out.append("|------------|---------|----------|-------------|---------------|--------------|")
        for h in holdings:
            ident = h["iban"] or h["card_number"] or "—"
            climit = h["credit_limit"] if h["credit_limit"] is not None else "—"
            customers_out.append(
                f"| {h['account_id']} | {h['product_name']} | {h['category']} | "
                f"{ident} | {h['balance']:.2f} | {climit} |"
            )
        customers_out.append("")
        customers_out.append(f"Transactions: [`data/transactions/{customer_id}_transactions.md`](transactions/{customer_id}_transactions.md)")
        customers_out.append("")
        customers_out.append("---")
        customers_out.append("")

        # --- customers.json record (products nested inside the customer) ---
        customer_record = {
            "customer_id": customer_id,
            "bank": bank,
            "full_name": name,
            "date_of_birth": dob,
            "email": email,
            "phone": phone,
            "address": address,
            "nationality": nat,
            "tax_residency": nat,
            "kyc_status": "verified",
            "segment": segment,
            "created_at": created,
            "products": [
                {
                    "account_id": h["account_id"],
                    "product_code": h["product_code"],
                    "product_name": h["product_name"],
                    "category": h["category"],
                    "iban": h["iban"],
                    "card_number": h["card_number"],
                    "balance": h["balance"],
                    "credit_limit": h["credit_limit"],
                    "currency": "EUR",
                    "status": "active",
                }
                for h in holdings
            ],
        }
        customers_json.append(customer_record)

        # --- transactions.json record (customer -> products -> transactions) ---
        tx_record = {
            "customer_id": customer_id,
            "full_name": name,
            "bank": bank,
            "products": [],
        }

        # --- per-customer transactions file ---
        tx_lines = [f"# Transactions — {customer_id} ({name})", "",
                    "> Fictional demo data generated by `scripts/generate_data.py`.", ""]
        for h in holdings:
            ident = h["iban"] or h["card_number"] or "—"
            # A securities depot has no cash-style transaction ledger in this
            # demo — it is represented by its current market value only.
            if h["category"] == "securities":
                tx_record["products"].append({
                    "account_id": h["account_id"],
                    "product_code": h["product_code"],
                    "product_name": h["product_name"],
                    "category": h["category"],
                    "iban": h["iban"],
                    "card_number": h["card_number"],
                    "currency": "EUR",
                    "transactions": [],
                })
                tx_lines.append(f"## {h['account_id']} — {h['product_name']} ({ident})")
                tx_lines.append("")
                tx_lines.append(
                    f"Securities depot — market value €{h['balance']:.2f}. "
                    "No transaction ledger in this demo."
                )
                tx_lines.append("")
                continue
            txns = make_transactions(
                h["account_id"], customer_id, h["category"], h["is_card"],
                h["balance"], rng,
            )
            tx_record["products"].append({
                "account_id": h["account_id"],
                "product_code": h["product_code"],
                "product_name": h["product_name"],
                "category": h["category"],
                "iban": h["iban"],
                "card_number": h["card_number"],
                "currency": "EUR",
                "transactions": [
                    {
                        "transaction_id": t["transaction_id"],
                        "date": t["date"],
                        "direction": t["direction"],
                        "amount": t["amount"],
                        "currency": "EUR",
                        "category": t["category"],
                        "merchant": t["merchant"],
                        "balance_after": t["balance_after"],
                    }
                    for t in txns
                ],
            })
            tx_lines.append(f"## {h['account_id']} — {h['product_name']} ({ident})")
            tx_lines.append("")
            tx_lines.append(f"Transaction count: {len(txns)}")
            tx_lines.append("")
            tx_lines.append("| transaction_id | date | direction | amount (EUR) | category | merchant | balance_after |")
            tx_lines.append("|----------------|------|-----------|--------------|----------|----------|---------------|")
            for t in txns:
                tx_lines.append(
                    f"| {t['transaction_id']} | {t['date']} | {t['direction']} | "
                    f"{t['amount']:.2f} | {t['category']} | {t['merchant']} | {t['balance_after']:.2f} |"
                )
            tx_lines.append("")
        (tx_dir / f"{customer_id}_transactions.md").write_text("\n".join(tx_lines))
        transactions_json.append(tx_record)
        print(f"wrote data/transactions/{customer_id}_transactions.md ({len(holdings)} holdings)")

    (DATA_DIR / "customers.md").write_text("\n".join(customers_out))
    print("wrote data/customers.md (20 customers)")

    (DATA_DIR / "customers.json").write_text(
        json.dumps({"customers": customers_json}, indent=2, ensure_ascii=False) + "\n"
    )
    print("wrote data/customers.json (20 customers)")

    (DATA_DIR / "transactions.json").write_text(
        json.dumps({"customers": transactions_json}, indent=2, ensure_ascii=False) + "\n"
    )
    print("wrote data/transactions.json (20 customers)")


if __name__ == "__main__":
    main()
