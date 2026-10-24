"""Sales-swarm inbox: new sellers + new PE buyers ingested each orchestrator cycle.
Sellers: data/inbox/sellers_from_swarm.csv (git-ignored). Deduped, GREEN jurisdictions only.
Buyers:  PE buyer registry CSV from the swarm (path via ROLLUPOPS_BUYER_REGISTRY). Free-text columns
         (cross_ref, found_by, reach_status) are never loaded."""
import csv, json, os, re
from pathlib import Path
from . import jurisdiction
ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data/inbox"
SELLERS = INBOX / "sellers_from_swarm.csv"
BUYERS = Path(os.environ.get("ROLLUPOPS_BUYER_REGISTRY", "/workspace/pipeline/outreach/impact-quadrant/pe-buyer-registry/registry.csv"))
SEEN = INBOX / ".seen.json"
CC = {"united states": "US", "usa": "US", "us": "US", "brazil": "BR", "switzerland": "CH", "germany": "DE", "spain": "ES", "japan": "JP", "mexico": "MX"}
def _cc(c): c = (c or "US").strip(); return CC.get(c.lower(), c.upper())
def _dom(u): return re.sub(r"^(https?://)?(www\.)?", "", (u or "").lower()).split("/")[0]
def _rows(p): return list(csv.DictReader(open(p, newline="", encoding="utf-8-sig"))) if p.exists() else []
def sellers():
    out, keys = [], set()
    for r in _rows(SELLERS):
        cc, st = _cc(r.get("country")), (r.get("state") or "").strip().upper() or None
        k = _dom(r.get("website")) or (r.get("company", "").strip().lower(), st)
        if not r.get("company") or k in keys: continue
        if not jurisdiction.available(cc, st if cc == "US" else None): continue
        keys.add(k); out.append({**r, "country": cc, "state": st, "key": str(k)})
    return out
def buyers():
    out, keys = [], set()
    for r in _rows(BUYERS):
        if (r.get("platform") or "unknown") == "unknown": continue
        k = (r["platform"].strip().lower(), (r.get("portfolio_company") or "").strip().lower())
        if k in keys: continue
        keys.add(k); out.append({c: r.get(c) for c in ("platform", "pe_sponsor", "portfolio_company", "city", "state", "trade", "acquired_date", "source_url")} | {"key": "|".join(k)})
    return out
def cycle_counts():
    """Call once per orchestrator cycle: totals + rows not seen in earlier cycles."""
    INBOX.mkdir(parents=True, exist_ok=True)
    seen = json.loads(SEEN.read_text()) if SEEN.exists() else {"sellers": [], "buyers": []}
    s, b = sellers(), buyers()
    ns = [x for x in s if x["key"] not in set(seen["sellers"])]; nb = [x for x in b if x["key"] not in set(seen["buyers"])]
    SEEN.write_text(json.dumps({"sellers": sorted({*seen["sellers"], *(x["key"] for x in s)}), "buyers": sorted({*seen["buyers"], *(x["key"] for x in b)})}))
    return {"sellers_total": len(s), "new_sellers": len(ns), "buyers_total": len(b), "new_buyers": len(nb),
            "sellers_feed": SELLERS.exists(), "buyers_feed": BUYERS.exists()}
def load(b):
    """Load inbox rows into a db builder (both public and private builds)."""
    from .taxonomy import verticals
    for r in sellers():
        b.operator(r["company"], "data/inbox/sellers_from_swarm.csv", trade=r.get("trade"), vertical=verticals(r.get("trade"))[0], town=r.get("city"),
                   state=r["state"], country=r["country"], website=r.get("website"), notes=f"swarm {r.get('found_at','')} {r.get('est_revenue_band','')}".strip(), independent=True)
    for r in buyers():
        pid = b.platform(r["platform"], r["pe_sponsor"], r["trade"], "swarm:pe_buyer_registry", regions_json=json.dumps([r["state"]]))
        b.signal(pid, "registry", r["acquired_date"], r["portfolio_company"], r["source_url"], "swarm:pe_buyer_registry")
