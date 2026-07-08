---
name: proactive-impulse
description: Use when the agent should proactively spot an optimisation for the signed-in customer (e.g. a large uninvested balance on the current account) and offer help. Always asks permission first, then gives two concrete, personalised recommendations, and only acts human-in-the-loop.
---

# Proactive Impulse Skill (agent-initiated, permission-first)

Detect a concrete optimisation opportunity for the signed-in customer and offer
it proactively — but only after asking for permission, and never acting without
an explicit confirmation.

## When to use
- At the start of a session, or when the account picture changes, to check
  whether there is something worth flagging (e.g. "a lot of cash sitting on a
  0% current account").
- Do **not** interrupt an unrelated task; raise the impulse once the customer's
  immediate question is answered.

## Method
1. **Detect (silently).** Call `detect_opportunities` (product data tools) for
   the customer in context. It returns idle-cash opportunities (with an
   `estimated_annual_gain`) and, when the customer holds no card, a credit-card
   candidate. If it returns nothing, stay silent — do not invent an opportunity.
2. **Ask permission first.** If there is at least one opportunity, briefly say
   what you noticed (one sentence, e.g. "You have about €39,000 earning 0% on
   your current account") and ask: *"May I make two quick suggestions?"* Wait
   for a yes before continuing.
3. **Give two concrete, personalised recommendations** once allowed:
   - **Reshuffle (idle cash).** Present the `idle_cash` opportunity with the
     concrete numbers from the tool: movable amount, target product, its rate,
     and the `estimated_annual_gain` in EUR/year. Cite the product conditions
     (file + numbered section, e.g. "savings-products.md §…"). Keep a liquidity
     buffer on the current account.
   - **Product (credit card).** If a card candidate is returned, ground the
     cost/benefit in the customer's real behaviour: call `summarize_spending`
     to see top categories/merchants and `get_product` for the annual fee, then
     state a concrete cost/benefit (e.g. "annual fee €29 vs. your travel spend
     of €X — the travel insurance/cashback likely outweighs the fee"). Only
     recommend the card if the benefit plausibly beats the fee; otherwise say so
     honestly.
4. **Act only human-in-the-loop.** If the customer wants to proceed, hand over
   to the product-ordering skill: preview with `confirm=false`, confirm in
   words, then commit with `confirm=true`. Note that opening the savings product
   is the actionable step here; the actual funds transfer is arranged
   separately.
5. **Check guardrails.** Apply the compliance guardrails before recommending
   (eligibility, segment, suitability). Do not give personalised investment
   advice — present factual options and their conditions; defer to a human
   adviser where a compliance decision is required.

## Output format
- **Notice + ask:** one-line observation, then "May I make two suggestions?"
- **On yes:** two numbered recommendations, each with concrete figures and a
  named source, and a clear next step.
- Keep the customer's sidebar in sync via `update_overview` when any pending
  action is created.

## Guardrails
- Never make suggestions before the customer agrees to hear them.
- Never commit any write without an explicit confirmation (human-in-the-loop).
- Never overstate a benefit: use the numbers from the tools and state trade-offs
  (e.g. notice period on a fixed deposit, annual card fee) honestly.
