---
name: regulatory-guidance
description: Use when a customer-facing or employee-facing agent asks a regulatory, KYC, AML, sanctions, eligibility or account-opening question. Produces a grounded, cited compliance determination.
---

# Regulatory Guidance Skill

Answer a banking compliance question with a clear, cited determination grounded
in the compliance knowledge base.

## When to use
- "Can a 16-year-old open a credit card?"
- "What screening is required before opening a business account?"
- "Is this international transfer allowed under sanctions rules?"
- Any guardrail check requested by another agent (customer support, credit card).

## Method
1. **Classify the request.** Identify the regulatory domain(s) involved: KYC,
   AML, CTF, Sanctions, Fraud Prevention, Consumer Protection, Credit Risk,
   Data Privacy, Beneficial Ownership, Auditability.
2. **Retrieve the rules.** Call `search_compliance_rules` with the scenario and
   the domain filter. Retrieve every rule that could apply.
3. **Determine the outcome.** Map the scenario onto the rules and state one of:
   **approve**, **review**, **reject**, or **escalate**. Include the specific
   thresholds, required documents and screening steps.
4. **Cite the evidence.** Name the source file and the numbered hierarchy
   element for each rule you relied on (e.g. `compliance-regulatory.md §3.2.2`).

## Output format
- **Determination:** approve / review / reject / escalate.
- **Requirements:** the concrete steps, documents or thresholds.
- **Sources:** file + numbered section for each cited rule.

## Guardrails
- Never state a rule that is not in the retrieved results.
- If the knowledge base does not cover the scenario, say so explicitly and
  escalate — do not improvise a rule.
