# ImpactQuadrant DuckDB backend (`data/rollupops.duckdb`)
Build (idempotent, drops & rebuilds): `python -m rollupops.db` — also runs at the end of `python -m rollupops.pipeline`.
DDL: `sql/schema.sql`; views: `sql/views.sql`. Every source table carries `src_file` provenance.

## Builds
- `python -m rollupops.db` → `data/rollupops.duckdb` (PUBLIC, committed): no contact names/emails/phones, no agreement status.
- `python -m rollupops.db --private` → `/workspace/contests/terac/data/rollupops_private.duckdb` (never committed): contacts + private overlays (`signed_buyers.csv`), which give the matcher a buyer-relationship boost.
- `python -m rollupops.orchestrator [--exa] [--n 5]` → one full multi-agent cycle (below), builds both DBs and writes `dashboard/public/data/agents.json`.
- Raw user workbooks (they contain work emails/phones) stay in `ROLLUPOPS_PRIVATE_RAW`; tables record `file::sheet` provenance in `src_file`.

## Multi-agent orchestration (around Whop)
1. **buyer-search agents** (one per vertical) query Exa in parallel → `buyer_signals` (+ new lead platforms); results cached in `data/exa_cache/` (emails/phones scrubbed) so builds stay idempotent.
2. **seller-search agents** (one per vertical × GREEN state) query Exa → `operators` → `seller_pipeline`.
3. `buyer_agent` → `buyer_mandates`; the Partner A workbook's Master Platform List rows are **authoritative** (`authoritative=TRUE`, $2M+ EBITDA, founder-owned, non-broker, US) and override keyword-inferred mandates.
4. `seller_agent` → `seller_pipeline` (GREEN jurisdiction gate, Terac flag).
5. `matcher` → `matches` (top 3 per seller, score ≥55; rationale names the criteria applied).
6. `whop_agent` → `whop_outbox`: blind-teaser product + checkout payloads (no seller identity). Products are created on Whop only if `WHOP_AUTOPUBLISH=1`; access is gated by a Whop membership (NDA + proof of funds).
7. `whop_sync` pulls payments from the live Whop business into `whop_events`; `dashboard/api/whop-webhook` verifies and logs events in real time.

## Agents run both sides + matching (`rollupops/agents.py`)
| agent | side | reads | writes |
|---|---|---|---|
| `buyer_agent` | buy | platforms, platform_verticals, buyer_signals | `buyer_mandates` (activity score from public signals, refreshed_at) |
| `seller_agent` | sell | listings, jurisdictions | `seller_pipeline` (verification_status, terac_check_required, jurisdiction_status) |
| `matcher` | match | `v_match_candidates`, buyer_mandates | `matches` (score, rationale, status proposed→intro_requested→nda→closed) |
Every run logs to `agent_runs` and every step to `agent_actions` (agent, side, input, output, ts).
No outreach is sent; status changes past `proposed` are human-approved (`agents.advance`).

## Tables (new)
- `candidate_buyer_map`, `exclusions` (from the consolidated rollup workbook), `documents` (IQ sale-process doc), `whop_outbox`, `whop_events`
- `sponsors` now carries website/HQ/roll-up model/active sectors/firm refresh status; `operators` carries ownership, size, sale-intent, lane.

## Tables
- `jurisdictions` US states + countries, GREEN/YELLOW/RED (from state_licensing.json)
- `sponsors`, `platforms`, `platform_verticals`, `portfolio_companies`, `buyer_signals` — buy side
- `operators`, `listings` — sell side
- `contacts` — public DB keeps name/sponsor/email_domain only; `email` NULL unless built with `ROLLUPOPS_INCLUDE_PII=1` from private raw
- `raw_records` — generic PII-scrubbed ingest of any xlsx/docx/csv/md dropped in `ROLLUPOPS_PRIVATE_RAW` (default `/workspace/contests/terac/data/raw`, never committed)

## Views
`v_green_jurisdictions`, `v_platform_activity`, `v_listing_states`, `v_match_candidates` (vertical + geography + size + GREEN seller state).
