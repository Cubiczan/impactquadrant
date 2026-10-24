"""Jurisdiction gate (NOT legal advice). Source: state_licensing.json {_disclaimer, states:{ST:{status,basis,source,verified,state_ma_broker_relief}}, countries:{CC:{...}}}.
Rules:
- Success fee/commission ONLY if seller AND buyer jurisdictions are GREEN (and verified not 'unverified'), US-only,
  asset sale, fee basis excludes real estate/leases, and we never hold funds.
- Stock/share sales: only within the federal M&A broker exemption + state relief (state_ma_broker_relief), else partner broker-dealer.
- RED/YELLOW (or unknown) -> 'licensed partner broker' referral for any success-fee work.
- Flat-fee info/verification/subscriptions everywhere; NO advance seller listing fees in RED states or NV.
- Non-US: info products only, no success fees.
Build default: commission features are OFF regardless; the gate only reports eligibility."""
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
        return {"status": e.get("status", "UNKNOWN"), "basis": e.get("basis", "no entry"), "us": False, "ma_relief": False}
    st = US_STATES.get(region, region or "")
    e = (d.get("states") or {}).get(st.upper()) if st else None
    if not e: return {"status": "UNKNOWN", "basis": "no state on record", "us": True, "ma_relief": False, "state": st}
    status = e["status"]
    if status == "GREEN" and str(e.get("verified", "")).lower().startswith("unverified"): status = "YELLOW"
    return {"status": status, "basis": e["basis"], "source": e.get("source"), "us": True, "ma_relief": bool(e.get("state_ma_broker_relief")), "state": st}
def gate(seller=("US", None), buyer=("US", None), deal_structure="asset", fee_basis_includes_real_estate=False):
    s, b = lookup(*seller), lookup(*buyer)
    both_green = s["status"] == "GREEN" and b["status"] == "GREEN" and s["us"] and b["us"]
    if deal_structure == "stock": structure_ok = both_green and s["ma_relief"] and b["ma_relief"]  # + federal M&A broker exemption
    else: structure_ok = both_green and not fee_basis_includes_real_estate
    route = "eligible (commission still OFF in build)" if structure_ok else ("partner broker-dealer" if deal_structure == "stock" and both_green else "licensed partner broker referral")
    red_or_nv = s["status"] == "RED" or s.get("state") == "NV"
    return {"seller": s["status"], "buyer": b["status"], "seller_state": s.get("state"), "success_fee_eligible": structure_ok,
            "success_fee_enabled": False, "success_fee_route": route,
            "flat_fee_products_enabled": True,  # info/verification/subscriptions everywhere
            "advance_seller_listing_fee_allowed": (not red_or_nv) and s["us"],
            "non_us_info_only": not (s["us"] and b["us"]), "never_hold_funds": True}
