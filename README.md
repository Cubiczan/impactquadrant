# RollupOps by Impact Quadrant
**Business brokerage, reimagined and automated.** The agent does the broker's whole job: finds buyers, sources sellers, qualifies both sides, matches, and runs the deal room and checkout. **Agents run the brokerage; humans guarantee trust.**

Built for the Terac Zero-Human Company Hackathon (NYC, 2026-10-24). Focus: small and medium **manufacturing & distribution** businesses (precision machining, industrial distribution). Global-ready (country/state fields, jurisdiction gate).

- Dashboard: https://dashboard-six-fawn-83.vercel.app (calculator: /calculator.html, webhook: /api/whop-webhook)
- Marketplace (Wix): impactquadrant.info/marketplace. See `wix/APPLY.md`.
- Trust, KYC, jurisdiction: `TRUST.md` · Demo script: `DEMO.md`

## Pipeline (`python -m rollupops.pipeline --whop`)
1. **Buyers**: curated public signals (`data/buyer_signals.json`) + Impact Quadrant PE registry + live **Exa** search (`EXA_API_KEY`).
2. **Buyer activity score** from public signals (add-on press, partner pages, corp-dev hiring), buy-box inference, qualification (proof of funds before unlock).
3. **Sourcing** (curated + Exa), automated checks (company site, PE-owned exclusion, dedupe, focus; no mining).
4. **Value-driver scoring** + valuation **estimate** (SDE <$2M, EBITDA ≥$2M; never mixed; range, not asking price).
5. **Blind teaser** (no name/city/site) + PII lint; down-payment estimate; stale-deal timer.
6. **Trust ladder** (`trust.py`): Whop KYC identity + Terac human verification of sellers and buyers (Terac off until org exists).
7. **Jurisdiction gate** (`jurisdiction.py`): flat-fee info products everywhere; success fees OFF.
8. **Whop** (`marketplace.py`): per-listing checkouts on the seller's connected account with a 20% application fee, for both PE and individual buyers.
9. **Outreach drafts** for sellers (free confidential valuation) and buyers; lint; **never sent** (Needs Shyam).
10. Outputs in `out/*.json`; `python -m rollupops.wix_push` exports `wix/targets_import.csv` (dry run unless `--send`).

## Whop (sandbox, business biz_a5nrqqjxL9lLAv)
| Product | Segment | Price | Checkout |
|---|---|---|---|
| RollupOps Deal Flow | PE platforms | $499/mo | https://sandbox.whop.com/checkout/plan_G3u2jR3bL0Mva |
| Off-Market Deal Drop | Individual buyers | $49/mo | https://sandbox.whop.com/checkout/plan_PobV6T3Hak8FP |
| Deal Teardown | Individual buyers | $149 | https://sandbox.whop.com/checkout/plan_K5LRRtkdPMull |
| Per-target unlock | PE $250 / individual $19–99 by deal size | 20% app fee | per listing in `out/03_listings.json` |
Seller connected account (sandbox): `biz_GUUF0UYxQLOE5S`. Verifier transfers are queued (sandbox has no payouts). Referral line: Whop Partners pays 30% of Whop's eligible gross profit on referred businesses (tracked at whop.com/partners).
**Going live is a Needs-Shyam switch**: `WHOP_LIVE=1` + `NEEDS_SHYAM_APPROVED=1` + production key. Not done.

## Safety
Sandbox only. No real sends. No secrets in repo (`.env.example`). We don't hold funds or store SSNs. Not legal advice; see TRUST.md.

## Run
```
cp .env.example .env  # fill locally
pip install -r requirements.txt  # stdlib only today
python -m rollupops.pipeline --whop && python -m rollupops.wix_push && python scripts/build_wix.py
cp out/*.json dashboard/public/data/ && (cd dashboard && vercel deploy --prod)
```


## Sell-side success fee (commission)
`rollupops/commission.py` - click-through engagement letter (versioned, SHA-256 hashed) + Whop checkouts (sandbox).
- Fee: 10% / 8% / 6% / 4% tiers on price excluding real estate, min $15k, payable only at close. Whop caps a purchase at $100k, so the fee is invoiced in equal tranches of $95k or less.
- Optional $1,500 retainer, credited at close, only where advance fees are allowed (not RED states or NV).
- Gate (`jurisdiction.gate`): seller AND buyer GREEN, asset sale, no real estate, we never hold funds. Otherwise declined: "Not available in your location yet".
- GREEN: 24 US states/DC plus BR, CH, DE, ES, JP, MX. See STATE_LICENSING.md. Output: `out/08_commission.json`; dashboard section "Sell-side success fee".

