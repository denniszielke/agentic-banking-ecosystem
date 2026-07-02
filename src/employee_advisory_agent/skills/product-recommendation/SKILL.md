---
name: product-recommendation
description: Use when an employee asks which product to recommend to a customer, or to compare products for a specific customer need. Produces a grounded, segment-aware recommendation.
---

# Product Recommendation Skill

Help an employee recommend the most suitable financial product for the customer
in front of them, grounded in product conditions and the customer's context.

## When to use
- "Which savings product should I suggest for this customer?"
- "Compare GrowthSaver and FixedDeposit Plus for a customer with €20k."
- "Is a GoldCard or PlatinumCard better for a frequent traveller?"

## Inputs to gather first
1. **Customer context** — use the customer data tools to read the customer's
   segment (retail / youth / premium), existing holdings and recent activity.
   Read-only; never modify customer data.
2. **Product conditions** — use `search_financial_products` and the product
   data tools to pull interest rates, fees, minimum deposits, notice periods and
   eligibility for the candidate products.

## Method
1. **Frame the need.** State the customer goal (liquidity, yield, everyday
   spend, children's savings) and any constraints (deposit size, age, segment).
2. **Shortlist products.** Pick 2–3 candidates whose conditions fit the need.
3. **Compare on the facts.** Contrast rate, fee, minimum deposit, notice period
   and eligibility. Cite each figure with its source file and numbered section.
4. **Recommend.** Give a single primary recommendation with a one-line rationale
   and note the runner-up and when it would be preferable.

## Output format
A short comparison (product, rate, fee, min deposit, key condition) followed by
the recommendation, rationale and sources.

## Guardrails
- Match the segment: youth/children's products require the age/guardian rules —
  if unsure, defer to compliance guidance.
- Do not oversell: state the trade-offs honestly. This is employee guidance, not
  regulated advice to the customer.
