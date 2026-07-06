# 1. Banking Compliance & Regulatory Knowledge Base

## 1.1. Purpose

### 1.1.1. This document defines the compliance, regulatory, KYC, AML, sanctions, fraud, and eligibility rules used by banking agents during

- 1.1.1.1 **Current account opening.** This covers the end-to-end process of establishing a new everyday transactional account for a retail customer. It is about ensuring the applicant is correctly identified, screened, and eligible before any account is activated. Compliance requires completed KYC identity verification, successful sanctions and PEP screening, and a verified reference or funding method before the account can be used.
- 1.1.1.2 **Business account opening.** This covers onboarding legal entities such as sole proprietors and limited companies rather than individual consumers. It is about verifying the business itself, the people who control it, and the legitimacy of its expected activity. Compliance requires valid business registration documents, identification of beneficial owners and directors, and a completed business risk assessment before the account is opened.
- 1.1.1.3 **Savings account onboarding.** This covers adding a deposit or savings product to an existing verified banking relationship. It is about confirming that the customer is known, that funds have a legitimate origin, and that a linked reference account exists. Compliance requires valid identity verification, an existing customer record, and a verified reference account before deposits are accepted.
- 1.1.1.4 **Children's savings products.** This covers savings and youth banking products where the account holder is a minor. It is about protecting the child, confirming guardianship, and applying restrictions on credit-based services. Compliance requires the child's details, a verified legal guardian with confirmed parental authority, and adherence to the prohibitions on lending to minors.
- 1.1.1.5 **Credit card applications.** This covers requests for revolving credit products that expose the bank to repayment and credit risk. It is about assessing the applicant's ability to repay and ensuring the agent never issues an approval itself. Compliance requires verified identity and address, employment and income information, an existing banking relationship, and human credit assessment before any approval.
- 1.1.1.6 **Domestic transfers.** This covers payments moved between accounts within the same national or SEPA payment area. It is about confirming payment details, authenticating the payer, and monitoring for unusual behaviour. Compliance requires complete recipient details, strong customer authentication where triggered, and transaction monitoring for suspicious patterns.
- 1.1.1.7 **International transfers.** This covers cross-border payments that carry higher sanctions, embargo, and money-laundering exposure. It is about screening the destination, the beneficiary, and the stated purpose before funds leave the country. Compliance requires full beneficiary and bank details, a stated transfer purpose, sanctions and embargo screening, and source-of-funds checks where risk indicators appear.
- 1.1.1.8 **Account maintenance.** This covers ongoing changes to an existing account such as updating details, settings, or linked services. It is about ensuring only the authenticated account holder can make sensitive changes. Compliance requires successful customer authentication, additional verification for high-risk changes, and an audit record of every modification.
- 1.1.1.9 **Fraud prevention.** This covers the detection and interruption of unauthorised or deceptive account activity. It is about spotting anomalies in devices, behaviour, and transactions and responding proportionately to the risk level. Compliance requires active monitoring, graduated response actions from additional verification to account freezes, and escalation of high-risk cases to a human specialist.
- 1.1.1.10 **Ongoing customer monitoring.** This covers the continuous review of customer activity throughout the life of the relationship, not just at onboarding. It is about detecting changes in risk, unusual behaviour, and events that require re-screening. Compliance requires periodic and event-driven reviews, re-screening after profile changes, and escalation whenever new red flags emerge.

---

# 2. Regulatory Domains

| Ref | Domain | Purpose |
|-----|------|-------|
| 2.1 | KYC | Verify customer identity |
| 2.2 | AML | Prevent money laundering |
| 2.3 | CTF | Prevent terrorist financing |
| 2.4 | Sanctions | Screen against sanctions lists |
| 2.5 | Fraud Prevention | Detect abuse and scams |
| 2.6 | Consumer Protection | Protect retail customers |
| 2.7 | Credit Risk | Assess lending and card eligibility |
| 2.8 | Data Privacy | Protect personal data |
| 2.9 | Beneficial Ownership | Identify ultimate owners of businesses |
| 2.10 | Auditability | Maintain regulatory evidence |

---

# 3. Personal Account Opening

## 3.1. Identity Verification (KYC)

### 3.1.1. Before opening any account, the bank must verify

- 3.1.1.1 **Full legal name.** The customer's complete legal name as it appears on official identity documents anchors every downstream compliance check. It is about uniquely identifying the individual so that screening and record-keeping are reliable. Compliance requires the name to match a government-issued identity document exactly, with any discrepancy resolved before onboarding continues.
- 3.1.1.2 **Date of birth.** The date of birth confirms the customer's age and helps distinguish between individuals with similar names. It is about establishing legal capacity and applying age-based product eligibility rules. Compliance requires a verified date of birth from an identity document and, for minors, the guardian controls described in the age-requirements rules.
- 3.1.1.3 **Nationality.** Nationality informs sanctions exposure, tax obligations, and jurisdictional risk. It is about understanding which national frameworks and screening lists apply to the customer. Compliance requires nationality to be captured from a valid identity document and screened against relevant sanctions and high-risk-country criteria.
- 3.1.1.4 **Residential address.** The residential address establishes where the customer actually lives and is a core proof-of-identity element. It is about preventing impersonation, confirming service jurisdiction, and enabling correspondence. Compliance requires a verifiable current address and additional verification when the address is inconsistent or in a high-risk location.
- 3.1.1.5 **Tax residency.** Tax residency determines the customer's reporting obligations under regimes such as CRS and FATCA. It is about ensuring the bank meets its cross-border tax-reporting duties. Compliance requires the customer to declare tax residency and, where applicable, provide a taxpayer identification number for reporting.
- 3.1.1.6 **Email address.** A verified email address supports secure communication, notifications, and identity recovery. It is about maintaining a reliable, customer-controlled contact channel. Compliance requires a valid, confirmed email that belongs to the customer and is protected within account security controls.
- 3.1.1.7 **Mobile number.** The mobile number underpins strong customer authentication and fraud alerts. It is about enabling out-of-band verification and rapid customer contact on suspicious activity. Compliance requires a confirmed mobile number tied to the customer and used for authentication challenges.
- 3.1.1.8 **Government-issued identification.** An official identity document such as a passport or national ID is the evidentiary basis for the whole KYC process. It is about proving the customer is a real, correctly identified person. Compliance requires a valid, unexpired document verified through an accepted method, with any mismatch triggering review before the account opens.

### 3.1.2. Accepted Identification Methods

- 3.1.2.1 **Branch verification.** In-person identification at a physical branch lets staff inspect original documents and the customer directly. It is about achieving high-assurance identity proofing through face-to-face document checks. Compliance requires a trained staff member to validate the original document and record that the check was performed.
- 3.1.2.2 **Video identification.** A live video session allows remote but supervised inspection of the customer and their documents. It is about extending high-assurance verification to customers who cannot attend a branch. Compliance requires a real-time session, liveness checks, and capture of the document imagery for the audit record.
- 3.1.2.3 **Electronic ID (eID).** Government-backed or certified digital identity schemes verify the customer through a trusted electronic credential. It is about enabling secure, fully digital onboarding at a recognised assurance level. Compliance requires the eID scheme to meet the bank's assurance standard and to produce a verifiable, logged authentication result.

