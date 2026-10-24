"""RollupOps agent loop: Business brokerage, reimagined and automated.
Stages write JSON to out/. Run: python -m rollupops.pipeline [--whop]"""
import csv, json, os, re, sys, hashlib, datetime as dt
from pathlib import Path
from . import exa, terac, trust, jurisdiction
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"; OUT.mkdir(exist_ok=True)
REG = Path(os.environ.get("PE_REGISTRY", "/workspace/pipeline/outreach/impact-quadrant/pe-buyer-registry/registry.csv"))
NOW = dt.date(2026, 10, 24)
MFG_DIST = ("machin", "manufactur", "distribut", "fabricat", "stamping", "automation", "bearing", "fluid", "mro")
EXCLUDE = ("mining", "mine ", "quarry", "silica")
def w(name, obj): (OUT / f"{name}.json").write_text(json.dumps(obj, indent=2)); return obj
def tid(name): return "t_" + hashlib.sha1(name.encode()).hexdigest()[:8]

# 1. buyers ---------------------------------------------------------------
def discover_buyers():
    buyers = json.loads((ROOT / "data/buyer_signals.json").read_text())
    if REG.exists():
        for r in csv.DictReader(open(REG)):
            t = (r["trade"] + " " + r["platform"]).lower()
            if any(k in t for k in MFG_DIST) and not any(k in t for k in EXCLUDE):
                if r["platform"] not in {b["platform"] for b in buyers}:
                    buyers.append({"platform": r["platform"], "sponsor": r["pe_sponsor"], "sector": r["trade"],
                                   "regions": [r["state"]], "signals": [{"type": "registry", "date": r["acquired_date"], "note": r["portfolio_company"], "url": r["source_url"]}]})
    buyers += exa.discover_buyers()  # live Exa when EXA_API_KEY set; [] otherwise
    return buyers

# 2. automated buyer-activity score (public signals; no human) -------------
SIG_W = {"addon_press": 25, "partner_page": 15, "corpdev_hiring": 15, "registry": 10}
def score_buyer(b):
    s = 0
    for g in b["signals"]:
        base = SIG_W.get(g["type"], 5)
        if "2026" in str(g.get("date", "")): base *= 1.2
        s += base
    b["activity_score"] = min(100, round(s)); b["active"] = b["activity_score"] >= 25
    # qualification checklist (proof of funds before any unlock)
    b["qualification"] = {"buy_box_fit": None, "competitor_conflict_check": "pending",
        "proof_of_funds": "PE entity with recent closed add-ons" if any(g["type"] == "addon_press" for g in b["signals"]) else "request >=20-25% liquid / fund docs",
        "unlock_allowed": any(g["type"] == "addon_press" for g in b["signals"])}
    return b

# 3. buy-box inference (rules) --------------------------------------------
def buy_box(b):
    sec = b["sector"].lower()
    trade = "precision machining" if "machin" in sec else "industrial distribution" if ("distribut" in sec or "bearing" in sec) else sec
    b["buy_box"] = {"trade": trade, "regions": ["Southeast US"] if b["regions"] == ["US"] else b["regions"],
                    "revenue_band": "$3M-$40M", "ebitda_band": "$0.5M-$8M", "deal_type": "add-on (majority, founder rollover 15-25%)",
                    "evidence": [g["url"] for g in b["signals"]]}
    return b

# 4. sourcing + automated data checks -------------------------------------
PE_HINTS = ("compass precision", "portfolio company", "a division of", "acquired by")
def source_targets():
    raw = json.loads((ROOT / "data/targets_raw.json").read_text()) + exa.source_targets()
    seen, out = set(), []
    for t in raw:
        dom = re.sub(r"https?://(www\.)?", "", t.get("website", "")).split("/")[0]
        key = dom if t.get("src") == "exa" or dom in seen else re.sub(r"\W", "", t["name"].lower())
        if dom in seen: key = dom
        checks = {"dedupe": key not in seen, "has_website": bool(t.get("website", "").startswith("http")),
                  "is_company_site": not re.search(r"linkedin|\.pdf$|nist\.gov|ncsu\.edu|inddist|magazine|ptda|bernardandcompany|privsource|mapquest", t.get("website", "")),
                  "not_pe_owned": not any(h in t["notes"].lower() for h in PE_HINTS),
                  "in_focus": any(k in t["trade"] for k in MFG_DIST) and not any(k in t["notes"].lower() for k in EXCLUDE)}
        seen.add(key); seen.add(dom); t["id"] = tid(t["name"]); t["checks"] = checks
        t["status"] = "eligible" if all(checks.values()) else "dropped:" + ",".join(k for k, v in checks.items() if not v)
        out.append(t)
    return out

# 5. value-driver scoring + valuation estimate ----------------------------
def _years(n):
    m = re.search(r"(?:since|est\.?|founded|in)\s*(19\d\d|20[01]\d)", n.lower())
    return NOW.year - int(m.group(1)) if m else None
