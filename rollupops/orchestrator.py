"""Orchestrator: one marketplace cycle around Whop.
 1. buyer-search agents (per sponsor/vertical) + seller-search agents (per vertical x GREEN state) hit Exa IN PARALLEL
 2. rebuild DuckDB (public + private), replaying cached Exa results; buyer_agent/seller_agent/matcher/whop_agent run in order
 3. whop_sync pulls payments/memberships from Whop into whop_events (feedback loop; webhook at dashboard /api/whop-webhook logs live)
 4. export public, PII-free agent stats to dashboard/public/data/agents.json
No outreach. Whop products created only when WHOP_AUTOPUBLISH=1 (default: payloads in whop_outbox).
Run: python -m rollupops.orchestrator [--exa] [--n 5]"""
import json, os, sys, time, datetime as dt
from pathlib import Path
import duckdb
from . import agents, db
ROOT = Path(__file__).resolve().parent.parent
BUYER_TASKS = [
 {"agent": "buyer_search:home_services_mep", "side": "buy", "vertical": "home_services_mep", "query": "2026 press release private equity backed HVAC plumbing platform acquires family-owned company add-on"},
 {"agent": "buyer_search:exterior", "side": "buy", "vertical": "exterior", "query": "2026 private equity roofing platform add-on acquisition residential roofing company"},
 {"agent": "buyer_search:precision_machining", "side": "buy", "vertical": "precision_machining", "query": "2026 private equity backed precision machining platform completes add-on acquisition"},
]
SELLER_TASKS = [
 {"agent": "seller_search:home_services_mep:NC", "side": "sell", "vertical": "home_services_mep", "state": "NC", "query": "family-owned HVAC and plumbing company North Carolina serving since 1980s multiple locations"},
 {"agent": "seller_search:precision_machining:SC", "side": "sell", "vertical": "precision_machining", "state": "SC", "query": "family-owned CNC precision machine shop South Carolina founded decades ago"},
 {"agent": "seller_search:distribution:TX", "side": "sell", "vertical": "distribution", "state": "TX", "query": "family-owned industrial MRO distributor Texas founded 1970s"},
]
def whop_sync(con):
    r = agents.Run(con, "whop_sync", "whop"); key = os.environ.get("WHOP_PROD_API_KEY")
    if not key: return r.done({"skipped": "no WHOP_PROD_API_KEY"})
    import urllib.request
    req = urllib.request.Request(f"https://api.whop.com/api/v1/payments?account_id={agents.os.environ.get('WHOP_COMPANY_ID','biz_hBjAsGrR4pbWup')}&first=50",
                                 headers={"Authorization": f"Bearer {key}"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp: data = json.loads(resp.read()).get("data", [])
    except Exception as e: return r.done({"error": str(e)[:200]})
    for p in data:  # amounts + plan only; no buyer PII stored
        con.execute("INSERT OR REPLACE INTO whop_events VALUES (?,?,?,?,?,?,?)", [p.get("id"), "payment:" + str(p.get("status")), (p.get("plan") or {}).get("id"),
                    (p.get("membership") or {}).get("id"), p.get("total") or p.get("usd_total"), json.dumps(p.get("metadata") or {}), agents.now()])
    from . import fulfillment  # Precision Sale Process: draft deliverables for paid plans (human review, no sends)
    drafted = [fulfillment.fulfill(p) for p in data if str(p.get("status")) in ("paid", "succeeded")]
    return r.done({"payments": len(data), "intakes_created": [d["order_id"] for d in drafted if "order_id" in d and not d.get("duplicate")]})
def export(con, path):
    q = lambda s: [dict(zip([d[0] for d in con.description], r)) for r in con.execute(s).fetchall()]
    out = {"generated": str(agents.now()), "agents": q("SELECT * FROM v_agent_summary ORDER BY side, agent"),
           "counts": {t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ["sponsors", "platforms", "buyer_mandates", "operators", "seller_pipeline", "matches", "whop_outbox", "whop_events", "agent_runs", "agent_actions"]},
           "authoritative_mandates": con.execute("SELECT count(*) FROM buyer_mandates WHERE authoritative").fetchone()[0],
           "matches_by_vertical": q("SELECT sp.vertical, count(*) n, round(max(score)) top FROM matches m JOIN seller_pipeline sp USING(seller_id) GROUP BY 1 ORDER BY 2 DESC"),
           "top_matches": q("SELECT p.name platform, sp.vertical, sp.state, round(m.score) score, m.status FROM matches m JOIN buyer_mandates b USING(mandate_id) JOIN platforms p USING(platform_id) JOIN seller_pipeline sp USING(seller_id) ORDER BY m.score DESC LIMIT 15"),
           "whop_outbox": q("SELECT json_extract_string(payload_json,'$.product.title') title, published FROM whop_outbox")}
    path.write_text(json.dumps(out, indent=1, default=str)); return out
def cycle(use_exa=False, n=5):
    t0 = time.time(); fetched = agents.exa_fetch(BUYER_TASKS + SELLER_TASKS, n) if use_exa else []
    pub = db.build(private=False); priv = db.build(private=True)
    for p in (pub, priv):
        con = duckdb.connect(str(p)); whop_sync(con)
        orun = agents.Run(con, "orchestrator", "orchestrate", {"exa": use_exa, "n": n, "tasks": len(fetched)})
        orun.done({"exa_results": sum(len(f["results"]) for f in fetched), "secs": round(time.time() - t0, 1)})
        if p == pub: stats = export(con, ROOT / "dashboard/public/data/agents.json")
        con.close()
    return stats
if __name__ == "__main__":
    s = cycle("--exa" in sys.argv, int(sys.argv[sys.argv.index("--n") + 1]) if "--n" in sys.argv else 5)
    print(json.dumps({k: s[k] for k in ("counts", "authoritative_mandates", "agents")}, indent=1, default=str))
