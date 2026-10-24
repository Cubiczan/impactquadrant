# RollupOps DuckDB backend (`data/rollupops.duckdb`)
Build (idempotent, drops & rebuilds): `python -m rollupops.db` — also runs at the end of `python -m rollupops.pipeline`.
DDL: `sql/schema.sql`; views: `sql/views.sql`. Every source table carries `src_file` provenance.

## Agents run both sides + matching (`rollupops/agents.py`)
| agent | side | reads | writes |
|---|---|---|---|
| `buyer_agent` | buy | platforms, platform_verticals, buyer_signals | `buyer_mandates` (activity score from public signals, refreshed_at) |
| `seller_agent` | sell | listings, jurisdictions | `seller_pipeline` (verification_status, terac_check_required, jurisdiction_status) |
| `matcher` | match | `v_match_candidates`, buyer_mandates | `matches` (score, rationale, status proposed→intro_requested→nda→closed) |
Every run logs to `agent_runs` and every step to `agent_actions` (agent, side, input, output, ts).
No outreach is sent; status changes past `proposed` are human-approved (`agents.advance`).

## Tables
- `jurisdictions` US states + countries, GREEN/YELLOW/RED (from state_licensing.json)
- `sponsors`, `platforms`, `platform_verticals`, `portfolio_companies`, `buyer_signals` — buy side
- `operators`, `listings` — sell side
- `contacts` — public DB keeps name/sponsor/email_domain only; `email` NULL unless built with `ROLLUPOPS_INCLUDE_PII=1` from private raw
- `raw_records` — generic PII-scrubbed ingest of any xlsx/docx/csv/md dropped in `ROLLUPOPS_PRIVATE_RAW` (default `/workspace/contests/terac/data/raw`, never committed)

## Views
`v_green_jurisdictions`, `v_platform_activity`, `v_listing_states`, `v_match_candidates` (vertical + geography + size + GREEN seller state).
