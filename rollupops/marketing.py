"""Marketing agent: drafts social posts for live Whop products. NEVER publishes.
Status flow: draft -> approved (user approves final text) -> posted.
Posting is a stub gated by MARKETING_AUTOPUBLISH (default 0); actual posting is done
manually via the signed-in browser only after explicit user approval."""
import json, os, re, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out/marketing"
GREEN = "24 US states plus Brazil, Switzerland, Germany, Spain, Japan and Mexico"
BANNED = re.compile(r"signed (partner|agreement)|\bnda\b", re.I)
PLATFORMS = {"linkedin": 1300, "facebook": 600, "instagram": 2000, "tiktok": 2200}
TAGS = {"linkedin": ["#MergersAndAcquisitions", "#SmallBusiness", "#Manufacturing", "#Distribution", "#ExitPlanning"],
        "facebook": ["#SmallBusiness", "#BusinessOwner", "#SellYourBusiness"],
        "instagram": ["#smallbusiness", "#businessowner", "#manufacturing", "#distribution", "#exitplanning", "#mergersandacquisitions", "#businessvaluation", "#entrepreneur"],
        "tiktok": ["#smallbusiness", "#businessowner", "#exitplanning", "#manufacturing", "#businesstok"]}
HOOK = {"pe_deal_flow": "Private equity teams: get vetted lower-middle-market manufacturing and distribution deal flow every month.",
        "deal_drop": "A curated drop of owner-operated manufacturing and distribution businesses open to a sale.",
        "teardown": "Thinking about selling? Get a plain-English teardown of what buyers will see in your business.",
        "sell_side_retainer": "Ready to sell your manufacturing or distribution business? Start a sell-side process with a retainer credited at close.",
        "valuation": "What is your business actually worth to a buyer? Get a defensible valuation report.",
        "readiness": "Most owners aren't ready for diligence. A Sale-Readiness Audit shows exactly what to fix first.",
        "buyer_landscape": "Who would buy your company? See the buyer landscape for your niche before you go to market.",
        "teaser_cim": "Go to market like a pro: a confidential teaser plus a full CIM, prepared for you.",
        "qoe_lite": "Get ahead of buyer diligence with a Quality-of-Earnings Lite review of your numbers."}
def catalog():
    return json.loads((ROOT / "data/whop_live_catalog.json").read_text())["products"]
def render(key, p, platform):
    title = p.get("title") or key.replace("_", " ").title()
    body = (f"{HOOK.get(key, title)}\n\n{title} — {p['price']}.\nAvailable in {GREEN}. "
            f"Not legal or financial advice.\n\n")
    link = p["purchase_url"]; tags = " ".join(TAGS[platform])
    if platform == "tiktok":
        text = f"{HOOK.get(key, title)} {title}, {p['price']}. Link in bio. Available in {GREEN}. Not legal or financial advice. {tags}"
    elif platform == "instagram": text = body + "Link in bio / checkout: " + link + "\n\n" + tags
    elif platform == "facebook": text = body + link + "\n\n" + tags
    else: text = body + f"Details and checkout: {link}\n\n{tags}"
    text = text[:PLATFORMS[platform]]
    assert not BANNED.search(text), "confidential term in draft"
    d = {"product": key, "platform": platform, "text": text, "checkout": link, "status": "draft", "chars": len(text)}
    if platform == "instagram":
        d["image_prompt"] = (f"Clean editorial photo of a modern small manufacturing/distribution floor, warm light, "
                             f"bold overlay text '{title}', navy and gold palette, square 1080x1080, no logos, no people's faces")
    if platform == "tiktok":
        d["script"] = {"hook (0-3s)": re.split(r"(?<=[.?!]) ", HOOK.get(key, title))[0],
                       "beat_1": f"Most owners guess. Buyers don't. {title} gives you the buyer's view.",
                       "beat_2": "Built for small and mid-size manufacturing and distribution businesses.",
                       "beat_3": f"Available in {GREEN}.",
                       "cta": f"{p['price']}. Tap the link in bio to check out.",
                       "on_screen_text": title, "length_s": 30}
    return d
def week(start=None):
    t = dt.date.today(); start = start or (t + dt.timedelta(days=(7 - t.weekday()) % 7 or 7) if t.weekday() >= 5 else t)
    cat = catalog(); keys = list(cat); OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / start.isoformat(); folder.mkdir(exist_ok=True); cal = []
    for i, k in enumerate(keys):
        day = start + dt.timedelta(days=i % 7)
        for pf in PLATFORMS:
            f = folder / f"{day.isoformat()}_{pf}_{k}.json"
            if f.exists(): d = json.loads(f.read_text())  # keep approvals
            else: d = render(k, cat[k], pf); d["scheduled"] = day.isoformat(); f.write_text(json.dumps(d, indent=1))
            cal.append({"date": day.isoformat(), "platform": pf, "product": k, "status": d["status"], "file": f.name})
    (folder / "calendar.json").write_text(json.dumps(cal, indent=1))
    return folder, cal
def approve(path):
    d = json.loads(Path(path).read_text()); d["status"] = "approved"; d["approved_at"] = dt.datetime.now().isoformat()
    Path(path).write_text(json.dumps(d, indent=1)); return d
def post(path):
    d = json.loads(Path(path).read_text())
    if d["status"] != "approved": raise PermissionError("not approved by user")
    if os.environ.get("MARKETING_AUTOPUBLISH", "0") != "1":
        return {"posted": False, "reason": "MARKETING_AUTOPUBLISH=0; post manually via signed-in browser after approval"}
    raise NotImplementedError("autopublish stub: no platform API wired")
def standup():
    _, cal = week(); s = {}
    for c in cal: s[c["status"]] = s.get(c["status"], 0) + 1
    return {"marketing_drafts": len(cal), "by_status": s, "autopublish": os.environ.get("MARKETING_AUTOPUBLISH", "0")}
if __name__ == "__main__":
    f, cal = week(); print(f, len(cal)); print(json.dumps(standup()))
