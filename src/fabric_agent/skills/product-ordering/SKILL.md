---
name: product-ordering
description: Use when the customer wants to order a product (e.g. open a savings account or apply for a credit card) or change their contact details. Enforces the human-in-the-loop confirmation and compliance guardrails.
---

# Product Ordering Skill (human-in-the-loop)

Guide a customer through starting a product order or a contact-detail change.
Every write is human-in-the-loop and must be confirmed before it commits.

## When to use
- "I'd like to apply for a GoldCard." / "Open a FlexSave savings account."
- "Please update my phone number / address."

## Method
1. **Check eligibility & guardrails.** Before proposing an order, apply the
   compliance guardrails (age, KYC status, segment, product eligibility). Cite
   the relevant compliance rule (file + numbered section). If eligibility is
   unclear or the rule requires a compliance decision, escalate rather than
   proceed.
2. **Preview.** Call the write tool with `confirm=false`
   (`order_product` for a new product, `update_customer` for contact details) to
   produce a preview of exactly what will change.
3. **Confirm.** Show the preview to the customer, set the sidebar pending action
   (`update_overview` with `awaiting_confirmation=true`) and ask them to confirm
   in words.
4. **Commit.** Only after an explicit "yes", call the same tool with
   `confirm=true`. `order_product` opens an **order case** (status `requested`,
   the holding starts `pending`) and returns an `order_id`.
5. **State the next steps.** Confirm what was placed and, for a credit card,
   read the `delivery` details from the order (estimated business days +
   shipping address) and tell the customer when it will arrive and where.
6. **Track the order.** The order moves through its lifecycle — `requested` →
   `approved` | `rejected`; `approved` → `shipped` → `delivered`. Use
   `list_orders` / `get_order` to report status ("Your GoldCard application is
   approved and shipping"). Advancing the status (`update_order_status`) is a
   bank-side decision and is itself human-in-the-loop; approving an order
   activates the holding, rejecting it marks the holding `rejected`.

## Output format
- **Preview:** the product/holding or field change, with any fee/condition.
- **Ask:** "Shall I go ahead?"
- **After commit:** confirmation, the `order_id`, new account id (for orders),
  the delivery ETA + address (for cards), and the current order status.

## Guardrails
- Never call a write tool with `confirm=true` without an explicit customer "yes".
- Never bypass an eligibility rule. If compliance requires a human decision,
  stop and hand off.
- Do not tell the customer an order is complete while it is still `requested` or
  `pending`; report the actual status from the order case.