def value_drivers(t):
    n = t["notes"].lower()
    d = {"certifications_moat": 1 if re.search(r"as9100|iso 13485|itar|cage", n) else 0,
         "multi_location_or_capacity": 1 if re.search(r"location|branch|sq ft|50\+|machines", n) else 0,
         "recurring_mro_revenue": 1 if re.search(r"mro|service|stock", n) else 0,
         "succession_signal": 1 if re.search(r"family|generation|since 19[4-8]", n) else 0,
         "customer_concentration_risk": -1 if "prototype" in n else 0,
         "owner_dependence_risk": -1 if "family" in n and "generation" not in n else 0}
    return d
def estimate_financials(t):
    n = t["notes"].lower(); big = bool(re.search(r"\d{2,}\+? locations|12\+|15 locations|92,000|50\+ cnc", n))
    if big: rev = (15e6, 40e6); earn = ("EBITDA", rev[0]*.12, rev[1]*.12)
    else:   rev = (3e6, 12e6);  earn = ("SDE", rev[0]*.18, rev[1]*.18)
    kind, lo, hi = earn
    if kind == "SDE" and hi >= 2e6: kind = "EBITDA"; lo, hi = lo*.7, hi*.7  # never mix SDE w/ EBITDA multiple
    mult = (2.0, 3.1) if kind == "SDE" else (4.0, 5.8)
    return {"basis": kind, "revenue_band": rev, "earnings_band": (round(lo), round(hi)), "multiple_band": mult,
            "valuation_band": (round(lo*mult[0], -4), round(hi*mult[1], -4)),
            "reference": "PE manufacturing avg 7.1x EBITDA (GF Data 2026 mid-year)", "label": "estimate"}
def score_target(t, buyers):
    d = value_drivers(t); yrs = _years(t["notes"])
    fits = [b for b in buyers if b["active"] and b["buy_box"]["trade"] == t["trade"]]
    t["value_drivers"] = d; t["years_in_business"] = yrs
    t["valuation"] = estimate_financials(t)
    t["score"] = min(100, 40 + 10*sum(d.values()) + (10 if yrs and yrs >= 25 else 0) + min(20, 5*len(fits)))
    t["matched_buyers"] = [b["platform"] for b in sorted(fits, key=lambda b: -b["activity_score"])][:50]
    t["qoe_flag"] = False
    return t

# 6. blind teaser + PII lint ----------------------------------------------
REGION = {"NC": "Carolinas", "SC": "Carolinas", "GA": "Southeast", "AL": "Southeast", "FL": "Florida", "VA": "Mid-Atlantic"}
def fmt(x): return f"${x/1e6:.1f}M"
def teaser(t):
    v = t["valuation"]; d = t["value_drivers"]
    strengths = [s for s, k in [("Aerospace/medical certifications", "certifications_moat"), ("Multi-site / capacity", "multi_location_or_capacity"),
                 ("Recurring MRO/service revenue", "recurring_mro_revenue"), ("Succession-ready ownership", "succession_signal")] if d[k] > 0][:3]
    yrs = t["years_in_business"]
    tz = {"targetId": t["id"], "title": f"{t['trade'].title()} business, {REGION.get(t['state'], 'US')}",
          "trade": t["trade"], "region": REGION.get(t["state"], "US"),
          "revenueBand": f"{fmt(v['revenue_band'][0])}-{fmt(v['revenue_band'][1])} (est.)",
          "earningsBand": f"{v['basis']} {fmt(v['earnings_band'][0])}-{fmt(v['earnings_band'][1])} (est.)",
          "yearsInBusiness": f"{(yrs//5)*5}+ yrs" if yrs else "Established",
          "strengths": strengths, "dealType": "Add-on / majority recap",
          "valuationBand": f"{fmt(v['valuation_band'][0])}-{fmt(v['valuation_band'][1])} (estimate, {v['basis']} basis)",
          "score": t["score"], "verified": False, "status": "listed", "_val_lo": v["valuation_band"][0],
          "buyerSegments": "PE platforms + individual buyers",
          "equityHint": ("Estimate: deal size likely above SBA 7(a) loan limits; PE / conventional financing" if v['valuation_band'][0] > 5.5e6 else None) or f"Estimate: ~10% down ≈ {fmt(v['valuation_band'][0]*0.10)}-{fmt(v['valuation_band'][1]*0.10)} with SBA-style financing (estimate only; confirm with your lender)",
          "qualificationGate": "NDA + proof of funds (PE: fund docs / closed add-ons; individual: liquid funds or lender pre-qual letter)"}
    banned = [t["name"].lower(), t.get("town", "").lower(), re.sub(r"https?://(www\.)?", "", t.get("website", "")).split("/")[0]]
    blob = json.dumps(tz).lower()
    tz["pii_lint"] = "pass" if not any(b and b in blob for b in banned) and not re.search(r"\(\d{3}\)|@|\.com", blob) else "FAIL"
    return tz