---

## 3.2. Age Requirements

| Ref | Customer Age | Allowed Action |
|-----|------------|--------------|
| 3.2.1 | Under 7 | Account only via legal guardian |
| 3.2.2 | 7-17 | Guardian consent required |
| 3.2.3 | 18+ | Fully independent banking relationship |

---

## 3.3. Mandatory Screening

### 3.3.1. Every new customer must be checked against

- 3.3.1.1 **Sanctions lists.** Screening against official sanctions lists prevents the bank from serving prohibited individuals or entities. It is about ensuring no restricted party gains access to banking services. Compliance requires screening every new customer before onboarding and stopping the workflow for compliance review whenever a match is found.
- 3.3.1.2 **Terrorist financing lists.** These checks identify persons associated with terrorist financing networks. It is about blocking the flow of funds that could support terrorism. Compliance requires screening against current CTF lists and immediate escalation of any potential match without disclosing sensitive screening detail.
- 3.3.1.3 **Internal fraud databases.** Internal records flag customers previously linked to fraud or abuse of the bank's services. It is about preventing known bad actors from re-entering the relationship. Compliance requires checking the internal fraud database and referring positive matches to the appropriate review process.
- 3.3.1.4 **Politically Exposed Person (PEP) databases.** PEP screening identifies individuals in prominent public positions who carry elevated corruption risk. It is about applying enhanced scrutiny to higher-risk relationships. Compliance requires screening against PEP data and, on a match, escalating to compliance for enhanced due diligence before continuing.

### 3.3.2. Possible Outcomes

#### 3.3.2.1. Passed

**3.3.2.1.1** Customer continues onboarding.

#### 3.3.2.2. Match Found

**3.3.2.2.1** Customer is referred to compliance review.

---

# 4. Savings Account Compliance

## 4.1. Eligibility

### 4.1.1. Requirements

- 4.1.1.1 **Valid identity verification.** The savings applicant must already be a fully KYC-verified individual before a deposit product is opened. It is about ensuring funds are held for a properly identified person and not an anonymous party. Compliance requires current, unexpired identity verification on file, refreshed if it has lapsed.
- 4.1.1.2 **Existing customer record.** Savings products are added to an established banking relationship rather than opened cold. It is about linking deposits to a known customer with an existing risk profile. Compliance requires a confirmed existing customer record, and the workflow must pause if that relationship cannot be located.
- 4.1.1.3 **Reference account available.** A linked reference account provides a verified funding and withdrawal channel for the savings product. It is about reducing fraud, ownership, and repayment risk by tying savings to a known account. Compliance requires a verified reference account belonging to the customer, with escalation if it appears to belong to someone else.

---

## 4.2. Ongoing Monitoring

### 4.2.1. The bank may review

- 4.2.1.1 **Large deposits.** Unusually large single deposits can indicate laundering, unexplained wealth, or third-party funds. It is about verifying that significant inflows are consistent with the customer's known profile. Compliance requires monitoring large deposits and may require a source-of-funds explanation before the funds are treated as clear.
- 4.2.1.2 **Frequent deposits.** A high frequency of deposits may signal structuring or funnelling activity. It is about detecting patterns that break up value to avoid scrutiny. Compliance requires monitoring deposit frequency and escalating repetitive patterns for AML review.
- 4.2.1.3 **Unusual savings behaviour.** Behaviour that deviates sharply from the customer's established pattern is a potential red flag. It is about spotting sudden changes that may indicate account misuse. Compliance requires baselining normal behaviour and reviewing material deviations.
- 4.2.1.4 **Numerous incoming transfers.** Many incoming transfers, especially from varied senders, can indicate money mule or pass-through activity. It is about identifying accounts used to aggregate third-party funds. Compliance requires monitoring incoming transfer volume and escalating suspicious aggregation.
- 4.2.1.5 **Cross-border money movements.** Funds moving across borders raise sanctions, tax, and laundering considerations. It is about ensuring international flows are legitimate and properly screened. Compliance requires reviewing cross-border movements and applying sanctions and source-of-funds checks where indicated.

---

## 4.3. Source Of Funds Verification

**4.3.1** The bank may request the origin of savings.

### 4.3.2. Examples

- 4.3.2.1 **Salary income.** Regular employment earnings are a common and low-risk source of savings. It is about confirming that deposits align with the customer's stated occupation and pay. Compliance may require payslips or salary-credit evidence to validate the origin.
- 4.3.2.2 **Bonus payments.** One-off or periodic bonuses can explain larger-than-usual deposits. It is about distinguishing legitimate variable pay from unexplained inflows. Compliance may require employer documentation confirming the bonus.
- 4.3.2.3 **Property sale.** Proceeds from selling real estate can account for substantial one-time deposits. It is about verifying a genuine underlying transaction. Compliance may require a sale contract or completion statement as evidence.
- 4.3.2.4 **Inheritance.** Inherited funds are a legitimate but sometimes large and irregular source. It is about confirming the funds derive from an estate rather than an illicit origin. Compliance may require probate or estate documentation.
- 4.3.2.5 **Investment proceeds.** Returns from selling investments can explain notable inflows. It is about linking deposits to verifiable market activity. Compliance may require brokerage or settlement statements.
- 4.3.2.6 **Pension payouts.** Lump-sum or regular pension payments are a recognised source of funds. It is about confirming retirement income as the deposit origin. Compliance may require pension provider documentation.
- 4.3.2.7 **Business income.** Earnings drawn from a business can fund personal savings. It is about ensuring the business activity is legitimate and declared. Compliance may require business accounts or tax records to substantiate the income.

---

# 5. Children's Savings Accounts

## 5.1. Required Parties

### 5.1.1. Child

- 5.1.1.1 **Full legal name.** The child's complete legal name identifies the beneficial account holder even though a guardian operates the account. It is about ensuring the account is correctly attributed to the minor. Compliance requires the child's name to match an official document such as a birth certificate or identity record.
- 5.1.1.2 **Date of birth.** The child's date of birth confirms minor status and drives the age-based restrictions on products. It is about applying the correct eligibility and prohibition rules. Compliance requires a verified date of birth and escalation if the child's age cannot be confirmed.

### 5.1.2. Legal Guardian

- 5.1.2.1 **Name.** The guardian's full legal name identifies the adult legally responsible for operating the account. It is about establishing who has authority to act for the minor. Compliance requires the guardian's name to match verified identity evidence.
- 5.1.2.2 **Address.** The guardian's residential address supports identity proofing and correspondence. It is about confirming the responsible adult's location and reachability. Compliance requires a verifiable current address for the guardian.
- 5.1.2.3 **Identity verification.** The guardian must complete full KYC identity verification in their own right. It is about ensuring the controlling adult is a properly identified customer. Compliance requires an accepted verification method and a valid government-issued document for the guardian.
- 5.1.2.4 **Parental authority verification.** The bank must confirm the guardian actually holds legal authority over the child. It is about preventing an unauthorised adult from controlling a minor's account. Compliance requires evidence of parental or legal guardianship and escalation whenever that authority cannot be established.

