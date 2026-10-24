"""Order fulfillment for Precision Sale Process services. NOT legal/tax/financial advice. NEVER auto-sends.
States: paid -> intake_sent -> intake_received -> drafting -> awaiting_review -> delivered
- on_payment(evt): Whop payment webhook/sync -> order row + intake (questionnaire + doc list) + /intake?order=... link
- receive_intake(order, answers): seller answers -> analysis agents (DuckDB comps/buyers + Exa) -> markdown + PDF in outbox
- approve(order, secret): human approval (FULFILL_APPROVE_SECRET) -> delivered via Whop link (sandbox: recorded, not sent)
Orders live in data/orders.duckdb (separate from the rebuildable marketplace DB, gitignored)."""
import json, os, hmac, hashlib, datetime as dt
from pathlib import Path
import duckdb
from . import exa
ROOT = Path(__file__).resolve().parent.parent
ODB = Path(os.environ.get("ORDERS_DB", ROOT / "data/orders.duckdb"))
MDB = ROOT / "data/rollupops.duckdb"
OUTBOX = ROOT / "out/fulfillment"
DASH = os.environ.get("DASHBOARD_URL", "https://dashboard-six-fawn-83.vercel.app")
CAT = json.loads((ROOT / "data/whop_live_catalog.json").read_text())["products"]
PLAN2SKU = {v["plan_id"]: k for k, v in CAT.items()}
DISCLAIMER = "Prepared by ImpactQuadrant agents and reviewed by a human before delivery. Estimates only; not legal, tax, accounting or financial advice."
BASE_Q = [("company", "Business name (kept confidential)"), ("vertical", "Industry / vertical"), ("state", "State or country of the business"),
          ("revenue", "Last full-year revenue (USD)"), ("earnings", "Last full-year EBITDA or owner's earnings (SDE)")]
INTAKE = {
 "valuation": {"q": BASE_Q + [("employees", "Employees"), ("top_customer_pct", "Largest customer % of revenue")],
               "docs": ["3 years P&L", "3 years business tax returns", "Add-back schedule"]},
 "readiness": {"q": BASE_Q + [("owner_hours", "Owner hours per week in the business"), ("timeline", "Target sale timeline")],
               "docs": ["3 years P&L", "3 years tax returns", "Add-back schedule", "Balance sheet", "Org chart", "Top-10 customer list (share %)"]},
 "buyer_landscape": {"q": [("vertical", "Industry / vertical"), ("state", "Region or state"), ("revenue", "Approx. revenue band")], "docs": []},
 "teaser_cim": {"q": BASE_Q + [("story", "Company history and what makes it different"), ("growth", "Growth opportunities")],
                "docs": ["3 years P&L", "3 years tax returns", "Add-back schedule", "Customer and supplier overview", "Facility / equipment list", "Photos (optional)"]},
 "qoe_lite": {"q": BASE_Q + [("ar_days", "Average days to collect receivables")],
              "docs": ["3 years monthly P&L", "3 years tax returns", "Add-back schedule with support", "AR/AP agings", "Bank statements (12 months)", "Top-10 customer revenue by year"]},
}
STATES = ["paid", "intake_sent", "intake_received", "drafting", "awaiting_review", "delivered"]
def con():
    c = duckdb.connect(str(ODB))
    c.execute("""CREATE TABLE IF NOT EXISTS orders(order_id VARCHAR PRIMARY KEY, sku VARCHAR, plan_id VARCHAR, payment_id VARCHAR, status VARCHAR,
      sandbox BOOLEAN, intake_json VARCHAR, answers_json VARCHAR, deliverable_md VARCHAR, deliverable_pdf VARCHAR, delivery_url VARCHAR,
      created_at TIMESTAMP, updated_at TIMESTAMP)""")
    c.execute("CREATE TABLE IF NOT EXISTS order_events(order_id VARCHAR, status VARCHAR, note VARCHAR, ts TIMESTAMP)")
    return c
def now(): return dt.datetime.now()
def _set(c, oid, status, note="", **cols):
    sets = ", ".join(f"{k}=?" for k in cols) + (", " if cols else "")
    c.execute(f"UPDATE orders SET {sets}status=?, updated_at=? WHERE order_id=?", [*cols.values(), status, now(), oid])
    c.execute("INSERT INTO order_events VALUES (?,?,?,?)", [oid, status, note, now()])
def token(oid): return hmac.new((os.environ.get("FULFILL_APPROVE_SECRET") or "dev-only").encode(), oid.encode(), hashlib.sha256).hexdigest()[:16]