# 7. outreach drafts (never sent) -----------------------------------------
FOOTER = "\n--\nImpact Quadrant · impactquadrant.info · Reply STOP to opt out. [CAN-SPAM postal address required before any real send]"
def drafts(t, tz):
    seller = {"to_role": "owner", "target": t["name"], "subject": "A free, confidential valuation for your business",
      "body": f"Hi,\n\nWe run Impact Quadrant, an automated business brokerage. We prepare free, confidential valuation estimates for established {t['trade']} companies in the {tz['region']}. "
              "No obligation and nothing to sign. If you'd like yours, reply and we'll set up a 15-minute call." + FOOTER}
    buyer = [{"to_role": "buyer", "platform": b, "subject": f"Proprietary {t['trade']} add-on in the {tz['region']} matching your buy-box",
      "body": f"Hi,\n\nWe have a proprietary {t['trade']} lead in the {tz['region']} ({tz['revenueBand']}, {tz['earningsBand']}) matching your add-on criteria, and the owner is open to a call. "
              "Blind teaser and NDA: https://impactquadrant.info/marketplace" + FOOTER} for b in t["matched_buyers"][:3]]
    lint = lambda m: all([("guarantee" not in m["body"].lower()), ("we want to buy" not in m["body"].lower()), ("STOP" in m["body"])])
    for m in [seller] + buyer: m["lint"] = "pass" if lint(m) else "FAIL"; m["status"] = "draft (Needs Shyam to send)"
    return {"seller": seller, "buyers": buyer}

def free_teardown(tz):
    """Free weekly AI teardown of ONE anonymized listing (lead magnet; email signup on Wix, no sends)."""
    flags = []
    if "certifications" not in " ".join(tz["strengths"]).lower(): flags.append("No certification moat found: check customer stickiness.")
    flags += ["Ask for 3 years of tax returns vs. P&L: add-backs over 20% of earnings trigger a QoE review.",
              "Customer concentration: request top-10 customer share before LOI.",
              "Owner dependence: who quotes jobs and holds key accounts today?"]
    return {"listing": tz["title"], "value_range": tz["valuationBand"], "down_payment": tz["equityHint"], "red_flags": flags,
            "verdict": "Worth a call if concentration < 30% and add-backs are documented.", "cta": "Want this on a deal you found? Deal Teardown, $149.",
            "tone": "No pressure. No $10k course. Just the deals."}

def run(do_whop=False, top=6):
    buyers = [buy_box(score_buyer(b)) for b in discover_buyers()]
    for b in buyers:
        b["trust"] = trust.buyer_ladder(b); b["terac"] = b["trust"]["L3_terac"]; b["trustBadge"] = b["trust"]["badge"]
        b["qualification"]["full_memo_release"] = "after Terac buyer verification" if terac.ENABLED else "blocked until buyer verified"
    w("01_buyers", buyers)
    targets = source_targets()
    elig = [score_target(t, buyers) for t in targets if t["status"] == "eligible"]
    w("02_targets", targets)
    ranked = sorted(elig, key=lambda t: -t["score"])[:top]
    listings, outreach = [], []
    for t in ranked:
        tr = trust.seller_ladder(t)
        if not tr["publish_teaser"]: continue
        tz = teaser(t); tz["trust"] = tr; tz["country"] = t.get("country", "US"); tz["stateProvince"] = t.get("state", "")
        tz["jurisdiction"] = jurisdiction.gate((tz["country"], t.get("state")), ("US", None))

        tz["terac"] = tr["L2_terac_call"]
        tz["trustBadge"] = tr["badge"]; tz["trustLevel"] = tr["level"]; tz["verified"] = tr["level"] >= 2
        tz["stale_after"] = (NOW + dt.timedelta(days=10)).isoformat()
        listings.append(tz); outreach.append(drafts(t, tz))
    if do_whop:
        from . import marketplace; marketplace.list_on_whop(listings)
    w("03_listings", listings); w("04_outreach_drafts", outreach)
    needs = [{"item": f"Send {1+len(o['buyers'])} outreach drafts for {o['seller']['target']}", "why": "real send"} for o in outreach]
    needs += [{"item": f"Flagged by trust layer: {x.get('platform') or x.get('title')}", "why": "fraud/trust flag"} for x in buyers + listings if x.get("terac", {}).get("flagged")]
    needs += [{"item": "Flip Whop to live (WHOP_LIVE=1) for first real sale", "why": "non-sandbox charge"},
              {"item": "Enable Terac trust layer (TERAC_ENABLED=1): seller + buyer verification, cap 5 each, once researcher org exists", "why": "Terac spend"}]
    w("05_needs_shyam", needs)
    if listings: w("07_free_teardown", free_teardown(listings[0]))
    summary = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "buyers": len(buyers), "active_buyers": sum(b["active"] for b in buyers),
               "targets_sourced": len(targets), "eligible": len(elig), "listed": len(listings), "drafts": sum(1+len(o["buyers"]) for o in outreach),
               "terac_enabled": terac.ENABLED}
    w("00_summary", summary); print(json.dumps(summary, indent=1)); return summary

if __name__ == "__main__": run("--whop" in sys.argv)