---

## 5.2. Restrictions

### 5.2.1. Children cannot

- 5.2.1.1 **Receive overdraft facilities.** Minors are barred from overdrafts because they cannot enter binding credit agreements. It is about preventing debt exposure for customers without legal capacity. Compliance requires overdraft features to remain disabled on all minor accounts.
- 5.2.1.2 **Apply for loans.** Children are prohibited from taking out loans of any kind. It is about protecting minors from repayment obligations they cannot legally assume. Compliance requires the agent to block and escalate any loan request involving a minor.
- 5.2.1.3 **Apply for credit cards.** Revolving credit cards are not available to minors. It is about keeping credit-risk products away from customers who cannot contract for them. Compliance requires credit-card workflows to reject minor applicants outright.
- 5.2.1.4 **Obtain unsecured credit.** Any form of unsecured credit is prohibited for children. It is about ensuring no lending exposure is created against a minor. Compliance requires all unsecured credit features to be unavailable on minor accounts.

### 5.2.2. Permitted Services

- 5.2.2.1 **Savings accounts.** Deposit-only savings accounts are allowed for minors under guardian control. It is about enabling safe saving without any credit exposure. Compliance requires guardian oversight and adherence to the minor-account restrictions.
- 5.2.2.2 **Children's current accounts.** Youth current accounts provide everyday banking without credit facilities. It is about giving minors supervised transactional access. Compliance requires guardian consent and that no overdraft or credit feature is attached.
- 5.2.2.3 **Youth debit cards.** Debit cards tied to available balances are permitted for minors. It is about allowing spending only from the child's own funds. Compliance requires the card to draw solely on cleared balances with no credit line.
- 5.2.2.4 **Savings plans.** Structured savings plans help minors build funds over time. It is about supporting long-term saving within permitted product limits. Compliance requires guardian involvement and that the plan carries no lending component.

---

# 6. Credit Card Compliance

## 6.1. Application Requirements

### 6.1.1. Customers must provide

- 6.1.1.1 **Verified identity.** A confirmed identity is the precondition for any credit product. It is about ensuring the applicant is a real, correctly identified person before credit is considered. Compliance requires completed KYC verification with a valid government-issued document.
- 6.1.1.2 **Verified address.** A confirmed residential address supports fraud prevention and creditworthiness assessment. It is about tying the application to a verifiable location. Compliance requires current, verifiable address evidence on file.
- 6.1.1.3 **Existing banking relationship.** Credit cards are offered to established customers rather than unknown applicants. It is about grounding the credit decision in a known history. Compliance requires a confirmed existing relationship, and the application pauses if it cannot be verified.
- 6.1.1.4 **Employment information.** Employment details indicate income stability and repayment capacity. It is about understanding the applicant's ability to service the credit. Compliance requires employment information and enhanced verification for self-employed applicants.
- 6.1.1.5 **Income information.** Declared income underpins affordability and limit decisions. It is about ensuring the customer can repay what they borrow. Compliance requires income information and supporting evidence where standard salary proof is unavailable.

---

## 6.2. Credit Assessment

### 6.2.1. The bank evaluates

- 6.2.1.1 **Income.** Income level is the primary driver of how much credit can responsibly be extended. It is about matching the credit limit to demonstrated earning capacity. Compliance requires validated income and human assessment before any limit is set.
- 6.2.1.2 **Employment stability.** Stable, continuous employment reduces default risk. It is about gauging the reliability of the applicant's income over time. Compliance requires review of employment tenure and type, with enhanced checks for irregular income.
- 6.2.1.3 **Existing liabilities.** Current debts affect how much additional credit is affordable. It is about ensuring total obligations remain sustainable. Compliance requires assessment of outstanding liabilities as part of the affordability review.
- 6.2.1.4 **Housing costs.** Rent or mortgage costs are a major fixed obligation that constrains repayment capacity. It is about capturing the applicant's committed outgoings. Compliance requires housing costs to be factored into the affordability calculation.
- 6.2.1.5 **Internal customer rating.** The bank's own behavioural rating reflects the customer's track record. It is about using existing relationship data to inform the decision. Compliance requires the internal rating to be considered but never manually overridden by the agent.
- 6.2.1.6 **Credit bureau information.** External bureau data reveals borrowing history and existing exposure elsewhere. It is about obtaining an independent view of creditworthiness. Compliance requires bureau data to be reviewed as part of the human credit assessment.

---

## 6.3. Credit Limit Rules

### 6.3.1. Classic Card

#### 6.3.1.1. Typical limit

- 6.3.1.1.1 **€1,000 - €5,000.** The Classic card sits in the entry-level credit band for standard retail customers. It is about offering modest, broadly affordable credit with lower risk exposure. Compliance requires the limit to stay within this range unless an exceptional-limit review and human approval are completed.

### 6.3.2. Gold Card

#### 6.3.2.1. Typical limit

- 6.3.2.1.1 **€5,000 - €15,000.** The Gold card offers a mid-tier limit for customers with stronger income and standing. It is about extending greater credit to lower-risk, established profiles. Compliance requires the limit to remain within this band unless enhanced verification and human approval justify an exception.

### 6.3.3. Platinum Card

#### 6.3.3.1. Typical limit

- 6.3.3.1.1 **€15,000 - €50,000.** The Platinum card provides the highest limit tier for premium, high-income customers. It is about serving affluent customers while managing correspondingly higher credit exposure. Compliance requires enhanced verification, robust income evidence, and human approval before granting limits in this range.

---

## 6.4. Enhanced Verification

### 6.4.1. May be required for

- 6.4.1.1 **High credit limits.** Large limits carry greater potential loss and warrant deeper scrutiny. It is about confirming the customer can support significant credit. Compliance requires additional income and affordability evidence plus human approval.
- 6.4.1.2 **Recent account openings.** New relationships have limited internal history to rely on. It is about compensating for the absence of a track record. Compliance requires extra verification to offset the thin relationship history.
- 6.4.1.3 **Self-employed customers.** Self-employed income is variable and harder to validate from salary evidence. It is about establishing genuine, sustainable earnings. Compliance requires documentation such as tax returns or business income statements, with escalation if the customer refuses but still wants to proceed.
- 6.4.1.4 **Foreign residents.** Customers resident abroad add jurisdictional and verification complexity. It is about managing cross-border identity and collectability risk. Compliance requires enhanced verification appropriate to the customer's residence.
- 6.4.1.5 **High-risk profiles.** Profiles flagged as higher risk require deeper due diligence before credit is granted. It is about ensuring elevated risk is properly understood and controlled. Compliance requires enhanced verification and human review before proceeding.

#### 6.4.1.6. Additional documentation may include

- 6.4.1.6.1 **Payslips.** Recent payslips evidence regular employment income. It is about corroborating declared salary with primary documents. Compliance requires payslips to be current and consistent with the stated income.
- 6.4.1.6.2 **Tax returns.** Tax returns validate income for self-employed or complex-income applicants. It is about confirming declared earnings against filed records. Compliance requires recent returns sufficient to substantiate the income.
- 6.4.1.6.3 **Business income statements.** These statements demonstrate the profitability of an applicant's business. It is about verifying income drawn from self-employment. Compliance requires statements that credibly support the declared income.
- 6.4.1.6.4 **Asset information.** Evidence of assets can support affordability where income alone is insufficient. It is about assessing the applicant's broader financial capacity. Compliance requires verifiable asset documentation where it is relied upon.

