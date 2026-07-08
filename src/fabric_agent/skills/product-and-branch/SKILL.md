---
name: product-and-branch
description: Use when the customer asks what products they hold, to explain a product's conditions, to discover a new product, or where/when their nearest branch is open.
---

# Product & Branch Skill

Help the customer understand their products and find branch information, grounded
in the product catalogue, product conditions and the branch directory.

## When to use
- "What products do I have?" / "Explain my savings account conditions."
- "What savings options do you offer?" / "Compare two cards."
- "Where is my nearest branch and what are its opening hours?"

## Method
1. **Holdings.** Use the product data MCP tools (`list_holdings`, `get_product`)
   for what the customer holds and the catalogue definition.
2. **Conditions & discovery.** Use the Financial products knowledge to explain
   interest rates, fees, minimum deposits and notice periods, and to surface
   suitable alternatives. Cite the file and numbered section
   (e.g. "savings-products.md §1.2.2.1").
3. **Branch.** Answer branch location, opening hours and services from the
   branch directory grounding (bank-south.md). Cite the numbered section.

## Output format
A short explanation with the key figures, each backed by a named source, and —
for discovery — a two or three product comparison.

## Guardrails
- Explain conditions factually; do not give personalised investment advice. If
  the customer asks whether a product is "right for them" as advice, apply the
  compliance guardrails and defer to a human adviser where required.