# 1. intake agent ------------------------------------------------------------
def on_payment(evt, sandbox=True):
    d = evt.get("data", evt); plan = (d.get("plan") or {}).get("id") or d.get("plan_id"); sku = PLAN2SKU.get(plan)
    if sku not in INTAKE: return {"skipped": f"plan {plan} is not a service product"}
    oid = "ord_" + hashlib.sha1(str(d.get("id")).encode()).hexdigest()[:10]; c = con()
    if c.execute("SELECT 1 FROM orders WHERE order_id=?", [oid]).fetchone(): return {"order_id": oid, "duplicate": True}
    c.execute("INSERT INTO orders (order_id, sku, plan_id, payment_id, status, sandbox, created_at, updated_at) VALUES (?,?,?,?,?,?,?,?)",
              [oid, sku, plan, d.get("id"), "paid", sandbox, now(), now()])
    c.execute("INSERT INTO order_events VALUES (?,?,?,?)", [oid, "paid", f"Whop payment {d.get('id')}", now()])
    intake = {"order_id": oid, "service": CAT[sku]["title"].replace("IQ ", ""), "questions": [{"key": k, "label": l} for k, l in INTAKE[sku]["q"]],
              "documents": INTAKE[sku]["docs"], "url": f"{DASH}/intake.html?order={oid}&t={token(oid)}"}
    _set(c, oid, "intake_sent", "intake link ready (sent by human or Whop message after review; no auto-send)", intake_json=json.dumps(intake))
    _export(c); c.close(); return intake

# 2. analysis agents -----------------------------------------------------------
def _num(x):
    try: return float(str(x).replace(",", "").replace("$", ""))
    except Exception: return None
def _comps(vertical):
    out = {"buyers": [], "ev_band": None}
    try:
        m = duckdb.connect(str(MDB), read_only=True)
        rows = m.execute("""SELECT p.name, b.vertical, b.ev_min, b.ev_max, b.activity_score FROM buyer_mandates b JOIN platforms p USING(platform_id)
                            WHERE b.active AND (? IS NULL OR lower(b.vertical) LIKE '%'||lower(?)||'%') ORDER BY b.activity_score DESC NULLS LAST LIMIT 10""", [vertical, vertical]).fetchall()
        m.close(); out["buyers"] = [{"platform": r[0], "vertical": r[1], "ev_min": r[2], "ev_max": r[3], "activity": r[4]} for r in rows]
    except Exception as e: out["error"] = str(e)[:120]
    return out
MULT = {"SDE": (2.0, 3.1), "EBITDA": (4.0, 5.8)}
def analyze(sku, a):
    rev, earn = _num(a.get("revenue")), _num(a.get("earnings")); basis = "EBITDA" if (earn or 0) >= 1e6 else "SDE"
    lo, hi = MULT[basis]; comps = _comps((a.get("vertical") or "").lower().replace(" ", "_") or None)
    web = [] if os.environ.get("FULFILL_NO_EXA") else exa._search(f"{a.get('vertical','manufacturing')} business acquisition multiple {a.get('state','')} 2026", 5)
    L = [f"# {CAT[sku]['title'].replace('IQ ', '')}", f"_{DISCLAIMER}_", "", f"**Vertical:** {a.get('vertical')}  **Location:** {a.get('state')}"]
    if sku in ("valuation", "readiness", "teaser_cim", "qoe_lite") and earn:
        L += ["", "## Valuation range (estimate)", f"- Basis: {basis} ${earn:,.0f}" + (f" on revenue ${rev:,.0f} ({earn/rev:.0%} margin)" if rev else ""),
              f"- Multiple range: {lo}x-{hi}x  ->  **${earn*lo:,.0f} - ${earn*hi:,.0f}**", "- Reference: PE manufacturing avg ~7.1x EBITDA (GF Data 2026 mid-year) for larger deals"]
    if sku in ("readiness", "qoe_lite"):
        tc = _num(a.get("top_customer_pct")) or 0
        L += ["", "## Risk flags", f"- Customer concentration: {'HIGH' if tc >= 30 else 'ok'} ({tc:.0f}% top customer)" if tc else "- Customer concentration: provide top-10 list",
              f"- Owner dependence: {a.get('owner_hours','?')} hrs/week", "- Add-backs over 20% of earnings need documentation (QoE trigger)",
              "", "## 90-day fix list", "1. Reconcile P&L to tax returns", "2. Document every add-back with invoices", "3. Move key accounts to a second manager", "4. Monthly closes within 15 days"]
    if sku in ("buyer_landscape", "teaser_cim", "valuation"):
        L += ["", "## Active buyers in this vertical (public signals; partner names withheld)"] + [f"- Platform #{i+1}: {b['vertical']}, activity {b['activity']}" + (f", EV ${b['ev_min'] or 0:,.0f}-${b['ev_max'] or 0:,.0f}" if b['ev_max'] else "") for i, b in enumerate(comps["buyers"])] + ([] if comps["buyers"] else ["- none on file"])
    if sku == "teaser_cim":
        L += ["", "## Blind teaser", f"Established {a.get('vertical')} business in {a.get('state')}. {a.get('story','')}", f"Growth: {a.get('growth','')}"]
    if web: L += ["", "## Market sources"] + [f"- [{r.get('title')}]({r.get('url')})" for r in web]
    return "\n".join(L)