---

## 6.5. Prohibited Agent Actions

### 6.5.1. Agents may not

- 6.5.1.1 **Approve credit applications.** Only authorised human underwriters may grant credit. It is about keeping final lending decisions under human accountability. Compliance requires the agent to gather information and escalate, never to issue an approval.
- 6.5.1.2 **Override risk decisions.** Agents cannot reverse or bypass risk-based outcomes. It is about preserving the integrity of the bank's risk controls. Compliance requires risk decisions to stand unless changed through the proper human process.
- 6.5.1.3 **Override fraud alerts.** Fraud alerts must not be dismissed or worked around by the agent. It is about ensuring genuine fraud signals are acted upon. Compliance requires fraud alerts to trigger the defined response and escalation.
- 6.5.1.4 **Change risk ratings.** Agents cannot alter a customer's assigned risk rating. It is about maintaining accurate, tamper-resistant risk classifications. Compliance requires rating changes to occur only through authorised risk processes.

---

# 7. Domestic Money Transfers

## 7.1. SEPA Transfers

### 7.1.1. Required information

- 7.1.1.1 **Recipient name.** The payee's name is needed to identify who receives the funds and to support screening. It is about ensuring the payment reaches the intended, legitimate party. Compliance requires the recipient name before the payment instruction is constructed.
- 7.1.1.2 **IBAN.** The IBAN uniquely identifies the destination account within the SEPA area. It is about routing funds accurately and preventing misdirected payments. Compliance requires a valid IBAN and, for new payees, strong customer authentication.
- 7.1.1.3 **Amount.** The transfer amount defines the value moved and drives monitoring thresholds. It is about capturing exactly how much is being sent. Compliance requires a specified amount and additional authentication for high-value transfers.
- 7.1.1.4 **Reference text.** The reference explains the purpose of the payment for the recipient and for records. It is about providing traceability and context for the transaction. Compliance requires a reference before the instruction is finalised.

---

## 7.2. Strong Customer Authentication

### 7.2.1. Required when

- 7.2.1.1 **Adding a new payee.** Registering a previously unknown beneficiary is a high-risk change often exploited in scams. It is about confirming the account holder genuinely intends the new payment relationship. Compliance requires strong customer authentication before the payee is saved.
- 7.2.1.2 **Executing high-value transfers.** Large payments carry greater fraud and error impact. It is about adding assurance proportionate to the value at risk. Compliance requires an authentication challenge before a high-value transfer proceeds.
- 7.2.1.3 **Changing transfer settings.** Altering limits or payment configurations can weaken protective controls. It is about ensuring only the legitimate customer changes safety settings. Compliance requires authentication before such settings are modified.
- 7.2.1.4 **Using a new device.** An unrecognised device may indicate account takeover. It is about verifying the customer's identity from an untrusted context. Compliance requires additional authentication before sensitive actions on a new device.

#### 7.2.1.5. Methods

- 7.2.1.5.1 **Mobile approval.** Approving in the bank's mobile app ties authentication to a trusted, registered device. It is about confirming the action through a secured customer channel. Compliance requires the approval to be completed on the customer's enrolled device.
- 7.2.1.5.2 **Push notification approval.** A push challenge lets the customer confirm or reject an action in real time. It is about providing fast, out-of-band verification. Compliance requires the customer to positively approve the specific action.
- 7.2.1.5.3 **One-time password.** A single-use code sent to the customer verifies possession of a trusted channel. It is about proving control of the registered phone or token. Compliance requires the correct OTP to be entered before the action proceeds.

---

## 7.3. Transfer Monitoring

### 7.3.1. The bank may review

- 7.3.1.1 **Unusually large transfers.** Transfers well above the customer's norm can signal fraud or laundering. It is about catching outliers that deviate from established behaviour. Compliance requires monitoring for large transfers and escalating unexplained ones.
- 7.3.1.2 **Unusual recipients.** Payments to unexpected or high-risk beneficiaries warrant scrutiny. It is about detecting relationships inconsistent with the customer's profile. Compliance requires review of unusual recipients and escalation where risk is indicated.
- 7.3.1.3 **Rapid outgoing movements.** Fast, successive outflows may indicate account draining or funnelling. It is about spotting urgency patterns typical of fraud or mule activity. Compliance requires monitoring outgoing velocity and escalating suspicious bursts.
- 7.3.1.4 **New payees receiving large sums.** Large first payments to newly added payees are a classic scam indicator. It is about protecting customers from authorised-push-payment fraud. Compliance requires heightened scrutiny and authentication for such payments.

---

# 8. International Transfers

## 8.1. Additional Information Required

- 8.1.1 **Recipient name.** The beneficiary's name is essential for sanctions screening and correct delivery. It is about identifying exactly who receives cross-border funds. Compliance requires the full recipient name before screening begins.
- 8.1.2 **Bank name.** The receiving bank's name helps assess jurisdictional and counterparty risk. It is about knowing which institution will handle the funds. Compliance requires the bank name to be captured and screened.
- 8.1.3 **Account number.** The destination account number ensures funds reach the correct beneficiary account. It is about accurate routing in the receiving country. Compliance requires a valid account number appropriate to the destination.
- 8.1.4 **IBAN where applicable.** For jurisdictions using IBAN, this standardises destination identification. It is about precise routing where the format applies. Compliance requires a valid IBAN whenever the destination country uses one.
- 8.1.5 **SWIFT/BIC.** The SWIFT/BIC code identifies the beneficiary bank in the international network. It is about correctly directing the payment across borders. Compliance requires a valid SWIFT/BIC before the transfer is submitted.
- 8.1.6 **Country.** The destination country determines sanctions, embargo, and risk considerations. It is about assessing geographic exposure of the payment. Compliance requires the country to be identified and screened against sanctioned or embargoed jurisdictions.
- 8.1.7 **Transfer purpose.** The stated purpose supports AML analysis and detects suspicious intent. It is about understanding why the funds are being sent. Compliance requires a clear purpose, and unclear purposes must be routed for additional checks.

---

## 8.2. Additional Compliance Controls

### 8.2.1. The bank may verify

- 8.2.1.1 **Destination country.** The receiving jurisdiction drives the level of screening and control required. It is about identifying elevated geographic risk. Compliance requires screening the destination and stopping payments to sanctioned or embargoed regions.
- 8.2.1.2 **Sanctions exposure.** The bank checks whether any party or route touches sanctioned interests. It is about preventing prohibited transactions. Compliance requires sanctions screening before the transfer and immediate halt on any match.
- 8.2.1.3 **Embargo restrictions.** Embargoes prohibit dealings with specific regions or sectors. It is about ensuring no payment breaches an embargo. Compliance requires blocking embargoed destinations without offering workarounds.
- 8.2.1.4 **Beneficiary risk.** The characteristics of the recipient may indicate elevated risk. It is about assessing who ultimately benefits from the funds. Compliance requires review of beneficiary risk and escalation where concerns arise.
- 8.2.1.5 **Source of funds.** The origin of the money being sent may need to be established. It is about confirming the funds are legitimate. Compliance may require source-of-funds evidence before the transfer proceeds.
- 8.2.1.6 **Source of wealth.** For larger or higher-risk transfers, the customer's overall wealth origin may be examined. It is about ensuring the customer's finances are legitimately derived. Compliance may require source-of-wealth documentation for high-risk cases.

