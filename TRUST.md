# Trust, KYC & jurisdiction (RollupOps)
**Agents run the brokerage; humans guarantee trust.** Access scales with verification (trust ladder).

## Seller ladder
| Level | What | How | Unlocks |
|---|---|---|---|
| L1 automated | web/company-site check, PE-owned exclusion, dedupe; **todo (not wired today):** state SoS registration active, Google Business Profile/reviews/phone consistency, UCC lien / lawsuit / bankruptcy search. Identity: **Whop KYC** of the seller's connected account | `trust.seller_ladder` | Blind teaser publishes |
| L2 human (Terac) | Owner call: identity cross-check vs SoS filing/LinkedIn, authority & sell intent, consent to list, fraud flag. Disclosed script, no recording without consent | `terac.seller_verification` | "Verified by human (Terac)" badge |
| L3 financials | Owner uploads 3y tax returns + TTM P&L; agent reconciles to teaser range; add-backs >20% → QoE flag. **Never bank logins** | upload (todo) | "Financials reconciled" |

## Buyer ladder
| Level | What | Unlocks |
|---|---|---|
| L1 | Email verified | View teasers |
| L2 | Whop payment + click-through NDA (+ proof-of-funds attestation) | Blind deal memo (no owner identity) |
| L3 human (Terac) | PE: firm exists, recent add-ons, person employed (firm-domain email). Individual: proof of funds or SBA pre-qual letter review + short video confirm. Flag data harvesters, competitors, unfunded | Owner identity release |

Flagged at any level → **Needs Shyam** lane. Terac runs only on items that pass automated pre-screens, async, cap 5 participants per task. Terac is OFF (`TERAC_ENABLED=0`) until a researcher org exists.

## Fraud cases modeled
Fake listings (L1 + L2 call), competitor fishing (L3 buyer check + NDA + staged disclosure), inflated add-backs (L3 reconciliation, QoE flag), identity spoofing (Whop KYC + Terac cross-check), scraping/data harvesting (blind teasers, PII lint, paid + NDA gate, L3 before identity).

## Whop KYC: what we use (from docs.whop.com, checked 2026-10-24)
| Use | Endpoint / field |
|---|---|
| Create seller connected account | `POST /accounts` {parent_account_id, email, title, metadata.external_id} → `biz_…` (tested in sandbox) |
| Hosted KYC onboarding link | `POST /account_links` {account_id, use_case:"account_onboarding", return_url, refresh_url} → `url` (tested in sandbox; URL holds a short-lived token, never log it) |
| KYC status | `GET /identity_profiles?account_id=` → `status` ∈ not_started, pending, manual_review, approved, rejected, action_required; `profile_type` (individual/business), `payouts_enabled`, `verifications` (tested: returns empty / not_started for new sandbox account) |
| Verification sessions | `GET /verifications?payout_account_id=` / `GET /verifications/{id}` → `status` (requires_input … verified/approved/declined), `last_error_code` (e.g. selfie_face_mismatch, document_expired, id_number_mismatch) |
| Buyer payment | Whop checkout (`checkout_configurations`, `plans`); 3DS level configurable (`three_ds_level`) |

**Covers:** identity (document/selfie/ID number) of people/businesses receiving payouts, i.e. **sellers/brokers/verifiers via connected accounts**; business address and structure on business profiles.
**Gaps (not shown in docs):** no buyer-side identity KYC on checkout (payment only), no proof-of-funds, no business-registration (SoS) or lien/litigation checks, no sell-intent or authority-to-sell check. Terac human checks + L1 automation fill these. Sandbox: payouts/withdrawals not available, so transfers to verifiers are recorded as queued.

## What we do NOT do
We do not hold escrow, move deal funds, or store SSNs/bank logins. Whop handles payment KYC. Closing runs through a licensed escrow agent/attorney. We monetize **information and verification only** (subscriptions, unlocks, teardowns); **no success-fee commissions** in this build.

## Jurisdiction rules (`rollupops/jurisdiction.py`, data `data/state_licensing.json`)
> **Not legal advice.** Research snapshot 2026-10-24 (see `_disclaimer` and sources in the JSON); confirm with counsel before enabling any commission feature.
- Success fee/commission eligible only if seller AND buyer are GREEN (a GREEN marked "unverified" is treated as YELLOW), US-only, asset sale, fee basis excludes real estate/leases, never hold funds. Even when eligible, `success_fee_enabled` stays **False** in this build.
- Stock sales: only within the federal M&A broker exemption plus state relief (`state_ma_broker_relief`), else route to a partner broker-dealer.
- RED/YELLOW/unknown: route success-fee work to a **licensed partner broker** referral.
- Flat-fee info/verification/subscriptions: available everywhere; **no advance seller listing fees in RED states or NV**.
- Non-US: info products only, no success fees.