def _pdf(md, path):
    from reportlab.lib.pagesizes import letter; from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet; st = getSampleStyleSheet(); els = []
    for ln in md.splitlines():
        t = ln.replace("&", "&amp;").replace("<", "&lt;").replace("**", "")
        els.append(Paragraph(t[2:], st["Title"]) if ln.startswith("# ") else Paragraph(t[3:], st["Heading2"]) if ln.startswith("## ") else Paragraph(t, st["Normal"]) if t.strip() else Spacer(1, 6))
    SimpleDocTemplate(str(path), pagesize=letter).build(els)
def receive_intake(oid, answers, tok=None):
    if tok is not None and not hmac.compare_digest(tok, token(oid)): return {"error": "bad intake token"}
    c = con(); r = c.execute("SELECT sku, status FROM orders WHERE order_id=?", [oid]).fetchone()
    if not r or r[1] != "intake_sent": c.close(); return {"error": f"order not awaiting intake ({r and r[1]})"}
    _set(c, oid, "intake_received", "answers + document list received", answers_json=json.dumps(answers))
    _set(c, oid, "drafting", "analysis agents: DuckDB comps/buyers + Exa")
    md = analyze(r[0], answers); OUTBOX.mkdir(parents=True, exist_ok=True)
    mp, pp = OUTBOX / f"{oid}.md", OUTBOX / f"{oid}.pdf"; mp.write_text(md); _pdf(md, pp)
    _set(c, oid, "awaiting_review", "deliverable in outbox; needs human approval", deliverable_md=str(mp.relative_to(ROOT)), deliverable_pdf=str(pp.relative_to(ROOT)))
    _export(c); c.close(); return {"order_id": oid, "status": "awaiting_review", "md": str(mp), "pdf": str(pp)}

# 3. human approval -> delivery -----------------------------------------------
def approve(oid, secret):
    if not secret or secret != os.environ.get("FULFILL_APPROVE_SECRET"): return {"error": "approval secret required"}
    c = con(); r = c.execute("SELECT status, sandbox, payment_id FROM orders WHERE order_id=?", [oid]).fetchone()
    if not r or r[0] != "awaiting_review": c.close(); return {"error": f"order not awaiting review ({r and r[0]})"}
    url = f"https://whop.com/hub/ (deliverable attached to membership for payment {r[2]})"
    note = "SANDBOX: delivery recorded, nothing sent" if r[1] else "approved by human; deliver via Whop membership message/file"
    _set(c, oid, "delivered", note, delivery_url=url); _export(c); c.close(); return {"order_id": oid, "status": "delivered", "note": note}

def _export(c):  # PII-free order board for the dashboard
    rows = c.execute("SELECT order_id, sku, status, sandbox, updated_at FROM orders ORDER BY created_at DESC LIMIT 50").fetchall()
    ev = c.execute("SELECT order_id, status, note, ts FROM order_events ORDER BY ts").fetchall()
    intakes = {r[0]: json.loads(r[1]) for r in c.execute("SELECT order_id, intake_json FROM orders WHERE intake_json IS NOT NULL").fetchall()}
    for i in intakes.values(): i.pop("url", None)
    p = ROOT / "dashboard/public/data/orders.json"
    p.write_text(json.dumps({"states": STATES, "orders": [dict(zip(["order_id", "sku", "status", "sandbox", "updated_at"], r)) for r in rows],
        "events": [dict(zip(["order_id", "status", "note", "at"], e)) for e in ev], "intakes": intakes}, indent=1, default=str))

def fulfill(payment):  # backward-compatible hook used by orchestrator.whop_sync
    return on_payment(payment, sandbox=False)

if __name__ == "__main__":  # demo: simulated sandbox order end to end
    import sys
    os.environ.setdefault("FULFILL_APPROVE_SECRET", "demo-secret-not-real")
    sku = sys.argv[1] if len(sys.argv) > 1 else "valuation"
    evt = {"type": "payment.succeeded", "data": {"id": f"pay_SANDBOX_{sku}_{int(now().timestamp())}", "plan": {"id": CAT[sku]["plan_id"]}, "status": "paid"}}
    i = on_payment(evt, sandbox=True); print("1 intake:", json.dumps({k: i[k] for k in ("order_id", "service", "documents")}))
    ans = {"company": "Demo Precision Co (fictional)", "vertical": "precision machining", "state": "NC", "revenue": "6,200,000", "earnings": "1,150,000",
           "employees": "38", "top_customer_pct": "34", "owner_hours": "55", "timeline": "12 months", "story": "Family-owned AS9100 shop since 1986.", "growth": "Second shift; medical work."}
    print("2 draft:", receive_intake(i["order_id"], ans, token(i["order_id"])))
    print("  approve w/o secret:", approve(i["order_id"], "wrong"))
    print("3 approve:", approve(i["order_id"], os.environ["FULFILL_APPROVE_SECRET"]))
    c = con(); print("events:", [e[0] for e in c.execute("SELECT status FROM order_events WHERE order_id=? ORDER BY ts", [i["order_id"]]).fetchall()])
