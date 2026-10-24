"""Sell-side success-fee (commission) product. NOT legal advice. SANDBOX unless WHOP_LIVE=1 + NEEDS_SHYAM_APPROVED=1.
Eligibility = jurisdiction.gate(): seller AND buyer GREEN, asset sale, fee basis excludes real estate, we never hold funds.
Otherwise -> licensed partner-broker referral (no fee charged by us)."""
import json, hashlib
from pathlib import Path
from . import whop, jurisdiction
OUT = Path(__file__).resolve().parent.parent / "out"
RETAINER = 1500.0
MIN_FEE = 15000.0
TRANCHE_MAX = 95000.0
def fee_schedule(price):
    """Double-Lehman style on enterprise value excl. real estate: 10% first $1M, 8% next $1M, 6% next $1M, 4% above. Min $15k."""
    tiers, fee, rest = [(1e6, .10), (1e6, .08), (1e6, .06), (float("inf"), .04)], 0.0, price
    for size, pct in tiers:
        take = min(rest, size); fee += take * pct; rest -= take
        if rest <= 0: break
    return round(max(MIN_FEE, fee), 2)

AGREEMENT_VERSION = "SFA-2026-10-24"
AGREEMENT = """RollupOps Success-Fee Engagement (click-through) v{v}
1. Scope: Seller engages RollupOps (Impact Quadrant) to introduce qualified buyers for an ASSET SALE of the business described in listing {tid}.
2. Exclusions: The fee is calculated on purchase price EXCLUDING any real property, leases or interests in land. We do not broker real estate or securities.
3. Funds: RollupOps never holds deposits, escrow or purchase funds. All closing funds move through the parties' attorney/escrow agent.
4. Fee: Payable only at closing, from closing statement, per schedule: 10% of first $1M, 8% next $1M, 6% next $1M, 4% above; minimum ${min:,.0f}. Estimated fee at listed value: ${est:,.0f}.
5. Retainer: {ret}
6. Jurisdiction: Offered only where seller ({s}) and buyer ({b}) jurisdictions are both rated GREEN in our licensing register; otherwise we refer to a licensed partner broker and charge nothing.
7. Term: 12 months; 12-month tail for buyers we introduced. Seller may terminate on 30 days' notice.
8. No legal, tax or investment advice. Seller should retain counsel. Electronic acceptance via Whop checkout constitutes signature (E-SIGN/UETA)."""

def terms(listing, gate, est_price):
    ret = f"Optional ${RETAINER:,.0f} marketing retainer, credited against fee at close." if gate["advance_seller_listing_fee_allowed"] else "No advance fee in this jurisdiction."
    txt = AGREEMENT.format(v=AGREEMENT_VERSION, tid=listing["targetId"], min=MIN_FEE, est=fee_schedule(est_price), ret=ret, s=gate.get("seller_state") or gate["seller"], b=gate["buyer"])
    return {"version": AGREEMENT_VERSION, "text": txt, "sha256": hashlib.sha256(txt.encode()).hexdigest()}

def _plan(price, title, tid, kind):
    r = whop.call("POST", "/checkout_configurations", {"mode": "payment",
        "plan": {"company_id": whop.BIZ, "currency": "usd", "plan_type": "one_time", "initial_price": price, "title": title},
        "metadata": {"app": "rollupops", "kind": kind, "target_id": tid, "agreement": AGREEMENT_VERSION},
        "redirect_url": "https://impactquadrant.info/thanks"})
    return {"checkout_id": r.get("id"), "purchase_url": r.get("purchase_url"), "price": price, "error": r.get("error") and r.get("body")}

def offer(listing, buyer=("US", None), do_whop=False):
    g = jurisdiction.gate((listing.get("country", "US"), listing.get("stateProvince")), buyer, "asset", False)
    est = listing.get("_val_lo") or 1e6
    o = {"targetId": listing["targetId"], "gate": g, "route": g["success_fee_route"], "est_fee_at_close": fee_schedule(est), "never_hold_funds": True}
    if not g["success_fee_eligible"]:
        o["route"] = jurisdiction.NOT_AVAILABLE; return o
    o["agreement"] = terms(listing, g, est)
    if do_whop:
        # fee-at-close invoice: one-time plan sent from closing statement; sandbox creates it now as a demo
        # Whop caps a single purchase at $100k -> fee invoiced in equal tranches <= $95k at close
        n = int(-(-o["est_fee_at_close"] // TRANCHE_MAX)); amt = round(o["est_fee_at_close"] / n, 2)
        o["success_fee_tranches"] = n
        o["success_fee_checkout"] = _plan(amt, f"Success fee {listing['targetId'][2:]}", listing["targetId"], f"success_fee 1/{n}")
        if g["advance_seller_listing_fee_allowed"]:
            o["retainer_checkout"] = _plan(RETAINER, f"Retainer {listing['targetId'][2:]}", listing["targetId"], "retainer")
    return o

def green_states():
    d = jurisdiction._load()
    us = sorted(k for k, v in d.get("states", {}).items() if jurisdiction.lookup("US", k)["status"] == "GREEN")
    intl = sorted(k for k in d.get("countries", {}) if jurisdiction.lookup(k)["status"] == "GREEN")
    return {"us": us, "countries": intl}

def run(listings, do_whop=False):
    offers = [offer(l, ("US", "NC"), do_whop) for l in listings]
    for l, o in zip(listings, offers):
        l["commission"] = {"route": o["route"], "est_fee": o["est_fee_at_close"], "url": (o.get("success_fee_checkout") or {}).get("purchase_url"), "tranches": o.get("success_fee_tranches"), "tranche_amount": (o.get("success_fee_checkout") or {}).get("price"),
                           "retainer_url": (o.get("retainer_checkout") or {}).get("purchase_url")}
    state = {"mode": "LIVE" if whop.LIVE else "sandbox", "green": green_states(), "fee_schedule": "10/8/6/4% tiers excl. real estate, min $15k", "retainer": RETAINER, "offers": offers}
    (OUT / "08_commission.json").write_text(json.dumps(state, indent=2)); return state
