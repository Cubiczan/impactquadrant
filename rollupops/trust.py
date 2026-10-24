"""Trust ladder: access scales with verification. Agents run the brokerage; humans guarantee trust."""
import re
from . import terac
FRAUD_CASES = ["fake listing", "competitor fishing", "inflated add-backs", "identity spoofing", "scraping / data harvesting"]

def seller_ladder(t):
    c = t["checks"]
    l1 = {"web_presence": c["has_website"] and c["is_company_site"], "not_pe_owned": c["not_pe_owned"], "dedupe": c["dedupe"],
          # Data sources not wired today -> explicitly 'todo', never faked as passed:
          "sos_registration_active": "todo (state SoS lookup)", "gbp_reviews_phone_consistency": "todo (Google Business Profile match)",
          "lien_lawsuit_bankruptcy": "todo (UCC/PACER search)"}
    l1_pass = all(v is True for v in l1.values() if isinstance(v, bool))
    l2 = terac.owner_verification(t) if l1_pass else {"status": "not_sent", "badge": "Flagged", "flagged": True}
    acct = t.get("whop_account_id")
    l1["whop_kyc_identity"] = whop_kyc_status(acct)["status"] if acct else "not_started (seller connected account created at listing; KYC via hosted account link)"
    l3 = {"status": "awaiting owner upload", "docs": ["3y tax returns", "TTM P&L"], "rule": "agent reconciles to teaser range; >20% add-backs -> QoE flag; never bank logins"}
    level = 3 if l3["status"] == "reconciled" else 2 if l2.get("status") == "verified" else 1 if l1_pass else 0
    return {"level": level, "badge": ["Unverified", "L1 Agent-checked", "L2 Verified by human (Terac)", "L3 Financials reconciled"][level] if not l2.get("flagged") else "Flagged",
            "L1_automated": l1, "L2_terac_call": l2, "L3_financials": l3, "publish_teaser": l1_pass}

def buyer_ladder(b, segment="pe"):
    l1 = {"email_verified": "required to view teasers (Wix member/email confirm)"}
    l2 = {"whop_payment": "required", "click_through_nda": "required", "unlocks": "blind deal memo (no owner identity)"}
    pe_pre = segment == "pe" and any(g["type"] == "addon_press" for g in b.get("signals", []))
    # No Terac on scoring/subscriptions: human screening happens only on flagged high-value events (terac.buyer_screening).
    l3 = {"status": "on_flagged_request", "rule": "human screen only if unverified buyer requests confidential deal box, retainer/$15k+ fee path, or anomaly", "flagged": False}
    l3["checks"] = (["firm exists", "recent add-ons", "person employed at firm (firm-domain email)"] if segment == "pe"
                    else ["proof of funds or SBA pre-qual letter review", "short video identity confirm"])
    l3["flag_for"] = ["data harvester", "competitor", "unfunded"]
    level = 3 if l3.get("status") == "verified" else 2  # PE platforms on our list are scored as L2-eligible once they pay + NDA
    return {"segment": segment, "level_max_today": level, "badge": "Flagged" if l3.get("flagged") else "Agent-vetted; human screen on confidential request",
            "L1": l1, "L2": l2, "L3_terac": l3, "owner_identity_released": level >= 3}

# --- Whop KYC as the identity layer (documented endpoints only) ---------------------------------
def whop_kyc_link(account_id, return_url="https://impactquadrant.info/thanks", refresh_url="https://impactquadrant.info/marketplace"):
    """POST /account_links use_case=account_onboarding -> hosted KYC URL for a seller's connected account.
    The URL carries a short-lived token: hand it to the seller, never log or commit it."""
    from . import whop
    r = whop.call("POST", "/account_links", {"account_id": account_id, "use_case": "account_onboarding", "return_url": return_url, "refresh_url": refresh_url})
    return {"has_url": bool(r.get("url")), "url": r.get("url"), "error": r.get("error")}

def whop_kyc_status(account_id):
    """GET /identity_profiles?account_id=... -> status in {not_started,pending,manual_review,approved,rejected,action_required},
    plus profile_type (individual|business), payouts_enabled. Returns only non-PII fields."""
    from . import whop
    r = whop.call("GET", f"/identity_profiles?account_id={account_id}")
    profs = r.get("data") or []
    if not profs: return {"status": "not_started", "profiles": 0}
    p = profs[0]
    return {"status": p.get("status"), "profile_type": p.get("profile_type"), "payouts_enabled": p.get("payouts_enabled"), "profiles": len(profs)}
