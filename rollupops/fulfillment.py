"""Fulfillment stub for Precision Sale Process services. Triggered by a Whop payment (webhook or orchestrator whop_sync).
Builds a DRAFT deliverable from DuckDB (marketplace data) + Exa (public comps / buyers) into out/fulfillment/ for HUMAN REVIEW.
Never sends anything. Not legal, tax or financial advice."""
import json, datetime as dt
from pathlib import Path
from . import exa
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/fulfillment"
CAT = json.loads((ROOT / "data/whop_live_catalog.json").read_text())["products"]
PLAN2SKU = {v["plan_id"]: k for k, v in CAT.items()}
DISCLAIMER = "Draft for human review. Estimates only; not legal, tax, accounting or financial advice."
SECTIONS = {
 "valuation": ["Earnings basis (SDE/EBITDA)", "Comparable transactions", "Multiple range", "Value range", "Key value drivers"],
 "readiness": ["P&L normalization", "Add-backs (documented / undocumented)", "Risk flags", "90-day fix list"],
 "buyer_landscape": ["Active buyers in vertical/region (public signals)", "Typical multiples paid", "Deal structures seen"],
 "teaser_cim": ["Blind teaser (PII-linted)", "CIM: overview, operations, customers, financials, growth, transaction"],
 "qoe_lite": ["Revenue & margin trends", "Add-back support", "Customer concentration", "Net working capital"],
}
def _duck(vertical=None, state=None):
    try:
        import duckdb
        p = next((ROOT / "data").glob("*public*.duckdb"), None) or next((ROOT / "data").glob("*.duckdb"), None)
        if not p: return {}
        con = duckdb.connect(str(p), read_only=True)
        q = lambda s, a=(): [dict(zip([d[0] for d in con.description], r)) for r in con.execute(s, a).fetchall()]
        out = {"buyers": q("SELECT p.name platform, b.* FROM buyer_mandates b JOIN platforms p USING(platform_id) WHERE (? IS NULL OR b.vertical = ?) LIMIT 25", [vertical, vertical])}
        con.close(); return out
    except Exception as e: return {"duckdb_error": str(e)[:200]}
def fulfill(payment):
    plan = (payment.get("plan") or {}).get("id") or payment.get("plan_id"); sku = PLAN2SKU.get(plan)
    if not sku or sku not in SECTIONS: return {"skipped": f"plan {plan} has no fulfillment"}
    md = payment.get("metadata") or {}; vertical, state = md.get("vertical"), md.get("state")
    q = {"valuation": f"{vertical or 'small manufacturing'} business sold EBITDA multiple 2026",
         "buyer_landscape": f"private equity platform add-on acquisition {vertical or 'manufacturing distribution'} {state or ''} 2026"}.get(sku)
    draft = {"sku": sku, "service": CAT[sku]["title"], "payment_id": payment.get("id"), "created": dt.datetime.now().isoformat(timespec="seconds"),
             "status": "DRAFT - needs human review before delivery", "disclaimer": DISCLAIMER,
             "inputs_needed": ["3 years P&L + tax returns", "customer list (top 10 share)", "add-back schedule"] if sku != "buyer_landscape" else ["vertical", "region"],
             "sections": {s: None for s in SECTIONS[sku]}, "duckdb": _duck(vertical, state),
             "exa": [{"title": r.get("title"), "url": r.get("url")} for r in (exa._search(q, 8) if q else [])]}
    OUT.mkdir(parents=True, exist_ok=True); f = OUT / f"{sku}_{payment.get('id','manual')}.json"
    f.write_text(json.dumps(draft, indent=1, default=str)); return {"draft": str(f.relative_to(ROOT)), "sku": sku}