---

## 8.3. High-Risk Indicators

- 8.3.1 **Transfers to sanctioned jurisdictions.** Payments toward sanctioned regions are a critical red flag. It is about preventing breaches of sanctions law. Compliance requires the workflow to stop and escalate rather than proceed.
- 8.3.2 **Multiple international transfers.** A pattern of many cross-border payments may indicate layering. It is about detecting attempts to obscure the movement of funds. Compliance requires monitoring and AML escalation of such patterns.
- 8.3.3 **Large unexplained transfers.** Big transfers without a clear rationale suggest laundering risk. It is about ensuring significant flows are justified. Compliance requires a source-of-funds explanation and escalation where it is missing.
- 8.3.4 **Transfers with unclear purposes.** A vague or inconsistent stated purpose is a warning sign. It is about confirming the legitimate intent of the payment. Compliance requires clarification and additional checks before proceeding.
- 8.3.5 **Structuring behaviour.** Splitting transfers to stay under review thresholds is deliberate evasion. It is about identifying attempts to avoid scrutiny. Compliance requires escalation for AML review without coaching the customer on thresholds.

---

# 9. Anti-Money Laundering (AML)

## 9.1. AML Objectives

### 9.1.1. Detect and prevent

- 9.1.1.1 **Money laundering.** Money laundering disguises the illicit origin of funds by moving them through the financial system. It is about stopping criminals from legitimising proceeds of crime. Compliance requires due diligence, transaction monitoring, and escalation of suspicious activity.
- 9.1.1.2 **Terrorist financing.** Terrorist financing channels funds toward violent activity, often in small or ordinary-looking amounts. It is about cutting off financial support for terrorism. Compliance requires CTF screening and immediate escalation of any potential match.
- 9.1.1.3 **Fraud.** Fraud uses deception to obtain money or services unlawfully. It is about protecting customers and the bank from deceptive schemes. Compliance requires monitoring, protective action, and escalation of high-risk cases.
- 9.1.1.4 **Financial crime.** Financial crime spans bribery, corruption, and other illicit financial conduct. It is about keeping the bank from being used as a vehicle for such activity. Compliance requires vigilance, due diligence, and escalation when indicators appear.
- 9.1.1.5 **Sanctions violations.** Sanctions violations involve dealings with prohibited parties or regions. It is about preventing breaches of sanctions regimes. Compliance requires screening at defined events and halting any matched transaction.

---

## 9.2. Customer Due Diligence Levels

### 9.2.1. Standard Due Diligence

**9.2.1.1** Applied to most customers.

#### 9.2.1.2. Requirements

- 9.2.1.2.1 **Identity verification.** Standard due diligence begins with confirming who the customer is. It is about establishing a verified identity as the baseline control. Compliance requires accepted identity verification for most customers.
- 9.2.1.2.2 **Screening checks.** New customers are screened against sanctions, CTF, fraud, and PEP data. It is about filtering out prohibited or high-risk parties. Compliance requires completed screening with escalation on any match.
- 9.2.1.2.3 **Address confirmation.** Confirming the customer's address supports identity assurance and fraud prevention. It is about validating a key element of the customer profile. Compliance requires verifiable address evidence on file.

---

### 9.2.2. Enhanced Due Diligence

#### 9.2.2.1. Applied to

- 9.2.2.1.1 **PEPs.** Politically exposed persons carry heightened corruption and bribery risk. It is about applying deeper scrutiny to influential individuals. Compliance requires enhanced due diligence and senior sign-off where required.
- 9.2.2.1.2 **High-risk countries.** Customers connected to high-risk jurisdictions demand closer review. It is about managing elevated geographic exposure. Compliance requires enhanced checks and additional documentation.
- 9.2.2.1.3 **Complex ownership structures.** Layered or opaque ownership can hide the true controllers of funds. It is about seeing through structures to the real beneficiaries. Compliance requires identifying ultimate beneficial owners and understanding the structure.
- 9.2.2.1.4 **High-value customers.** Large exposures warrant proportionately deeper due diligence. It is about matching scrutiny to the size of the relationship. Compliance requires enhanced review and source-of-wealth understanding.

**9.2.2.1.5** Additional review is required.

---

## 9.3. AML Red Flags

### 9.3.1. Customer Behaviour

- 9.3.1.1 **Reluctance to provide information.** Unwillingness to supply required details can indicate concealment. It is about recognising evasiveness as a due-diligence warning sign. Compliance requires the missing information before proceeding and escalation if it is withheld.
- 9.3.1.2 **Contradicting information.** Inconsistent statements or documents suggest possible deception. It is about detecting mismatches that undermine trust in the profile. Compliance requires resolving contradictions and escalating unexplained ones.
- 9.3.1.3 **Use of third parties.** Acting through intermediaries can obscure the real party of interest. It is about identifying who actually controls the activity. Compliance requires understanding the third party's role and escalating where it is unclear.

### 9.3.2. Transaction Behaviour

- 9.3.2.1 **Frequent cash transactions.** Heavy cash use can be a means of introducing illicit funds. It is about flagging patterns that reduce traceability. Compliance requires monitoring cash activity and escalating anomalies.
- 9.3.2.2 **Rapid movement of funds.** Quick in-and-out flows are typical of layering. It is about spotting funds that pass through without economic purpose. Compliance requires monitoring velocity and escalating suspicious movement.
- 9.3.2.3 **Multiple transfers below thresholds.** Repeated sub-threshold payments indicate deliberate structuring. It is about catching attempts to avoid reporting triggers. Compliance requires escalation without coaching the customer on the thresholds.
- 9.3.2.4 **Circular payments.** Funds routed in loops between related accounts can disguise origin. It is about detecting artificial transaction flows. Compliance requires investigation and AML escalation of circular patterns.
- 9.3.2.5 **Sudden activity spikes.** Abrupt jumps in volume or value deviate from the norm. It is about identifying unexplained changes in behaviour. Compliance requires review of spikes against the customer's profile.

### 9.3.3. Geographic Indicators

- 9.3.3.1 **High-risk countries.** Links to high-risk jurisdictions raise the laundering risk of activity. It is about weighing geographic exposure in the assessment. Compliance requires enhanced scrutiny of related transactions.
- 9.3.3.2 **Sanctioned regions.** Any connection to sanctioned regions is a critical concern. It is about preventing prohibited dealings. Compliance requires screening and halting activity linked to sanctioned areas.
- 9.3.3.3 **Unusual international patterns.** Cross-border flows that lack a clear rationale are suspicious. It is about detecting geographic patterns inconsistent with the customer. Compliance requires review and escalation of unusual international activity.

---

