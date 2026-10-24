"""Jurisdiction gate (NOT legal advice). Source: state_licensing.json {_disclaimer, states:{ST:{status,basis,source,verified,state_ma_broker_relief}}, countries:{CC:{...}}}.
Rules:
- Success fee/commission ONLY if seller AND buyer jurisdictions are GREEN (and verified not 'unverified'), US-only,
  asset sale, fee basis excludes real estate/leases, and we never hold funds.
- Stock/share sales: only within the federal M&A broker exemption + state relief (state_ma_broker_relief), else partner broker-dealer.
- RED/YELLOW (or unknown) -> 'licensed partner broker' referral for any success-fee work.
- Flat-fee info/verification/subscriptions everywhere; NO advance seller listing fees in RED states or NV.
- Non-US: success fee allowed only for GREEN countries (researched 2026-10-24, see STATE_LICENSING.md); else info products only.
Commission is a SANDBOX product until WHOP_LIVE + NEEDS_SHYAM_APPROVED."""
import json, os
from pathlib import Path
SRC = Path(os.environ.get("STATE_LICENSING_JSON", str(Path(__file__).resolve().parent.parent / "data/state_licensing.json")))
US_STATES = {"North Carolina": "NC", "South Carolina": "SC", "Georgia": "GA", "Florida": "FL", "Virginia": "VA", "Alabama": "AL"}
def _load():
    try: return json.loads(SRC.read_text())
    except Exception: return {}
def lookup(country="US", region=None):
    d = _load(); country = (country or "US").upper()
    if country != "US":
        e = (d.get("countries") or {}).get(country) or {}
        status = e.get("status", "UNKNOWN")
        if status == "GREEN" and "unverified" in str(e.get("verified", "")).lower(): status = "YELLOW"
        return {"status": status, "basis": e.get("basis", "no entry"), "source": e.get("source"), "us": False, "ma_relief": False, "state": country}
    st = US_STATES.get(region, region or "")
    e = (d.get("states") or {}).get(st.upper()) if st else None
    if not e: return {"status": "UNKNOWN", "basis": "no state on record", "us": True, "ma_relief": False, "state": st}
    status = e["status"]
    if status == "GREEN" and str(e.get("verified", "")).lower().startswith("unverified"): status = "YELLOW"
    return {"status": status, "basis": e["basis"], "source": e.get("source"), "us": True, "ma_relief": bool(e.get("state_ma_broker_relief")), "state": st}
def gate(seller=("US", None), buyer=("US", None), deal_structure="asset", fee_basis_includes_real_estate=False):
    s, b = lookup(*seller), lookup(*buyer)
    both_green = s["status"] == "GREEN" and b["status"] == "GREEN"
    if deal_structure == "stock" and not (s["us"] and b["us"]): both_green = False  # non-US share deals -> partner
    if deal_structure == "stock": structure_ok = both_green and s["ma_relief"] and b["ma_relief"]  # + federal M&A broker exemption
    else: structure_ok = both_green and not fee_basis_includes_real_estate
    route = "direct success fee (RollupOps engagement letter)" if structure_ok else ("partner broker-dealer" if deal_structure == "stock" and both_green else "licensed partner broker referral")
    red_or_nv = s["status"] == "RED" or s.get("state") == "NV"
    return {"seller": s["status"], "buyer": b["status"], "seller_state": s.get("state"), "success_fee_eligible": structure_ok,
            "success_fee_enabled": structure_ok, "success_fee_route": route,
            "flat_fee_products_enabled": True,  # info/verification/subscriptions everywhere
            "advance_seller_listing_fee_allowed": (not red_or_nv) and s["us"],
            "non_us_info_only": not (s["us"] and b["us"]) and not structure_ok, "never_hold_funds": True}
