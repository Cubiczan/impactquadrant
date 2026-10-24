# Weekly metrics Page: spec only (not created)

**Audience:** Shyam. **Cadence:** Mondays 8:00 AM ET, covering the prior Mon–Sun. **Sources:** Mixpanel (via `/api/track` events), Whop (payments/memberships via webhook log), prospecting DuckDB/Algolia.

## Sections
1. **Funnel (Mixpanel):** scorecard_viewed → scorecard_started → scorecard_completed → pricing_viewed → checkout_clicked → checkout_completed. Counts, step conversion %, week-over-week delta. Split by `device` and `utm_source`.
2. **Score bands:** completed scorecards by `score_band`, and checkout rate per band (feeds nurture routing).
3. **Revenue (Whop):** Snapshot sales ($100), Deal Access ($49/mo) and Deal Room ($129/mo) new/churned members, MRR, refunds, disputes.
4. **Checkout clicks by plan:** plan_DxqY6XEluwGE6 / plan_dz3xCCAiGVTns / plan_wFIIKYKAZbP1n.
5. **Prospecting:** new prospects stored, dupes skipped, DNC blocks, PE-owned flags (by GREEN state/trade), credits spent per tool.
6. **Content:** approved posts published, clicks by `utm_campaign`.
7. **Flags:** any step with >30% WoW drop; tracking proxy returning `mixpanel_not_configured`.

## Build notes
- Mixpanel Query API needs a service account (secret via secure input box); do not reuse the project token.
- `checkout_completed` should be emitted server-side from the Whop webhook (payment.succeeded) so it can't be spoofed; not wired yet.
