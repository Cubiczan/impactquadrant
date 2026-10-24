"""Multi-agent marketplace: agents run BOTH sides + matching on DuckDB. No outreach is ever sent.
  buyer_agent          side=buy   mandates from platforms/verticals; Partner A rows are AUTHORITATIVE (override inferred)
  buyer_search_agent   side=buy   Exa: PE platform add-on activity -> buyer_signals (+ cache data/exa_cache)
  seller_search_agent  side=sell  Exa: founder-owned operators per vertical x GREEN state -> operators
  seller_agent         side=sell  seller_pipeline (verification, Terac flag, GREEN jurisdiction)
  matcher              side=match scored matches (signed-buyer boost only exists in the PRIVATE build)
  whop_agent           side=whop  blind-teaser payloads -> whop_outbox (publishes only if WHOP_AUTOPUBLISH=1)"""
import json, uuid, os, re, hashlib, datetime as dt
from pathlib import Path
import duckdb
from .taxonomy import verticals, PARTNER_LANES
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/rollupops.duckdb"; CACHE = ROOT / "data/exa_cache"
W = {"addon_press": 25, "addon_log": 15, "addon_activity": 25, "partner_page": 15, "corpdev_hiring": 15, "registry": 10, "hunger": 20, "exa": 10}
now = lambda: dt.datetime.now().replace(microsecond=0)
hid = lambda *p: hashlib.sha1("|".join(str(x).lower() for x in p).encode()).hexdigest()[:10]

class Run:
    def __init__(s, con, agent, side, inp=None):
        s.con, s.agent, s.side, s.id, s.n = con, agent, side, uuid.uuid4().hex[:12], 0
        con.execute("INSERT INTO agent_runs VALUES (?,?,?,?,NULL,?,NULL)", [s.id, agent, side, now(), json.dumps(inp or {})])
    def act(s, action, eid, inp, out):
        s.n += 1; s.con.execute("INSERT INTO agent_actions VALUES (?,?,?,?,?,?,?,?,?)",
            [f"{s.id}-{s.n}", s.id, s.agent, s.side, action, eid, json.dumps(inp, default=str)[:2000], json.dumps(out, default=str)[:2000], now()])
    def done(s, out): s.con.execute("UPDATE agent_runs SET finished_at=?, output_json=? WHERE run_id=?", [now(), json.dumps(out), s.id]); return out

