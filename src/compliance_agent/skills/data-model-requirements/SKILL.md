---
name: data-model-requirements
description: Use when an agent asks what data is required for a customer, account or transaction to be compliant — an onboarding checklist, an eligibility gap analysis, or "what do we still need to collect". Maps each compliance rule onto the concrete banking data model and returns an extensive, field-level requirements breakdown.
---

# Data-Model Compliance Requirements Skill

Turn a regulatory rule into a precise, field-level checklist against the bank's
**live data model**. Where the regulatory-guidance skill answers "is this
allowed?", this skill answers "exactly which data fields must be present,
verified, and in what state for this to be compliant?" — and, when a caller
supplies a customer's actual data, which of those fields are satisfied and which
are still missing.

## The data model you reason over

The customer support and employee agents read this data through the customer and
product MCP servers. You do not call those servers yourself (you are index-only),
but you know their shape so you can name the exact field each rule maps to and
tell the caller what to fetch or collect.

### Customer (`get_customer` / `list_customers`)
| Field | Type | Compliance meaning |
|-------|------|--------------------|
| `customer_id` | string `CUST-1001` | Record key; anchors the audit trail (§17). |
| `full_name` | string | KYC full legal name (§3.1.1.1). Must match the ID document. |
| `date_of_birth` | date `YYYY-MM-DD` | Drives age gating (§3.2) and minor rules (§5). Derive age from it. |
| `email` | string | Verified contact channel (§3.1.1.6). |
| `phone` | string | Strong-customer-authentication / fraud-alert channel (§3.1.1.7). |
| `address` | string | Residential address (§3.1.1.4). |
| `nationality` | string | Sanctions & high-risk-country exposure (§3.1.1.3, §13). |
| `tax_residency` | string | CRS / FATCA reporting (§3.1.1.5). |
| `kyc_status` | `verified` \| `pending` \| `unverified` | The KYC gate. Most openings require `verified` (§3.1, §4.1.1.1). |
| `segment` | `retail` \| `premium` \| ... | Context for limits and enhanced due diligence. |
| `created_at` | date | Establishes the "existing customer record" (§4.1.1.2, §6.1.1.3). |
| `products[]` | list | Holdings — see below. The presence of one proves an existing relationship. |

### Product holding / account (`list_accounts` / `get_account`)
| Field | Type | Compliance meaning |
|-------|------|--------------------|
| `account_id` | string `ACC-100001` | Holding key. |
| `product_code` / `product_name` | string | Which catalogue product. |
| `category` | `savings` \| `current` \| `credit_card` \| ... | Selects the rule set (savings §4, credit card §6). |
| `iban` | string | A `current`/`savings` holding can act as the reference account (§4.1.1.3). |
| `card_number` | string \| null | Present for card products. |
| `balance` | number | Funding evidence; large-deposit monitoring (§4.2.1.1). |
| `credit_limit` | number \| null | Non-null ⇒ credit-risk product; minors barred (§5.2.1.3). |
| `currency` | string | Cross-border / FX context (§8). |
| `status` | `active` \| `pending` \| `rejected` | An `active` holding proves the relationship. |

### Transaction (`list_transactions` / `summarize_spending`)
| Field | Compliance meaning |
|-------|--------------------|
| `amount`, `currency` | Threshold & source-of-funds monitoring (§4.2, §9). |
| `date` | Frequency / structuring detection (§4.2.1.2). |
| `counterparty` / `merchant` | Sanctions & mule-account screening (§4.2.1.4, §13). |
| `direction` (credit/debit) | Incoming-transfer aggregation checks (§4.2.1.4). |
| `category` | Behavioural baselining (§4.2.1.3). |

## Method
1. **Identify the scenario and rule set.** Which workflow is this — personal
   account opening (§3), savings (§4), children's savings (§5), credit card (§6),
   domestic/international transfer (§7/§8)? Call `search_compliance_rules` with
   the scenario and domain and retrieve every applicable rule.
2. **Map every requirement to a data-model field.** For each retrieved rule,
   name the concrete field (or derived value, e.g. age from `date_of_birth`),
   the **required state/value** (e.g. `kyc_status == "verified"`, an `active`
   holding with an `iban` for the reference account), and the source citation.
3. **Assess against supplied data (if any).** When the caller includes the
   customer's actual field values, mark each requirement **met**, **missing**, or
   **needs-verification**, and state exactly what is still required.
4. **List documentary evidence** the data model cannot hold on its own —
   government-issued ID, guardian parental-authority proof (§5.1.2.4),
   employment/income evidence (§6.1.1.4–5), source-of-funds documents (§4.3).
5. **Give the determination.** approve / review / reject / escalate, with the
   blocking gaps called out first.

## Output format
- **Scenario:** the workflow and the customer/product in context.
- **Determination:** approve / review / reject / escalate.
- **Requirements checklist:** a table with columns
  `Requirement | Data-model field | Required state | Status | Source`.
  Include one row per rule; make it extensive — cover identity, screening, age,
  product-specific and monitoring rules, not just the obvious ones.
- **Documentary evidence:** items collected outside the data model.
- **Gaps / next steps:** the missing or unverified fields, in priority order.
- **Sources:** file + numbered section for every rule cited.

## Guardrails
- Never invent a field or a rule. Only name fields from the data model above and
  rules returned by `search_compliance_rules`.
- If a required field is not represented in the data model, say so plainly and
  describe how it must be evidenced instead of implying the data holds it.
- Field values you were not given are **unknown**, not compliant — mark them
  needs-verification rather than assuming they pass.
