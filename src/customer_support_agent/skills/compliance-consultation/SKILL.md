---
name: compliance-consultation
description: Use before asking Bank North's Compliance agent (the ask_compliance tool) any regulatory, KYC/AML, sanctions, fraud or product-eligibility question. Gathers the signed-in customer's real data first, then composes a precise, self-contained compliance question so the answer is specific to this customer and product rather than generic.
---

# Compliance Consultation Skill

The Compliance agent gives a far more specific, actionable answer when the
question already contains the relevant customer facts. Never send a bare "Can
this customer get a credit card?" — gather the data model context first, then
ask a structured question.

## When to use
- Any product order where eligibility must be checked (savings, credit card,
  children's account) — before the product-ordering preview.
- Any regulatory / KYC / AML / sanctions / fraud question a customer raises.
- Any guardrail check where you would otherwise guess.

Only proceed when the `ask_compliance` tool is available. If it is not, do not
answer from your own knowledge — tell the customer the compliance service is
unavailable and defer to a human adviser.

## Method
1. **Gather the customer's data model context.** Read what the rule needs from
   the customer MCP tools before you ask:
   - `get_customer` → `full_name`, `date_of_birth` (derive the **age**),
     `nationality`, `tax_residency`, `address`, `email`, `phone`, `kyc_status`,
     `segment`, `created_at`.
   - `list_accounts` → existing holdings: `category`, `status`, whether a
     `current`/`savings` holding with an `iban` exists (a reference account),
     and any holding with a non-null `credit_limit`.
   Fetch only the fields the scenario needs; never pull another customer's data.
2. **Identify the exact scenario.** Name the workflow and the specific product
   (e.g. "opening a FlexSave savings account", "applying for a GoldCard credit
   card") including its category and whether it carries credit exposure.
3. **Compose a structured, self-contained question.** Put the facts in the
   question so the compliance answer is unambiguous. Use this shape:

   > Scenario: <workflow + specific product, with category/credit exposure>.
   > Customer: age <n> (DOB <YYYY-MM-DD>), nationality <x>, tax residency <x>,
   > kyc_status <x>, segment <x>, customer since <year>.
   > Existing holdings: <e.g. one active current account with IBAN, one savings>.
   > Question: Is this customer eligible? List every data-model field and
   > document still required, the required state of each, and the determination
   > (approve / review / reject / escalate) with citations.

   Fill in only the fields relevant to the rule; state a value as "unknown" if
   you could not fetch it rather than omitting it silently.
4. **Relay the decision.** Report the compliance agent's determination, the
   field/document gaps it named, and its citations verbatim
   (file + numbered section). Do not soften a reject or invent a missing rule.
5. **Feed it back into the flow.** If compliance says approve and all fields are
   met, continue to the product-ordering preview. If it says review / reject /
   escalate, stop and route per the compliance answer and the escalation skill.

## Output format
- To the customer: the plain-language outcome and any information they must
  still provide, with the cited rule.
- Internally: the structured question above passed to `ask_compliance`.

## Guardrails
- Always gather the customer facts BEFORE calling `ask_compliance`; a question
  without customer context yields a generic, less useful answer.
- Never fabricate a field value to make the question look complete — mark
  unknowns as unknown.
- Defer personalised financial advice to a human adviser regardless of the
  compliance answer.
