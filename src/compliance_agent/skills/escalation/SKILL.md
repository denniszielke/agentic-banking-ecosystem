---
name: escalation
description: Use when a request goes beyond compliance guidance — personalised financial or investment advice, an ambiguous or high-risk scenario, or a case the knowledge base does not cover. Routes the case to the correct human per the escalation matrix.
---

# Escalation Skill

Recognise when a request must leave the automated compliance channel and route
it correctly.

## When to escalate
- The request asks for **personalised financial or investment advice** (what to
  buy, how to invest, whether a product is "right for me"). Compliance guidance
  is allowed; advice is not.
- The scenario is **high risk** (sanctions hit, suspected fraud, PEP match,
  beneficial-ownership ambiguity) and requires human review.
- The compliance knowledge base **does not cover** the question.
- Two rules **conflict** and the resolution is not deterministic.

## Method
1. **State why** the case is being escalated (advice request / high risk /
   coverage gap / conflict).
2. **Retrieve the escalation rule.** Call `search_compliance_rules` for the
   escalation matrix and cite the relevant numbered section.
3. **Route it.** Name the responsible role (e.g. compliance officer, fraud desk,
   qualified financial adviser) as defined in the escalation matrix.
4. **Do not answer** the out-of-scope part yourself. Provide only the compliance
   context that is safe to share, then hand off.

## Output format
- **Escalation reason:** one line.
- **Route to:** role / desk from the escalation matrix.
- **Sources:** file + numbered section.

## Guardrails
- Never provide investment or personalised financial advice, even if asked
  directly. Refuse politely and escalate.
