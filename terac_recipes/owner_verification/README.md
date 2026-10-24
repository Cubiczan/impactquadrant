# Terac recipe: owner verification (ImpactQuadrant' only Terac check)

Built on the Terac Cookbook (https://github.com/TeracAI/terac-cookbook) and the Terac MCP (https://terac.com/mcp).
PE buyers never go to Terac; they are vetted personally.

Flow: consented call -> redacted summary on token-gated review page -> 1 general-population US reviewer
(10 min, manual_review so payment waits for our approval) -> JSON verdict per result_schema.json
(verified | concerns | fail, reasons, red_flags).

- `study.json` — exact draft spec (terac_create_opportunity). Uses synthetic demo-owner-001 only.
- `run.py replay` — free offline replay (no key, no spend).
- `run.py draft` — creates/updates DRAFT via REST (free). Requires TERAC_API_KEY env.
- `run.py launch --confirm <opportunity_id>` — spends credit. Only after explicit human approval.

Current draft: paaztect07z1246r47i71m93, $7.50 total (1 x $7.50 machine estimate), NOT launched.