# ---------------- buy side ----------------
def buyer_agent(con):
    r = Run(con, "buyer_agent", "buy")
    rows = con.execute("""SELECT p.platform_id, v.vertical, coalesce(p.regions_json,'["US"]'), list(b.type), list(b.date), list(b.url)
        FROM platforms p JOIN platform_verticals v USING(platform_id) LEFT JOIN buyer_signals b USING(platform_id) GROUP BY ALL""").fetchall()
    for pid, vert, geo, types, dates, urls in rows:
        sc = min(100, round(sum(W.get(t, 5) * (1.2 if "2026" in str(d) or "2025" in str(d) else 1) for t, d in zip(types, dates) if t)))
        mid = f"{pid}:{vert}"
        con.execute("INSERT OR REPLACE INTO buyer_mandates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [mid, pid, vert, geo, 1.5e6, 3e6, 3e8, "inferred from public add-on signals", False, sc, sc >= 25, now(), json.dumps([u for u in urls if u][:5])])
        r.act("upsert_mandate", mid, {"signals": len([t for t in types if t])}, {"activity_score": sc})
    # Partner A workbook = authoritative areas of match (overrides keyword-inferred mandates for those platforms)
    alp = con.execute("""SELECT p.platform_id, p.name, p.appetite, p.status FROM platforms p JOIN sponsors s USING(sponsor_id)
                         WHERE s.name='Partner A' AND p.name IN ?""", [list(PARTNER_LANES)]).fetchall()
    for pid, name, appetite, status in alp:
        con.execute("DELETE FROM buyer_mandates WHERE platform_id=?", [pid]); vert = PARTNER_LANES[name]
        crit = appetite or "Founder/family-owned, $2M+ EBITDA, sale-intent, non-broker"
        con.execute("INSERT INTO buyer_mandates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    [f"{pid}:{vert}", pid, vert, '["US"]', 2e6, None, None, crit, True, 90, True, now(), json.dumps({"source": "Partner A workbook Master Platform List", "status": status})])
        r.act("authoritative_mandate", f"{pid}:{vert}", {"platform": name}, {"vertical": vert, "ebitda_min": 2e6, "criteria": crit})
    return r.done({"mandates": len(rows), "partner_authoritative": len(alp)})

def _exa(q, n):
    k = os.environ.get("EXA_API_KEY")
    if not k: return []
    import urllib.request
    req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps({"query": q, "numResults": n, "type": "auto", "contents": {"summary": True}}).encode(),
                                 headers={"x-api-key": k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=45) as resp: return json.loads(resp.read()).get("results", [])
    except Exception as e: return [{"error": str(e)[:200]}]

def exa_fetch(tasks, n=5):
    """Network step, run in parallel by the orchestrator. Caches results so builds stay idempotent."""
    from concurrent.futures import ThreadPoolExecutor
    CACHE.mkdir(exist_ok=True)
    def one(t):
        res = _exa(t["query"], n); from .db import scrub
        out = dict(t, results=[{k: scrub(x.get(k)) for k in ("title", "url", "publishedDate", "summary", "error")} for x in res], fetched=str(now()))
        (CACHE / f'{t["agent"].replace(":", "__")}.json').write_text(json.dumps(out, indent=1)); return out
    with ThreadPoolExecutor(8) as ex: return list(ex.map(one, tasks))

def buyer_search_agent(con, cached):
    r = Run(con, cached["agent"], "buy", {"query": cached["query"]}); names = con.execute("SELECT platform_id, name FROM platforms").fetchall(); n = 0
    for x in cached["results"]:
        if x.get("error") or not x.get("url"): continue
        txt = f'{x.get("title")} {x.get("summary")}'.lower()
        pid = next((p for p, nm in names if re.split(r"\s*[(/]", nm)[0].lower() in txt and len(nm) > 4), None)
        if not pid:  # new lead platform from public web
            pid = hid(x["title"]); con.execute("INSERT OR IGNORE INTO sponsors (sponsor_id,name,src_file) VALUES (?,?,?)", [hid("see source"), "see source", "exa"])
            con.execute("INSERT OR IGNORE INTO platforms (platform_id,name,sponsor_id,segment,regions_json,src_file) VALUES (?,?,?,?,?,?)",
                        [pid, (x["title"] or "")[:90], hid("see source"), cached["vertical"], '["US"]', f'exa:{cached["agent"]}'])
            con.execute("INSERT OR IGNORE INTO platform_verticals VALUES (?,?,?,?)", [pid, cached["vertical"], cached["vertical"], "exa"])
        con.execute("INSERT OR IGNORE INTO buyer_signals VALUES (?,?,?,?,?,?,?)", [hid(pid, x["url"]), pid, "exa", (x.get("publishedDate") or "")[:10], (x.get("summary") or "")[:300], x["url"], f'exa:{cached["agent"]}'])
        r.act("buyer_signal", pid, {"url": x["url"]}, {"title": x.get("title")}); n += 1
    return r.done({"signals": n})

# ---------------- sell side ----------------
def seller_search_agent(con, cached):
    r = Run(con, cached["agent"], "sell", {"query": cached["query"]}); n = 0
    for x in cached["results"]:
        if x.get("error") or not x.get("url"): continue
        name = re.split(r"\s[|\-–:]\s", x.get("title") or "")[0][:80]
        oid = hid(name, cached["state"])
        con.execute("""INSERT OR IGNORE INTO operators (operator_id,name,trade,vertical,state,country,website,independent,notes,src_file)
                       VALUES (?,?,?,?,?,?,?,?,?,?)""", [oid, name, cached["vertical"], cached["vertical"], cached["state"], "US", x["url"], True, (x.get("summary") or "")[:300], f'exa:{cached["agent"]}'])
        r.act("operator_found", oid, {"url": x["url"]}, {"name": name}); n += 1
    return r.done({"operators": n})

def seller_agent(con):
    r = Run(con, "seller_agent", "sell")
    green = {c for (c,) in con.execute("SELECT code FROM jurisdictions WHERE status='GREEN'").fetchall()}
    rows = [("listing", l, t, v, st, ver, "out/03_listings.json") for l, t, v, st, ver in
            con.execute("SELECT listing_id, title, vertical, state, verified FROM v_listing_states").fetchall()]
    rows += [("operator", o, n, v, st, False, src) for o, n, v, st, src in
             con.execute("SELECT operator_id, name, vertical, state, src_file FROM operators WHERE independent AND state IS NOT NULL").fetchall()]
    for kind, sid, name, vert, st, ver, src in rows:
        js = "GREEN" if st in green else "BLOCKED"
        con.execute("INSERT OR REPLACE INTO seller_pipeline VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [sid if kind == "operator" else f"{sid}:{st}", kind, name, vert, st, "verified" if ver else "auto_checks_pending", not ver,
                     "passed" if ver else "not_started", js, src, now()])
        r.act("upsert_seller", sid, {"state": st}, {"jurisdiction": js})
    return r.done({"sellers": len(rows), "green": sum(1 for x in rows if x[4] in green)})

# ---------------- match ----------------
def matcher(con, min_score=55, per_seller=3):
    r = Run(con, "matcher", "match"); con.execute("DELETE FROM matches WHERE status='proposed'"); n = 0
    cands = con.execute("SELECT mandate_id, authoritative, platform, sponsor, agreement_status, seller_id, seller, vertical, seller_state, geo_fit, size_fit, activity_score FROM v_match_candidates").fetchall()
    best = {}
    for mid, auth, plat, spon, agr, sid, seller, vert, st, gf, sf, act in cands:
        score = 35 + 15 * gf + 10 * sf + 0.25 * act + (10 if auth else 0) + (15 if agr == "signed" else 0)
        why = [f"{plat} ({spon}) buys {vert}", f"seller in GREEN {st}"] + (["authoritative Partner A criteria"] if auth else []) + (["signed buyer agreement"] if agr == "signed" else [])
        best.setdefault(sid, []).append((score, mid, "; ".join(why)))
    for sid, lst in best.items():
        for score, mid, why in sorted(lst, reverse=True)[:per_seller]:
            if score < min_score: continue
            con.execute("INSERT OR IGNORE INTO matches VALUES (?,?,?,?,?,'proposed',?,?)", [f"{mid}>{sid}", mid, sid, score, why, now(), now()]); n += 1
            r.act("propose_match", f"{mid}>{sid}", {}, {"score": score})
    return r.done({"candidates": len(cands), "proposed": n})

def advance(con, match_id, status):  # human-approved status changes only; never sends anything
    con.execute("UPDATE matches SET status=?, updated_at=? WHERE match_id=?", [status, now(), match_id])

# ---------------- Whop ----------------
def whop_agent(con, top=5):
    """Blind teaser per top match -> whop_outbox. Seller identity never in payload. Teaser access is gated by a Whop
    membership (NDA + proof of funds) — the membership unlocks the data room, not the seller name in public."""
    r = Run(con, "whop_agent", "whop"); live = os.environ.get("WHOP_AUTOPUBLISH") == "1"; out = []
    rows = con.execute("""SELECT m.match_id, sp.vertical, sp.state, m.score FROM matches m JOIN seller_pipeline sp USING(seller_id)
                          WHERE sp.kind='listing' OR m.score>=70 ORDER BY m.score DESC LIMIT ?""", [top]).fetchall()
    for mid, vert, st, score in rows:
        title = f"Blind teaser: {vert.replace('_', ' ')} business, {st}"
        payload = {"product": {"title": title, "description": "Founder-owned, off-market. NDA + proof of funds required; Terac human check on both sides.",
                               "plan_options": {"plan_type": "one_time", "base_currency": "usd", "initial_price": 149}, "metadata": {"match_id": mid, "gate": "nda+pof"}},
                   "checkout": {"mode": "payment", "metadata": {"match_id": mid, "segment": vert}}}
        resp = None
        if live:
            from . import whop
            resp = whop.create_product(title, payload["product"]["description"], "one_time", 149, metadata=payload["product"]["metadata"])
        con.execute("INSERT OR REPLACE INTO whop_outbox VALUES (?,?,?,?,?,?,?)", [hid(mid), mid, "blind_teaser", json.dumps(payload), live, json.dumps(resp) if resp else None, now()])
        r.act("teaser_payload", mid, {"score": score}, {"published": live}); out.append(title)
    return r.done({"payloads": len(out), "published": live})

def run_all(con=None):
    own = con is None; con = con or duckdb.connect(str(DB))
    for f in sorted(CACHE.glob("*.json")) if CACHE.exists() else []:   # replay cached Exa results -> idempotent builds
        c = json.loads(f.read_text()); (buyer_search_agent if c["side"] == "buy" else seller_search_agent)(con, c)
    out = {"buyer": buyer_agent(con), "seller": seller_agent(con), "match": matcher(con), "whop": whop_agent(con)}
    if own: con.close()
    return out
if __name__ == "__main__": print(json.dumps(run_all(), indent=1, default=str))
