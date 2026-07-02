---
name: account-enquiry
description: Use when the customer asks about their balance, transactions, or personal details. Produces a grounded, confidential answer from the customer data MCP tools.
---

# Account Enquiry Skill

Answer a customer's questions about their own accounts, balances and
transactions, strictly for the signed-in customer.

## When to use
- "What is my balance?"
- "List my transactions from last month / between two dates."
- "What are my registered contact details?"

## Method
1. **Identify the customer in context.** Use the customer id provided in the
   conversation. Never ask for or reveal another customer's data.
2. **Fetch the data.** Use the customer data MCP tools:
   - `get_balance` / `get_account` for a single holding balance.
   - `list_accounts` / `get_customer` for the full holding list and profile.
   - `list_transactions` with `date_from` / `date_to` for a statement window.
3. **Summarise clearly.** Report figures in EUR, group transactions by date, and
   show the running balance where useful.
4. **Update the sidebar.** Call `update_overview` with the customer profile and
   the current accounts before replying.

## Output format
Lead with the direct answer (e.g. the balance), then a compact table of
transactions (date, description, category, amount, balance after) when relevant.

## Guardrails
- Confidentiality first: only the signed-in customer's data, ever.
- Do not modify anything here — this is read-only. Contact-detail changes go
  through the update flow with explicit confirmation.
