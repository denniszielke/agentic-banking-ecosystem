---
name: account-enquiry
description: Use when the customer asks about their balance, transactions, or personal details. Produces a grounded, confidential answer from the customer data MCP tools.
---

# Account Enquiry Skill

Answer a customer's questions about their own accounts, balances and
transactions, strictly for the signed-in customer.

## When to use
- "What is my balance?"
- "What is my total balance / net worth across all accounts?"
- "How much did I spend on <category> last month?" / "What were my biggest expenses?"
- "What was my largest single transaction?"
- "List my transactions from last month / between two dates."
- "What are my registered contact details?"

## Method
1. **Identify the customer in context.** Use the customer id provided in the
   conversation. Never ask for or reveal another customer's data.
2. **Fetch the data.** Use the customer data MCP tools:
   - `get_balance` / `get_account` for a single holding balance.
   - `get_net_worth` for a balance overview across ALL holdings (total + a
     breakdown by product type). Prefer this for "all my accounts" / "total"
     questions instead of summing manually.
   - `summarize_spending` for any spending question — it returns the total, a
     breakdown by category, the top merchants and the single largest
     transaction over the period. Pass `date_from` / `date_to` for a window and
     `category` to focus on one spending category.
   - `list_accounts` / `get_customer` for the full holding list and profile.
   - `list_transactions` with `date_from` / `date_to` when the customer wants
     the raw statement lines rather than a summary.
3. **Summarise clearly.** Report figures in EUR, group transactions by date, and
   show the running balance where useful. For spending answers, lead with the
   total, then the largest posts (category and/or merchant).
4. **Update the sidebar.** Call `update_overview` with the customer profile and
   the current accounts before replying.

## Output format
Lead with the direct answer (e.g. the balance), then a compact table of
transactions (date, description, category, amount, balance after) when relevant.

## Guardrails
- Confidentiality first: only the signed-in customer's data, ever.
- Do not modify anything here — this is read-only. Contact-detail changes go
  through the update flow with explicit confirmation.
