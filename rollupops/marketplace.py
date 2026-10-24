"""Whop for Platforms: subscription + per-target unlock (direct charge on seller connected account, 20% app fee),
verifier transfer (queued), referral revenue line. SANDBOX unless Needs-Shyam live switch."""
import os, json
from pathlib import Path
from . import whop
OUT = Path(__file__).resolve().parent.parent / "out"
UNLOCK_PRICE = float(os.environ.get("UNLOCK_PRICE", 250)); FEE_PCT = 0.20; VERIFIER_PAYOUT = 25
SELLER_ACCT = os.environ.get("WHOP_SELLER_ACCOUNT", "biz_GUUF0UYxQLOE5S")
SEARCHER = {"deal_drop": {"product_id": "prod_Xrrw2ZWUd72nW", "plan_id": "plan_PobV6T3Hak8FP", "purchase_url": "https://sandbox.whop.com/checkout/plan_PobV6T3Hak8FP", "price": "$49/mo"},
            "teardown": {"product_id": "prod_8WJ9zRFEbGhDP", "plan_id": "plan_K5LRRtkdPMull", "purchase_url": "https://sandbox.whop.com/checkout/plan_K5LRRtkdPMull", "price": "$149 one-time"}}
def searcher_price(listing):  # scaled to deal size (low end of value range)
    lo = listing.get("_val_lo", 0)
    return 19.0 if lo < 1e6 else 49.0 if lo < 3e6 else 99.0
SUB = {"product_id": "prod_ZTAhjw5WPU11F", "plan_id": "plan_G3u2jR3bL0Mva", "purchase_url": "https://sandbox.whop.com/checkout/plan_G3u2jR3bL0Mva", "price": "$499/mo"}

def seller_account(email, title, external_id):
    """Idempotent on email+external_id. Onboard via our Whop partner referral first (see README)."""
    return whop.call("POST", "/accounts", {"parent_account_id": whop.BIZ, "email": email, "title": title, "metadata": {"external_id": external_id}})

def unlock_checkout(listing, account_id=SELLER_ACCT, price=None, segment="pe"):
    price = price or UNLOCK_PRICE; fee = round(price * FEE_PCT, 2)
    r = whop.call("POST", "/checkout_configurations", {"mode": "payment",
        "plan": {"account_id": account_id, "currency": "usd", "plan_type": "one_time", "initial_price": price,
                 "application_fee_amount": fee, "title": f"{'PE intro' if segment=='pe' else 'Deal'} unlock {listing['targetId']}"},
        "metadata": {"target_id": listing["targetId"], "app": "rollupops", "segment": segment},
        "redirect_url": "https://impactquadrant.info/thanks"})
    return {"checkout_id": r.get("id"), "purchase_url": r.get("purchase_url"), "plan_id": (r.get("plan") or {}).get("id"),
            "fee": fee, "price": price, "segment": segment, "error": r.get("error") and r.get("body")}

def queue_verifier_transfer(target_id, verifier_account):
    # Sandbox: payouts/withdrawals unsupported and platform balance is $0 -> recorded as queued ledger entry.
    return {"target_id": target_id, "amount": VERIFIER_PAYOUT, "origin_id": whop.BIZ, "destination_id": verifier_account,
            "status": "queued (sandbox: transfers need funded, KYC'd origin)", "live": whop.LIVE}

def list_on_whop(listings):
    ledger = []
    for l in listings:
        c = unlock_checkout(l); l["checkoutUrl"] = c["purchase_url"]
        c2 = unlock_checkout(l, price=searcher_price(l), segment="individual"); l["checkoutUrlIndividual"] = c2["purchase_url"]
        l["individualUnlockPrice"] = c2["price"]; l["whop"] = {"pe": c, "individual": c2}
        for x in (c, c2): ledger.append({"target": l["targetId"], "segment": x["segment"], "gmv_if_sold": x["price"], "platform_fee": x["fee"], "seller_net": x["price"] - x["fee"]})
    state = {"mode": "LIVE" if whop.LIVE else "sandbox", "business": whop.BIZ, "subscription": SUB, "individual_products": SEARCHER, "seller_account": SELLER_ACCT,
             "unlocks": ledger, "referral": {"program": "Whop Partners: 30% of Whop's eligible gross profit on referred businesses",
             "referred_businesses": [SELLER_ACCT], "pending": "tracked in whop.com/partners (not exposed by API)", "completed": 0},
             "go_live_switch": "Needs Shyam: set WHOP_LIVE=1 + NEEDS_SHYAM_APPROVED=1 with a production key"}
    (OUT / "06_whop.json").write_text(json.dumps(state, indent=2)); return state
