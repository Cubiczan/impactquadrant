"""Build data/rollupops.duckdb (idempotent: drops & rebuilds). Run: python -m rollupops.db
Public tables only; contacts with emails/phones load solely from PRIVATE_RAW (never committed),
and the public DB keeps only name+sponsor+email_domain."""
import csv, json, os, re, hashlib, datetime as dt
from pathlib import Path
import duckdb
ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data/rollupops.duckdb"
RAW = ROOT / "data/raw"
PRIVATE_RAW = Path(os.environ.get("ROLLUPOPS_PRIVATE_RAW", "/workspace/contests/terac/data/raw"))
INCLUDE_PII = os.environ.get("ROLLUPOPS_INCLUDE_PII") == "1"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"); PHONE = re.compile(r"\+?\d[\d\s().-]{8,}\d")
def hid(*p): return hashlib.sha1("|".join(str(x).lower().strip() for x in p).encode()).hexdigest()[:10]
VERT = {"hvac": "home_services_mep", "plumb": "home_services_mep", "electric": "home_services_mep",
        "roof": "exterior", "window": "openings", "door": "openings", "restor": "restoration", "tree": "tree_care",
        "facilit": "facilities", "machin": "precision_machining", "manufactur": "manufacturing", "fabricat": "manufacturing",
        "stamping": "manufacturing", "distribut": "distribution", "mro": "distribution", "bearing": "distribution",
        "fluid": "distribution", "automation": "industrial_automation", "property": "property_mgmt", "wealth": "wealth", "ria": "wealth"}
def verticals(text):
    t = (text or "").lower(); return sorted({v for k, v in VERT.items() if k in t}) or ["other"]
REGION_STATES = {"Carolinas": ["NC", "SC"], "Southeast": ["GA", "FL", "AL", "TN", "SC", "NC"], "Midwest": ["OH", "IN", "IL", "MI", "WI", "MO"]}