## 9.4. Source Of Wealth Examples

- 9.4.1 **Salary accumulation.** Wealth built from years of employment income is a common, low-risk source. It is about explaining accumulated funds through steady earnings. Compliance may require employment and income history as evidence.
- 9.4.2 **Business ownership.** Value derived from owning a business can account for significant wealth. It is about tying wealth to a legitimate enterprise. Compliance may require business records and financials as support.
- 9.4.3 **Inheritance.** Inherited wealth is legitimate but can be large and irregular. It is about confirming the funds originate from an estate. Compliance may require probate or estate documentation.
- 9.4.4 **Investment gains.** Returns from investments over time can explain wealth. It is about linking wealth to verifiable market activity. Compliance may require investment statements as evidence.
- 9.4.5 **Sale of company.** Proceeds from selling a business can produce substantial wealth. It is about verifying a genuine underlying transaction. Compliance may require sale agreements or completion records.
- 9.4.6 **Sale of real estate.** Property disposals can account for large wealth. It is about confirming legitimate proceeds from a real transaction. Compliance may require sale contracts or settlement statements.

---

# 10. Business Account Compliance

## 10.1. Required Business Information

### 10.1.1. Sole Proprietor

- 10.1.1.1 **Business registration.** Registration evidence confirms the sole proprietorship legally exists. It is about establishing the legitimacy of the business entity. Compliance requires valid registration documentation before the account opens.
- 10.1.1.2 **Identity verification.** The proprietor must be personally identified as the responsible individual. It is about tying the business to a verified natural person. Compliance requires full KYC verification of the proprietor.
- 10.1.1.3 **Tax number.** A tax identifier links the business to its tax obligations. It is about ensuring correct tax treatment and reporting. Compliance requires a valid tax number on file.

### 10.1.2. Limited Company

- 10.1.2.1 **Commercial register extract.** The register extract proves the company's legal existence and standing. It is about verifying the entity through an authoritative source. Compliance requires a current extract from the commercial register.
- 10.1.2.2 **Articles of association.** The articles define how the company is governed and controlled. It is about understanding the company's structure and authority. Compliance requires the articles to be provided and reviewed.
- 10.1.2.3 **Shareholder structure.** The ownership breakdown reveals who holds and controls the company. It is about identifying the parties behind the entity. Compliance requires a clear shareholder structure to support beneficial-ownership checks.
- 10.1.2.4 **Director identities.** The directors are the individuals who legally act for the company. It is about verifying who controls day-to-day operations. Compliance requires identity verification for each director.

---

# 11. Beneficial Ownership (UBO)

## 11.1. Definition

**11.1.1** The bank must identify the natural persons who ultimately control or own the business.

---

## 11.2. Required Information

### 11.2.1. For each beneficial owner

- 11.2.1.1 **Name.** The beneficial owner's full legal name identifies the natural person in ultimate control. It is about naming the real people behind the business. Compliance requires the name to be verified against identity evidence.
- 11.2.1.2 **Date of birth.** The date of birth distinguishes the owner and supports screening. It is about uniquely identifying the individual. Compliance requires a verified date of birth for each owner.
- 11.2.1.3 **Nationality.** Nationality informs sanctions and jurisdictional risk for the owner. It is about assessing the owner's risk profile. Compliance requires nationality to be captured and screened.
- 11.2.1.4 **Address.** The owner's residential address supports identity and correspondence. It is about confirming where the controlling person resides. Compliance requires a verifiable address for each owner.
- 11.2.1.5 **Ownership percentage.** The stake held indicates the degree of ownership control. It is about quantifying each owner's interest. Compliance requires ownership percentages sufficient to identify all reportable owners.
- 11.2.1.6 **Control mechanism.** Control can arise through means other than direct shareholding. It is about capturing how the person actually exercises control. Compliance requires documenting the control mechanism for each owner.

---

## 11.3. Typical Trigger

### 11.3.1. Beneficial ownership review is required when

- 11.3.1.1 **Account is opened.** Onboarding is the first point at which owners must be identified. It is about establishing control transparency from the outset. Compliance requires full UBO identification before the business account is activated.
- 11.3.1.2 **Ownership changes.** Shifts in ownership can change who ultimately controls the entity. It is about keeping beneficial-owner records current. Compliance requires re-verification of UBO details when ownership changes.
- 11.3.1.3 **Significant control changes occur.** New control arrangements can alter the risk picture even without ownership changes. It is about capturing changes in effective control. Compliance requires a beneficial-ownership review whenever significant control changes.

---

# 12. Business Risk Assessment

## 12.1. The bank evaluates

- 12.1.1 **Industry sector.** The sector indicates inherent money-laundering and regulatory risk. It is about weighting risk by the nature of the business. Compliance requires the sector to be assessed and higher-risk industries to receive enhanced scrutiny.
- 12.1.2 **Expected transaction volume.** Anticipated volume sets a baseline for normal activity. It is about detecting later deviations from expectation. Compliance requires expected volume to be captured for monitoring.
- 12.1.3 **Geographic exposure.** The countries the business operates in drive sanctions and jurisdictional risk. It is about understanding cross-border risk exposure. Compliance requires geographic exposure to be assessed and screened.
- 12.1.4 **Ownership complexity.** Complex structures can conceal true control. It is about gauging how transparent the ownership is. Compliance requires complex structures to trigger enhanced due diligence.
- 12.1.5 **Expected annual turnover.** Projected turnover contextualises the scale of activity. It is about aligning monitoring with the size of the business. Compliance requires expected turnover to be recorded and monitored against.

---

# 13. Sanctions Compliance

## 13.1. Screening Events

### 13.1.1. Sanctions screening is performed

- 13.1.1.1 **During onboarding.** Screening at onboarding stops prohibited parties from ever entering the relationship. It is about filtering sanctioned individuals and entities at the gate. Compliance requires screening before the account is activated and escalation on any match.
- 13.1.1.2 **Before international transfers.** Cross-border payments are screened before funds leave. It is about preventing prohibited transactions from completing. Compliance requires pre-transfer screening and a full stop on any match.
- 13.1.1.3 **During ongoing monitoring.** Continuous screening catches parties added to lists after onboarding. It is about maintaining protection over the life of the relationship. Compliance requires periodic re-screening and escalation of new matches.
- 13.1.1.4 **After customer profile changes.** Profile changes can alter sanctions exposure and must trigger re-screening. It is about keeping screening current with the latest information. Compliance requires re-screening after material profile changes.

---

## 13.2. Restricted Activities

### 13.2.1. The bank must prevent

- 13.2.1.1 **Sanctioned individuals using services.** Prohibited persons must not gain access to banking services. It is about denying service to sanctioned parties entirely. Compliance requires blocking onboarding and access on a confirmed match.
- 13.2.1.2 **Transactions involving sanctioned entities.** Payments touching sanctioned entities are prohibited. It is about stopping any dealing with restricted organisations. Compliance requires halting matched transactions and escalating for review.
- 13.2.1.3 **Payments to embargoed regions.** Funds must not flow to embargoed jurisdictions. It is about enforcing regional embargoes. Compliance requires blocking such payments and refusing to suggest workarounds.