## Operating scope: GREEN only
**Available in 24 US states + 6 countries** (AL, CT, DC, DE, IA, IN, KS, MA, MD, MO, MS, MT, NC, ND, NJ, NM, OK, PA, SC, TN, TX, VA, VT, WV + BR, CH, DE, ES, JP, MX).
`jurisdiction.scope_gate()` declines sellers and buyers anywhere else with "Not available in your location yet" (no flat-fee products, no referrals). The pipeline drops non-GREEN listings.

## Live Whop products (biz_hBjAsGrR4pbWup)
| Product | Price | Checkout |
|---|---|---|
| PE Deal Flow | $499/mo | https://whop.com/checkout/plan_vw11C9YfuqPBB |
| Off-Market Deal Drop | $49/mo | https://whop.com/checkout/plan_Y29FScJ0r99WQ |
| Deal Teardown | $149 | https://whop.com/checkout/plan_uJeL4VQ1BA9XB |
| Sell-side retainer (GREEN only) | $1,500 | https://whop.com/checkout/plan_ZoPJy2iiRGuYU |
Catalog: `data/whop_live_catalog.json`. Per-listing success-fee checkouts stay sandbox until approved.

## Marketplace backend (DuckDB)
Agents run both sides: `buyer_agent` keeps PE/platform buy mandates fresh from public signals, `seller_agent` keeps the seller pipeline (verification, Terac flag, GREEN jurisdiction), `matcher` proposes scored matches. `python -m rollupops.db` builds `data/rollupops.duckdb`. See [SCHEMA.md](SCHEMA.md).

**Multi-agent cycle:** `python -m rollupops.orchestrator --exa` runs parallel buyer-search and seller-search agents (Exa), the matcher and the Whop agent. The dashboard's Agents panel shows runs, matches and Whop teaser payloads. Nothing is sent to anyone.

## Impact Quadrant Precision Sale Process (live, flat fee)
| Service | Price | Checkout |
|---|---|---|
| Business Valuation Report | $499 one-time | https://whop.com/checkout/plan_WtHSQEw7OfZqz |
| Sale-Readiness Audit | $999 one-time | https://whop.com/checkout/plan_9V5dcLhzS24to |
| Buyer Landscape Report | $299 one-time | https://whop.com/checkout/plan_qMZc3rTzx0pOB |
| Confidential Teaser + CIM | $1,500 one-time | https://whop.com/checkout/plan_rHZvi1hNfO0RW |
| Quality-of-Earnings Lite | $2,500 one-time | https://whop.com/checkout/plan_5GulOsl8BSUJz |
On a `payment.succeeded` for one of these plans, `rollupops.fulfillment` drafts the deliverable from DuckDB + Exa into `out/fulfillment/` for human review. Nothing is sent automatically. Not legal, tax or financial advice.

## Service fulfillment (agents prepare, human approves, no auto-send)
`rollupops/fulfillment.py`, orders in `data/orders.duckdb` (gitignored). States: paid → intake_sent → intake_received → drafting → awaiting_review → delivered.
1. Whop payment (webhook / `orchestrator.whop_sync`) → intake agent builds a product-specific questionnaire + document list and a tokenized `/intake.html?order=…` link.
2. Intake submitted (`/api/intake`, HMAC token) → analysis agents (DuckDB buyer mandates/comps + Exa market sources) write markdown + PDF to `out/fulfillment/` with status awaiting_review.
3. Human approves (dashboard button → `/api/approve`, needs `FULFILL_APPROVE_SECRET`) → delivered via Whop. Sandbox orders record delivery and send nothing.
Demo: `FULFILL_APPROVE_SECRET=... python -m rollupops.fulfillment teaser_cim`. Sample output: `docs/sample_deliverables/`.

## Public copy
This public repo is a scrubbed mirror of a private working repo. Partner overlays (priority-sponsor lanes, platform lists, buyer registry, blocked marketing terms) live only in untracked `data/raw/private/`; without them the pipeline runs on public sources. `MARKETING_BLOCKED_TERMS` (comma-separated) adds confidential terms the marketing agent must never emit.