def build(path=DB):
    if path.exists(): path.unlink()
    con = duckdb.connect(str(path)); con.execute((ROOT / "sql/schema.sql").read_text())
    ins = lambda t, rows: rows and con.executemany(f"INSERT OR IGNORE INTO {t} VALUES ({','.join('?'*len(rows[0]))})", rows)
    # jurisdictions
    lic = json.loads((ROOT / "data/state_licensing.json").read_text())
    ins("jurisdictions", [(k, "US_STATE", v["status"], v.get("basis"), v.get("source"), "data/state_licensing.json") for k, v in lic["states"].items()]
        + [(k, "COUNTRY", v["status"], v.get("basis"), v.get("source"), "data/state_licensing.json") for k, v in lic["countries"].items()])
    sponsors, platforms, pv, portcos, sigs = {}, {}, [], [], []
    def plat(name, sponsor, segment, src, prio=None, regions=None, extra=None):
        sid = hid(sponsor); sponsors.setdefault(sid, (sid, sponsor, src))
        pid = hid(name); platforms.setdefault(pid, (pid, name, sid, segment, prio, json.dumps(regions or []), extra, src))
        for v in verticals(f"{name} {segment}"): pv.append((pid, v, segment, src))
        return pid
    # Partner A map
    for r in csv.DictReader(open(RAW / "private/partner_platforms.csv")):
        pid = plat(r["platform"], "Partner A", r["verticals"], "data/raw/private/partner_platforms.csv (from attachment b55de3ba…md)", int(r["priority"]), ["US"], r["pull"])
        sigs.append((hid(pid, r["hunger_signal"]), pid, "hunger", None, r["hunger_signal"], r["urls"] or None, "partner_map"))
    # buyer_signals.json
    for b in json.loads((ROOT / "data/buyer_signals.json").read_text()):
        pid = plat(b["platform"], b["sponsor"], b["sector"], "data/buyer_signals.json", None, b.get("regions"))
        for g in b["signals"]: sigs.append((hid(pid, g.get("url"), g.get("note")), pid, g["type"], g.get("date"), g.get("note"), g.get("url"), "buyer_signals.json"))
    # registry
    for r in csv.DictReader(open(RAW / "pe_buyer_registry.csv")):
        pid = plat(r["platform"], r["pe_sponsor"], r["trade"], "data/raw/pe_buyer_registry.csv", None, [r["state"]])
        portcos.append((hid(r["portfolio_company"], r["city"]), r["portfolio_company"], pid, r["city"], r["state"], r["trade"], r["acquired_date"], r["source_url"], "data/raw/pe_buyer_registry.csv"))
        sigs.append((hid(pid, r["portfolio_company"]), pid, "registry", r["acquired_date"], r["portfolio_company"], r["source_url"], "registry.csv"))
    ins("sponsors", list(sponsors.values())); ins("platforms", list(platforms.values()))
    ins("platform_verticals", pv); ins("portfolio_companies", portcos); ins("buyer_signals", sigs)
    # operators (targets) + listings
    ops = [(hid(t["name"], t["state"]), t["name"], t["trade"], verticals(t["trade"])[0], t["town"], t["state"], "US", t.get("website"), t.get("notes"), "data/targets_raw.json")
           for t in json.loads((ROOT / "data/targets_raw.json").read_text())]
    ins("operators", ops)
    lp = ROOT / "out/03_listings.json"
    if lp.exists():
        ins("listings", [(l["targetId"], l["title"], l["trade"], verticals(l["trade"])[0], l.get("region"),
                          json.dumps(REGION_STATES.get(l.get("region"), [])), l.get("revenueBand"), l.get("earningsBand"),
                          l.get("_val_lo"), l.get("valuationBand"), l.get("score"), bool(l.get("verified")), l.get("status"), "out/03_listings.json")
                         for l in json.loads(lp.read_text())])
    # contacts (PII-safe)
    cp = PRIVATE_RAW / "contacts_private.csv"
    if cp.exists():
        ins("contacts", [(hid(r["name"], r["email"]), r["name"], r["sponsor"], r["email"].split("@")[-1],
                          r["email"] if INCLUDE_PII else None, r["source"]) for r in csv.DictReader(open(cp))])
    # any other private raw files (xlsx/docx dropped by user) -> raw_documents (PII scrubbed)
    for f in sorted(PRIVATE_RAW.glob("*")):
        if f.suffix in (".xlsx", ".docx", ".csv", ".md") and f.name != "contacts_private.csv": _ingest_raw(con, f)
    con.execute((ROOT / "sql/views.sql").read_text())
    # seed agent-maintained tables
    from . import agents; agents.run_all(con)
    con.close(); return path

def _ingest_raw(con, f):
    rows = []
    if f.suffix == ".xlsx":
        import openpyxl
        for ws in openpyxl.load_workbook(f, read_only=True, data_only=True).worksheets:
            it = ws.iter_rows(values_only=True); hdr = [str(h) for h in (next(it, None) or [])]
            for i, r in enumerate(it):
                if any(r): rows.append((f.name, ws.title, i, json.dumps({h: _scrub(v) for h, v in zip(hdr, r)}, default=str)))
    elif f.suffix == ".docx":
        import docx
        for i, p in enumerate(docx.Document(f).paragraphs):
            if p.text.strip(): rows.append((f.name, "doc", i, json.dumps({"text": _scrub(p.text)})))
    else:
        for i, line in enumerate(f.read_text(errors="ignore").splitlines()):
            if line.strip(): rows.append((f.name, f.suffix, i, json.dumps({"text": _scrub(line)})))
    if rows: con.executemany("INSERT INTO raw_records VALUES (?,?,?,?)", rows)
def _scrub(v): return PHONE.sub("[phone]", EMAIL.sub("[email]", v)) if isinstance(v, str) and not INCLUDE_PII else v

if __name__ == "__main__":
    p = build(); con = duckdb.connect(str(p), read_only=True)
    for (t,) in con.execute("select table_name from information_schema.tables where table_type='BASE TABLE' order by 1").fetchall():
        print(f"{t:22s}", con.execute(f"select count(*) from {t}").fetchone()[0])