---

# 14. Fraud Prevention Controls

## 14.1. Device Monitoring

### 14.1.1. The bank may assess

- 14.1.1.1 **New devices.** An unfamiliar device may signal account takeover. It is about detecting access from unrecognised hardware. Compliance requires additional verification before sensitive actions on a new device.
- 14.1.1.2 **Suspicious devices.** Devices with risk signals warrant closer scrutiny. It is about identifying compromised or fraudulent access points. Compliance requires stepped-up authentication and possible blocking of suspicious devices.
- 14.1.1.3 **Device location anomalies.** Access from unexpected locations can indicate fraud. It is about spotting improbable or inconsistent geographic access. Compliance requires additional verification when location anomalies appear.

---

## 14.2. Behaviour Monitoring

### 14.2.1. The bank may assess

- 14.2.1.1 **Login patterns.** Deviations in how and when a customer logs in can reveal compromise. It is about baselining normal access and spotting anomalies. Compliance requires monitoring login behaviour and challenging suspicious sessions.
- 14.2.1.2 **Payment behaviour.** Changes in payment habits may indicate fraud or coercion. It is about detecting activity inconsistent with the customer's norm. Compliance requires monitoring payments and escalating anomalies.
- 14.2.1.3 **Spending patterns.** Unusual spending can signal a compromised account. It is about identifying out-of-pattern expenditure. Compliance requires review of anomalous spending against the customer profile.
- 14.2.1.4 **Card usage anomalies.** Irregular card use, such as unexpected locations or amounts, is a fraud indicator. It is about catching misuse of card credentials. Compliance requires monitoring card activity and applying graduated response actions.

---

## 14.3. Response Actions

| Ref | Risk Level | Action |
|-----|----------|------|
| 14.3.1 | Low | Allow transaction |
| 14.3.2 | Medium | Additional verification |
| 14.3.3 | High | Temporary block |
| 14.3.4 | Critical | Freeze account and escalate |

---

# 15. Agent Compliance Rules

## 15.1. The Agent May

**15.1.1** ✅ **Explain products.** The agent may describe how banking products work and their features. It is about helping customers understand available options without giving regulated advice. Compliance requires factual, balanced explanations that stop short of personalised recommendations.

**15.1.2** ✅ **Explain fees.** The agent may set out the charges associated with products and services. It is about ensuring fee transparency for the customer. Compliance requires accurate fee information consistent with published terms.

**15.1.3** ✅ **Compare savings products.** The agent may compare features of different savings options. It is about helping the customer weigh choices objectively. Compliance requires neutral comparisons without steering into regulated advice.

**15.1.4** ✅ **Compare credit cards.** The agent may lay out the differences between card products. It is about supporting an informed choice. Compliance requires factual comparison without promising approval or terms.

**15.1.5** ✅ **Calculate interest.** The agent may compute illustrative interest figures. It is about giving the customer clear numeric context. Compliance requires calculations to be accurate and clearly illustrative, not guarantees.

**15.1.6** ✅ **Explain onboarding requirements.** The agent may describe what is needed to open a product. It is about preparing the customer for the process. Compliance requires the requirements to reflect the actual KYC and eligibility rules.

**15.1.7** ✅ **Gather customer information.** The agent may collect the details needed to progress a workflow. It is about assembling the data required for verification and assessment. Compliance requires information to be captured securely and used only for the current request.

**15.1.8** ✅ **Initiate account opening workflows.** The agent may start the process of opening an account. It is about moving an eligible customer into the proper workflow. Compliance requires all prerequisites and screening to be respected before completion.

**15.1.9** ✅ **Initiate card applications.** The agent may begin a credit-card application. It is about collecting and submitting the application for assessment. Compliance requires the agent to gather facts and escalate, never to approve.

**15.1.10** ✅ **Initiate transfer workflows.** The agent may start a payment on the customer's behalf. It is about progressing a legitimate, authenticated transfer. Compliance requires complete details, authentication where triggered, and screening.

**15.1.11** ✅ **Escalate compliance reviews.** The agent may hand a case to a human specialist. It is about routing matters that exceed the agent's authority. Compliance requires escalation whenever a mandatory event or ambiguity arises.

---

## 15.2. The Agent Must Not

**15.2.1** ❌ **Approve loans.** Lending approvals are reserved for authorised human underwriters. It is about keeping credit decisions under human accountability. Compliance requires the agent to escalate any loan approval request.

**15.2.2** ❌ **Approve credit cards.** The agent cannot grant a credit-card application. It is about ensuring credit risk is decided by humans. Compliance requires the agent to gather information and route the case for assessment.

**15.2.3** ❌ **Approve overdrafts.** Overdraft facilities cannot be authorised by the agent. It is about preventing unapproved credit exposure. Compliance requires overdraft requests to be escalated.

**15.2.4** ❌ **Override compliance decisions.** The agent cannot reverse compliance outcomes. It is about protecting the integrity of compliance controls. Compliance requires decisions to stand unless changed through proper human process.

**15.2.5** ❌ **Override AML findings.** AML determinations must not be dismissed by the agent. It is about ensuring money-laundering signals are acted upon. Compliance requires AML findings to trigger escalation, not override.

**15.2.6** ❌ **Override sanctions screening.** Sanctions matches cannot be reinterpreted or bypassed. It is about enforcing sanctions law without exception. Compliance requires the workflow to stop and escalate on any match.

**15.2.7** ❌ **Override fraud blocks.** The agent cannot lift or bypass fraud controls. It is about keeping protective blocks effective. Compliance requires fraud blocks to remain until resolved through the proper process.

**15.2.8** ❌ **Provide regulated financial advice.** The agent must not give personalised regulated advice. It is about staying within the boundary of information, not advice. Compliance requires the agent to explain and compare without recommending.

**15.2.9** ❌ **Bypass customer authentication.** Authentication controls cannot be skipped. It is about preventing unauthorised access and actions. Compliance requires authentication to be completed before sensitive operations.

---

# 16. Mandatory Escalation Events

## 16.1. The agent must transfer the case to a human compliance specialist when

- 16.1.1 **AML alert is triggered.** An AML alert signals possible money laundering that exceeds the agent's authority. It is about ensuring suspicious activity gets expert human review. Compliance requires immediate escalation and a pause on the affected workflow.
- 16.1.2 **PEP match is detected.** A PEP match indicates a higher-risk relationship requiring enhanced due diligence. It is about applying senior human judgement to sensitive cases. Compliance requires escalation without disclosing sensitive screening detail.
- 16.1.3 **Sanctions match is detected.** A sanctions match is a critical legal stop condition. It is about preventing prohibited dealings. Compliance requires the workflow to halt immediately and escalate to compliance.
- 16.1.4 **Fraud risk is high.** High fraud risk demands protective action beyond the agent's scope. It is about safeguarding the customer and the bank. Compliance requires escalation and protective measures such as blocks.
- 16.1.5 **Credit approval is required.** Any credit decision must be made by a human underwriter. It is about keeping lending accountable to people. Compliance requires escalation for the approval decision.
- 16.1.6 **Beneficial ownership is unclear.** Uncertain ownership prevents proper due diligence. It is about ensuring true controllers are identified. Compliance requires escalation until ownership is clarified.
- 16.1.7 **Source of funds cannot be established.** Unverifiable fund origins pose laundering risk. It is about confirming money is legitimate before proceeding. Compliance requires escalation when the source cannot be established.
- 16.1.8 **Customer disputes a compliance decision.** A disputed decision needs impartial human handling. It is about ensuring fair review outside the agent. Compliance requires the dispute to be escalated to a specialist.

