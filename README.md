# ImpactQuadrant
**Business brokerage, reimagined and automated.** The agent does the broker's whole job: finds buyers, sources sellers, qualifies both sides, matches, and runs the deal room and checkout. **Agents run the brokerage; humans guarantee trust.**

Built for the Terac Zero-Human Company Hackathon (NYC, 2026-10-24). Focus: small and medium **manufacturing & distribution** businesses (precision machining, industrial distribution). Global-ready (country/state fields, jurisdiction gate).

- Live Services (buy now): https://www.impactquadrant.info/services
- Dashboard: https://dashboard-six-fawn-83.vercel.app (calculator: /calculator.html, webhook: /api/whop-webhook)
- Marketplace (Wix): impactquadrant.info/marketplace. See `wix/APPLY.md`.
- Trust, KYC, jurisdiction: `TRUST.md` · Demo script: `DEMO.md`

## Pipeline (`python -m rollupops.pipeline --whop`)
1. **Buyers**: curated public signals (`data/buyer_signals.json`) + ImpactQuadrant PE registry + live **Exa** search (`EXA_API_KEY`).
2. **Buyer activity score** from public signals (add-on press, partner pages, corp-dev hiring), buy-box inference, qualification (proof of funds before unlock).
3. **Sourcing** (curated + Exa), automated checks (company site, PE-owned exclusion, dedupe, focus; no mining).
4. **Value-driver scoring** + valuation **estimate** (SDE <$2M, EBITDA ≥$2M; never mixed; range, not asking price).
5. **Blind teaser** (no name/city/site) + PII lint; down-payment estimate; stale-deal timer.
6. **Trust ladder** (`trust.py`): Whop KYC identity + Terac human verification of business owners only; PE fund buyers are vetted personally by the owner.
7. **Jurisdiction gate** (`jurisdiction.py`): flat-fee info products everywhere; success fees OFF.
8. **Whop** (`marketplace.py`): per-listing checkouts on the seller's connected account with a 20% application fee, for both PE and individual buyers.
9. **Outreach drafts** for sellers (free confidential valuation) and buyers; lint; **never sent** (Needs Shyam).
10. Outputs in `out/*.json`; `python -m rollupops.wix_push` exports `wix/targets_import.csv` (dry run unless `--send`).

## Safety
No real outreach sends without owner approval. Terac checks only blue-collar owner verification; PE buyers are vetted personally by the owner. No secrets in repo (`.env.example`). We don't hold funds or store SSNs. Not legal advice; see TRUST.md.

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
Catalog: `data/whop_live_catalog.json`. Per-listing success-fee checkouts stay sandbox until approved.

## Marketplace backend (DuckDB)
Agents run both sides: `buyer_agent` keeps PE/platform buy mandates fresh from public signals, `seller_agent` keeps the seller pipeline (verification, Terac flag, GREEN jurisdiction), `matcher` proposes scored matches. `python -m rollupops.db` builds `data/rollupops.duckdb`. See [SCHEMA.md](SCHEMA.md).

**Multi-agent cycle:** `python -m rollupops.orchestrator --exa` runs parallel buyer-search and seller-search agents (Exa), the matcher and the Whop agent. The dashboard's Agents panel shows runs, matches and Whop teaser payloads. Nothing is sent to anyone.

## ImpactQuadrant Precision Sale Process (live, flat fee)
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

## Where humans help (and where they don't)
Terac human-in-the-loop runs in exactly ONE place, behind `TERAC_ENABLED=1`: **blue-collar business owner verification** (consented identity-and-intent call we run; one US reviewer reviews the redacted notes/transcript on our page; paid only after we approve). With the flag off, items queue as `pending_human`.

**No buyer review.** PE fund buyers are vetted personally by the owner, never by Terac or any automated review; no code path sends a buyer to review.

No Terac on: teasers, subscriptions, scoring, matching, marketing, checkout, service fulfillment. Fulfillment deliverables go out only after the owner's own approval. Marketing posts go out only after the owner approves the final text. Queues: `dashboard/public/data/human_checks.json` → dashboard "Human checks" panel.
### Terac (real API)
`rollupops/terac.py` talks to Terac REST v2 (`https://terac.com/api/external/v2`) with `TERAC_API_KEY` from the environment. Read-only calls: org context, list opportunities, get feasibility, get submissions. Free (explicit only): `request_feasibility(kind)` for the owner template. Spending: `launch()` requires `TERAC_LIVE=1` **and** the check id set to `true` in untracked `data/terac_approvals.json` by the owner. The orchestrator never creates, launches or approves anything.

## Submission

- Demo video (2 min, captions): [submission/demo.mp4](submission/demo.mp4) — [view on GitHub](https://github.com/Cubiczan/impactquadrant/blob/main/submission/demo.mp4)
- Pitch deck (PDF): [submission/impactquadrant-deck.pdf](submission/impactquadrant-deck.pdf)

## Website UI

All page sources are in [`/web`](web/README.md): the Wix Services embed and Velo page code (https://www.impactquadrant.info, /services, /marketplace) and the Vercel dashboard frontend (https://dashboard-six-fawn-83.vercel.app: dashboard, calculator, intake, review). Run locally with `cd web/dashboard/public && python3 -m http.server 8080`, or `cd dashboard && npx vercel dev` for the API routes. See `web/README.md` for the per-page table.
