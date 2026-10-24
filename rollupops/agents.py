"""Agents that run BOTH sides of the RollupOps marketplace plus matching, reading/writing data/rollupops.duckdb.
No outreach is ever sent here: status 'intro_requested' only queues for human (Shyam) approval.
  buyer_agent  (side=buy):   refresh buyer_mandates from public buyer_signals (Exa refresh hook optional)
  seller_agent (side=sell):  maintain seller_pipeline (verification, Terac flag, jurisdiction)
  matcher      (side=match): score v_match_candidates -> matches(status=proposed)"""
import json, uuid, datetime as dt
from pathlib import Path
import duckdb
DB = Path(__file__).resolve().parent.parent / "data/rollupops.duckdb"
W = {"addon_press": 25, "partner_page": 15, "corpdev_hiring": 15, "registry": 10, "hunger": 20}
now = lambda: dt.datetime.now().replace(microsecond=0)
class Run:
    def __init__(s, con, agent, side, inp=None):
        s.con, s.agent, s.side, s.id, s.n = con, agent, side, uuid.uuid4().hex[:12], 0
        con.execute("INSERT INTO agent_runs VALUES (?,?,?,?,NULL,?,NULL)", [s.id, agent, side, now(), json.dumps(inp or {})])
    def act(s, action, eid, inp, out):
        s.n += 1; s.con.execute("INSERT INTO agent_actions VALUES (?,?,?,?,?,?,?,?,?)",
            [f"{s.id}-{s.n}", s.id, s.agent, s.side, action, eid, json.dumps(inp, default=str), json.dumps(out, default=str), now()])
    def done(s, out): s.con.execute("UPDATE agent_runs SET finished_at=?, output_json=? WHERE run_id=?", [now(), json.dumps(out), s.id])

def buyer_agent(con):
    r = Run(con, "buyer_agent", "buy")
    rows = con.execute("""SELECT p.platform_id, v.vertical, p.regions_json, list(b.type), list(b.date), list(b.url)
        FROM platforms p JOIN platform_verticals v USING(platform_id) LEFT JOIN buyer_signals b USING(platform_id) GROUP BY ALL""").fetchall()
    for pid, vert, geo, types, dates, urls in rows:
        sc = min(100, round(sum(W.get(t, 5) * (1.2 if "2026" in str(d) else 1) for t, d in zip(types, dates) if t)))
        mid = f"{pid}:{vert}"; ev = [u for u in urls if u][:5]
        con.execute("INSERT OR REPLACE INTO buyer_mandates VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                    [mid, pid, vert, geo, 1.5e6, 3e6, 3e8, sc, sc >= 25, now(), json.dumps(ev)])
        r.act("upsert_mandate", mid, {"signals": len([t for t in types if t])}, {"activity_score": sc})
    r.done({"mandates": len(rows)}); return len(rows)

def seller_agent(con):
    r = Run(con, "seller_agent", "sell")
    rows = con.execute("""SELECT l.listing_id, l.verified, list(DISTINCT j.status) FROM v_listing_states l
        LEFT JOIN jurisdictions j ON j.code=l.state GROUP BY ALL""").fetchall()
    for lid, ver, st in rows:
        js = "GREEN" if st and all(s == "GREEN" for s in st) else ("MIXED" if st and "GREEN" in st else "BLOCKED")
        vs = "verified" if ver else "auto_checks_pending"
        con.execute("INSERT OR REPLACE INTO seller_pipeline VALUES (?,?,?,?,?,?,?)",
                    [lid, None, vs, not ver, "not_started" if not ver else "passed", js, now()])
        r.act("upsert_seller", lid, {"states": st}, {"verification": vs, "jurisdiction": js, "terac_check_required": not ver})
    r.done({"sellers": len(rows)}); return len(rows)

def matcher(con, min_score=50):
    r = Run(con, "matcher", "match"); n = 0
    for mid, plat, lid, title, vert, state, gf, sf, act in con.execute("""SELECT c.mandate_id, c.platform, c.listing_id, c.title, c.vertical,
            c.seller_state, c.geo_fit, c.size_fit, m.activity_score FROM v_match_candidates c JOIN buyer_mandates m USING(mandate_id)""").fetchall():
        score = 40 + 20 * gf + 15 * sf + 0.25 * act
        if score < min_score: continue
        why = f"{plat} buys {vert}; seller in GREEN {state}; geo_fit={gf}; size_fit={sf}; buyer activity={act}"
        con.execute("""INSERT INTO matches VALUES (?,?,?,?,?,'proposed',?,?) ON CONFLICT (match_id) DO UPDATE
            SET score=excluded.score, rationale=excluded.rationale, updated_at=excluded.updated_at""",
                    [f"{mid}>{lid}", mid, lid, score, why, now(), now()]); n += 1
        r.act("propose_match", f"{mid}>{lid}", {"listing": title}, {"score": score})
    r.done({"proposed": n}); return n

def advance(con, match_id, status):  # human-approved status changes only; never sends anything
    con.execute("UPDATE matches SET status=?, updated_at=? WHERE match_id=?", [status, now(), match_id])

def run_all(con=None):
    own = con is None; con = con or duckdb.connect(str(DB))
    out = {"buyer": buyer_agent(con), "seller": seller_agent(con), "matches": matcher(con)}
    if own: con.close()
    return out
if __name__ == "__main__": print(run_all())