---

# 17. Audit & Logging Requirements

## 17.1. Every regulated action should record

- 17.1.1 **Customer identifier.** The customer identifier ties every logged action to the correct person. It is about ensuring records are attributable and searchable. Compliance requires the identifier to be captured for each regulated action.
- 17.1.2 **Timestamp.** A precise timestamp establishes when the action occurred. It is about building a reliable chronological record. Compliance requires accurate timestamps on every logged event.
- 17.1.3 **Conversation transcript.** The transcript preserves what was said and decided. It is about evidencing the full context of the interaction. Compliance requires the transcript to be retained as part of the audit trail.
- 17.1.4 **Agent version.** Recording the agent version enables traceability of behaviour. It is about knowing which software produced a decision. Compliance requires the agent version to be logged.
- 17.1.5 **Model version.** The model version identifies the reasoning engine behind actions. It is about reproducibility and accountability of outcomes. Compliance requires the model version to be captured.
- 17.1.6 **Risk decisions.** Logged risk decisions show how risk was assessed and handled. It is about evidencing the risk rationale. Compliance requires risk decisions to be recorded in the audit trail.
- 17.1.7 **Compliance checks executed.** A record of checks performed proves controls were applied. It is about demonstrating due diligence. Compliance requires every executed check to be logged.
- 17.1.8 **APIs called.** Recording tool and API calls shows what actions were actually taken. It is about traceability of system operations. Compliance requires the APIs invoked to be captured.
- 17.1.9 **Human approvals.** Logged approvals evidence where a human authorised an action. It is about capturing accountability for approvals. Compliance requires human approvals and pending confirmations to be recorded.
- 17.1.10 **Final outcome.** The final outcome confirms how the action concluded. It is about establishing the definitive result of the workflow. Compliance requires the outcome to be logged and only marked complete when the final state confirms it.

**17.1.11** This audit trail must be immutable, searchable, and available for regulatory review.

---

# 18. Concrete Operating Rules

## 18.1. Identity And Eligibility Rules

### 18.1.1. The agent should apply these concrete controls during regulated workflows

- 18.1.1.1 A customer record is incomplete when any required KYC field is missing, expired, or inconsistent with a submitted identity document. The agent must ask for the missing field or explain that human review is required before continuing the workflow. The agent must not treat a partial profile, remembered conversation detail, or unverifiable statement as verified identity evidence.
- 18.1.1.2 A customer who is under 18 cannot independently open or modify a regulated banking product unless the relevant product rules explicitly allow it. The agent must require a legal guardian and guardian identity verification before starting a minor-related account workflow. The agent must escalate when guardianship, parental authority, or the child's age cannot be confirmed.
- 18.1.1.3 A new product application must be paused when the customer's existing banking relationship cannot be confirmed. The agent may explain the missing prerequisite and collect information needed to locate the customer record. The agent must not bypass the prerequisite by creating an application as an anonymous or unverified customer.
- 18.1.1.4 A current or savings account workflow must use a verified reference account before accepting funding instructions. The agent must tell the customer that the reference account is needed to reduce fraud, repayment, and ownership risks. The agent must escalate if the provided reference account appears to belong to another person or cannot be matched to the customer.

## 18.2. Credit And Card Rules

### 18.2.1. The agent should apply these concrete controls for credit-card interactions

- 18.2.1.1 A credit-card application is not ready for assessment until identity, address, employment, income, and existing banking relationship information are present. The agent may gather these facts and explain the typical review process. The agent must not state or imply that gathering these facts means the card has been approved.
- 18.2.1.2 A requested card limit above the product's typical range must be treated as an exceptional-limit request. The agent must explain that additional credit review and human approval are required before the limit can be granted. The agent must not promise, pre-approve, or manually override a limit decision.
- 18.2.1.3 A self-employed applicant must be routed to enhanced verification when income cannot be validated from standard salary evidence. The agent may request appropriate documentation such as tax returns, business income statements, or asset information. The agent must escalate if the customer refuses documentation but still asks to proceed.
- 18.2.1.4 A customer asking for a credit-card approval decision must receive a process explanation rather than a decision from the agent. The agent may describe the factors reviewed, including income, stability, liabilities, housing costs, internal rating, and credit bureau information. The agent must escalate the case whenever a final approve, decline, or override decision is requested.

## 18.3. Transfer And Sanctions Rules

### 18.3.1. The agent should apply these concrete controls for payment safety

- 18.3.1.1 A domestic transfer cannot proceed unless recipient name, IBAN, amount, and reference text are available. The agent must ask for any missing transfer field before constructing the payment instruction. The agent must require strong customer authentication when the transfer adds a new payee, uses a new device, or meets high-value criteria.
- 18.3.1.2 An international transfer must include destination country, bank details, beneficiary details, and transfer purpose before screening. The agent must route the payment for additional checks when sanctions exposure, embargo risk, unclear purpose, or beneficiary risk is present. The agent must not suggest workarounds for sanctioned or embargoed destinations.
- 18.3.1.3 A sanctions, terrorist-financing, or PEP match must stop the workflow immediately. The agent must tell the customer that the case requires compliance review without disclosing sensitive screening logic or list details. The agent must not override, dismiss, or reinterpret the match even if the customer claims it is a mistake.
- 18.3.1.4 A pattern of rapid outgoing payments, multiple international transfers, or repeated transfers just below review thresholds must be treated as suspicious activity. The agent must escalate the pattern for AML review and avoid coaching the customer on thresholds. The agent may explain that the bank reviews unusual payment behaviour to protect customers and meet regulatory obligations.

## 18.4. Fraud, Privacy And Audit Rules

### 18.4.1. The agent should apply these concrete controls for operational integrity

- 18.4.1.1 A login from a new device or unusual location must trigger additional verification before sensitive account changes are made. The agent must keep the requested action pending until authentication succeeds or a human support process takes over. The agent must not reveal account details while the verification challenge is unresolved.
- 18.4.1.2 A customer reporting suspected fraud must be prioritised for protective action and human escalation when risk is high. The agent may explain temporary blocks, replacement cards, and next steps in general terms. The agent must not investigate, accuse a party, or reverse a transaction without the appropriate fraud process.
- 18.4.1.3 Personal data must only be used for the signed-in customer's current service request. The agent must not reveal another customer's data, compare customers, or infer information from unrelated records. The agent must minimise repeated personal data in responses unless the customer specifically needs confirmation.
- 18.4.1.4 Every regulated action must leave an auditable record that includes the customer identifier, timestamp, checks performed, tools or APIs called, and final outcome. The agent must capture human approvals and pending confirmations when they are part of the workflow. The agent must not describe an action as completed unless the audit trail and final state confirm completion.
