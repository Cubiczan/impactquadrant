"""Build the RollupOps DuckDB (idempotent: drops & rebuilds).
  python -m rollupops.db            -> data/rollupops.duckdb   (PUBLIC: no PII, no agreement status)
  python -m rollupops.db --private  -> $PRIVATE_RAW/../rollupops_private.duckdb (PII + private overlays; never committed)
Raw user workbooks live only in PRIVATE_RAW (they contain work emails/phones)."""
import csv, json, os, re, sys, hashlib, datetime as dt
from pathlib import Path
import duckdb
from .taxonomy import verticals, PARTNER_LANES, state as norm_state
ROOT = Path(__file__).resolve().parent.parent
PUBLIC_DB = ROOT / "data/rollupops.duckdb"
RAW = ROOT / "data/raw"
PRIVATE_RAW = Path(os.environ.get("ROLLUPOPS_PRIVATE_RAW", "/workspace/contests/terac/data/raw"))
PRIVATE_DB = PRIVATE_RAW.parent / "rollupops_private.duckdb"
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"); PHONE = re.compile(r"\(?\+?\d[\d\s().-]{8,}\d")
REGION_STATES = {"Carolinas": ["NC", "SC"], "Southeast": ["GA", "FL", "AL", "TN", "SC", "NC"], "Midwest": ["OH", "IN", "IL", "MI", "WI", "MO"]}
def hid(*p): return hashlib.sha1("|".join(str(x).lower().strip() for x in p).encode()).hexdigest()[:10]
def s(v): return None if v is None else str(v).strip() or None
def scrub(v): return PHONE.sub("[phone]", EMAIL.sub("[email]", v)) if isinstance(v, str) else v
def sheet(f, name):
    import openpyxl
    wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
    if name not in wb.sheetnames: return []
    rows = [r for r in wb[name].iter_rows(values_only=True) if any(r)]
    hdr = [s(h) or f"c{i}" for i, h in enumerate(rows[0])]
    return [dict(zip(hdr, r)) for r in rows[1:]]
def find(sheetname):  # which private workbook has this sheet
    import openpyxl
    for f in sorted(PRIVATE_RAW.glob("*.xlsx")):
        if sheetname in openpyxl.load_workbook(f, read_only=True).sheetnames: return f
def first_int(v):
    m = re.search(r"\d+", str(v or "")); return int(m.group()) if m else None

class B:
    def __init__(self, con, private):
        self.con, self.private = con, private
        self.sponsors, self.platforms, self.pv, self.portcos, self.sigs, self.ops, self.contacts = {}, {}, {}, {}, {}, {}, {}
    def sponsor(self, name, src, **kw):
        name = re.split(r"\s*\(", s(name) or "unknown")[0].strip(" ,.") or "unknown"
        sid = hid(name); row = self.sponsors.setdefault(sid, dict(sponsor_id=sid, name=name, src_file=src))
        for k, v in kw.items():
            if v and not row.get(k): row[k] = v
        return sid
    def platform(self, name, sponsor, segment, src, **kw):
        name = s(name); sid = self.sponsor(sponsor, src); pid = hid(re.split(r"\s*\(", name)[0])
        row = self.platforms.setdefault(pid, dict(platform_id=pid, name=name, sponsor_id=sid, segment=segment, src_file=src))
        for k, v in kw.items():
            if v is not None and not row.get(k): row[k] = v
        if row["src_file"] != src and src not in row["src_file"]: row["src_file"] += "; " + src
        verts = [PARTNER_LANES[name]] if name in PARTNER_LANES else verticals(f"{name} {segment}")
        for v in verts: self.pv.setdefault((pid, v), (pid, v, segment, src))
        return pid
    def signal(self, pid, typ, date, note, url, src): self.sigs.setdefault(hid(pid, typ, note, url), (hid(pid, typ, note, url), pid, typ, s(date), s(note), s(url), src))
    def contact(self, name, title, org, email, phone, src):
        if not (name or email): return
        e = s(email); e = e if e and EMAIL.fullmatch(e) else (EMAIL.search(e).group() if e and EMAIL.search(e) else None)
        p = PHONE.search(phone).group() if phone and PHONE.search(str(phone)) else None
        cid = hid(name, e, org)
        self.contacts[cid] = (cid, s(name) if self.private else None, s(title), s(org), e.split("@")[1] if e else None,
                              e if self.private else None, p if self.private else None, src)
    def operator(self, name, src, **kw):
        oid = hid(name, kw.get("state")); row = self.ops.setdefault(oid, dict(operator_id=oid, name=s(name), src_file=src))
        for k, v in kw.items():
            if v is not None and row.get(k) is None: row[k] = v
        return oid
    def ins(self, table, rows):
        if not rows: return
        if isinstance(rows[0], dict):
            cols = [r[1] for r in self.con.execute(f"PRAGMA table_info('{table}')").fetchall()]
            rows = [tuple(r.get(c) for c in cols) for r in rows]
        pk = self.con.execute(f"SELECT count(*) FROM duckdb_constraints() WHERE table_name='{table}' AND constraint_type='PRIMARY KEY'").fetchone()[0]
        self.con.executemany(f"INSERT {'OR IGNORE ' if pk else ''}INTO {table} VALUES ({','.join('?' * len(rows[0]))})", rows)

def build(private=False):
    path = PRIVATE_DB if private else PUBLIC_DB
    if path.exists(): path.unlink()
    con = duckdb.connect(str(path)); con.execute((ROOT / "sql/schema.sql").read_text()); b = B(con, private)
    lic = json.loads((ROOT / "data/state_licensing.json").read_text())
    b.ins("jurisdictions", [(k, "US_STATE", v["status"], v.get("basis"), v.get("source"), "data/state_licensing.json") for k, v in lic["states"].items()]
          + [(k, "COUNTRY", v["status"], v.get("basis"), v.get("source"), "data/state_licensing.json") for k, v in lic["countries"].items()])
    # --- curated public sources ---
    for r in (csv.DictReader(open(RAW / "private/partner_platforms.csv")) if (RAW / "private/partner_platforms.csv").exists() else []):  # untracked private overlay
        pid = b.platform(r["platform"], "Partner A", r["verticals"], "data/raw/private/partner_platforms.csv", priority=int(r["priority"]), regions_json='["US"]', thesis=r["pull"])
        b.signal(pid, "hunger", None, r["hunger_signal"], r["urls"], "partner_map")
    for x in json.loads((ROOT / "data/buyer_signals.json").read_text()):
        pid = b.platform(x["platform"], x["sponsor"], x["sector"], "data/buyer_signals.json", regions_json=json.dumps(x.get("regions")))
        for g in x["signals"]: b.signal(pid, g["type"], g.get("date"), g.get("note"), g.get("url"), "data/buyer_signals.json")
    for r in (csv.DictReader(open(RAW / "private/pe_buyer_registry.csv")) if (RAW / "private/pe_buyer_registry.csv").exists() else []):  # untracked private overlay
        if r["platform"] == "unknown": continue
        pid = b.platform(r["platform"], r["pe_sponsor"], r["trade"], "data/raw/private/pe_buyer_registry.csv", regions_json=json.dumps([r["state"]]))
        b.portcos[hid(r["portfolio_company"], r["city"])] = (hid(r["portfolio_company"], r["city"]), r["portfolio_company"], pid, r["city"], r["state"], r["trade"], r["acquired_date"], r["source_url"], "data/raw/private/pe_buyer_registry.csv")
        b.signal(pid, "registry", r["acquired_date"], r["portfolio_company"], r["source_url"], "data/raw/private/pe_buyer_registry.csv")
    for t in json.loads((ROOT / "data/targets_raw.json").read_text()):
        b.operator(t["name"], "data/targets_raw.json", trade=t["trade"], vertical=verticals(t["trade"])[0], town=t["town"], state=t["state"], country="US",
                   website=t.get("website"), notes=t.get("notes"), independent=True)
    # --- user workbooks (private raw; provenance = file::sheet) ---
    load_workbooks(b)
    from . import inbox; inbox.load(b)  # sales-swarm feeds
    if (cp := PRIVATE_RAW / "contacts_private.csv").exists():
        for r in csv.DictReader(open(cp)): b.contact(r["name"], None, r["sponsor"], r["email"], None, "contacts_private.csv")
    if private and (sp := PRIVATE_RAW / "signed_buyers.csv").exists():
        for r in csv.DictReader(open(sp)): b.sponsor(r["sponsor"], "signed_buyers.csv (private)", agreement_status=r["agreement_status"])
    b.ins("sponsors", list(b.sponsors.values())); b.ins("platforms", list(b.platforms.values())); b.ins("platform_verticals", list(b.pv.values()))
    b.ins("portfolio_companies", list(b.portcos.values())); b.ins("buyer_signals", list(b.sigs.values()))
    b.ins("operators", list(b.ops.values())); b.ins("contacts", list(b.contacts.values()))
    if (lp := ROOT / "out/03_listings.json").exists():
        b.ins("listings", [(l["targetId"], l["title"], l["trade"], verticals(l["trade"])[0], l.get("region"), json.dumps(REGION_STATES.get(l.get("region"), [])),
                            l.get("revenueBand"), l.get("earningsBand"), l.get("_val_lo"), l.get("valuationBand"), l.get("score"), bool(l.get("verified")), l.get("status"), "out/03_listings.json")
                           for l in json.loads(lp.read_text())])
    con.execute((ROOT / "sql/views.sql").read_text())
    from . import agents; agents.run_all(con)
    con.close(); return path

def load_workbooks(b):
    tag = lambda f, sh: f"{f.name}::{sh}"
    if f := find("Roll-up Investors"):   # 1,020-firm universe extract: rollup sponsors + work contacts
        for r in sheet(f, "Roll-up Investors"):
            src = tag(f, "Roll-up Investors")
            b.sponsor(r["Firm Name"], src, website=s(r.get("Website")), hq_city=s(r.get("HQ City")), hq_state=norm_state(r.get("State/Province")), country=s(r.get("Country")),
                      rollup_model=s(r.get("Roll-up Model")), active_sectors=s(r.get("Active Sectors")), evidence_url=s(r.get("Evidence of Roll-up Strategy (URL)")))
            b.contact(r.get("Contact Name"), r.get("Contact Title"), r["Firm Name"], r.get("Work Email"), None, src)
        for r in sheet(f, "Master Targets"):
            src = tag(f, "Master Targets"); own = s(r.get("Ownership Status")) or ""
            b.operator(r["Company"], src, trade=s(r.get("Sub-vertical")), vertical=verticals(f'{r.get("Sub-vertical")} {r.get("Service Group")}')[0], service_group=s(r.get("Service Group")),
                       town=s(r.get("HQ City")), state=norm_state(r.get("State/Province")), country=s(r.get("Country")), website=s(r.get("Website")), size_estimate=s(r.get("Size Estimate")),
                       ownership=own, sponsor_if_known=scrub(s(r.get("Sponsor (if known)"))), independent=own.lower().startswith(("independent", "founder", "family", "private")),
                       notes=scrub(s(r.get("Why It Fits"))), evidence_url=s(r.get("Evidence Source URL")))
    if f := find("Firm Refresh G-O"):
        for r in sheet(f, "Firm Refresh G-O"):
            b.sponsor(r["Firm Name"], tag(f, "Firm Refresh G-O"), website=s(r.get("Original URL")), firm_status=s(r.get("Status")), firm_status_notes=scrub(s(r.get("Notes"))))
    if f := find("Platforms"):   # veterinary consolidators
        for r in sheet(f, "Platforms"):
            src = tag(f, "Platforms")
            pid = b.platform(r["Platform"], r.get("Parent / Sponsor"), "veterinary: " + (s(r.get("Segments acquired")) or ""), src, hq=s(r.get("HQ (City, State)")),
                             regions_json=json.dumps([s(r.get("Geographic focus"))]), appetite=s(r.get("Stated appetite (size/EBITDA criteria)")), deal_size=s(r.get("Typical deal size")),
                             status=s(r.get("Status")), confidence=s(r.get("Confidence")), source_urls=s(r.get("Source URLs")))
            b.signal(pid, "addon_activity", s(r.get("Source dates")), s(r.get("Add-on activity (dated examples + counts)")), s(r.get("Source URLs")), src)
            for dm in re.split(r";", s(r.get("Key decision-makers (public)")) or ""):
                if "—" in dm: n, t = dm.split("—", 1); b.contact(n.strip(), t.strip()[:80], r["Platform"], None, None, src)
    if f := find("Master Platform List"):   # consolidated Partner A + non-Partner A rollup buyer universe
        for r in sheet(f, "Master Platform List"):
            src = tag(f, "Master Platform List")
            b.platform(r["Platform"], r.get("PE Sponsor"), s(r.get("Vertical(s)")) or s(r.get("Segment (lane)")), src, hq=s(r.get("HQ")), regions_json='["US"]',
                       appetite=scrub(s(r.get("Stated Appetite / ICP"))), addons_logged=first_int(r.get("Add-ons Logged 2024-26")), status=scrub(s(r.get("Activity Status (dated evidence)"))),
                       confidence=s(r.get("Confidence")), thesis=scrub(s(r.get("Why It Matters"))))
            bc = s(r.get("Buyer Contact (published)")) or ""
            if EMAIL.search(bc): b.contact(re.split(r"[<(]", bc)[0].strip() if "<" in bc else None, None, r["Platform"], EMAIL.search(bc).group(), None, src)
        for r in sheet(f, "Add-On Log 2024-2026"):
            src = tag(f, "Add-On Log 2024-2026"); tgt = s(r.get("Target"))
            if not tgt: continue
            pid = b.platform(r["Platform"], r.get("PE Sponsor") or "unknown", s(r.get("Segment")), src)
            m = re.match(r"(.*?)\s*\((.*)\)", tgt); nm, loc = (m.group(1), m.group(2)) if m else (tgt, "")
            city = loc.split(",")[0].strip() if loc else None
            b.portcos.setdefault(hid(nm, city), (hid(nm, city), nm, pid, city, norm_state(loc), s(r.get("Segment")), s(r.get("Date (as published)")), s(r.get("Source")), src))
            b.signal(pid, "addon_log", r.get("Date (as published)"), tgt, r.get("Source"), src)
        for r in sheet(f, "Sell-Side Candidates (27)"):
            src = tag(f, "Sell-Side Candidates (27)"); hq = s(r.get("HQ + Footprint")) or ""
            b.operator(r["Company"], src, trade=s(r.get("Vertical")), vertical=PARTNER_LANES.get(next((p for p in PARTNER_LANES if p.split()[0] in (r.get("Lane") or "")), ""), None) or verticals(r.get("Vertical"))[0],
                       town=hq.split(",")[0], state=norm_state(hq), country="US", ownership=scrub(s(r.get("Ownership Profile"))), independent=True,
                       sale_intent=scrub(s(r.get("Sale-Intent Signals"))), lane=s(r.get("Lane")), size_estimate=scrub(s(r.get("Scale Indicators"))), notes=scrub(s(r.get("Why-Not-Broker"))), evidence_url=s(r.get("Sources")))
            b.contact(None, "company contact path", r["Company"], None, r.get("Contact Path"), src)
        b.ins("candidate_buyer_map", [(s(r["Company"]), s(r.get("Lane")), s(r.get("Best Partner Buyer")), s(r.get("Non-Partner Buyers")), s(r.get("Fit Rationale")), s(r.get("Candidate Confidence")), tag(f, "Candidate-Buyer Match"))
                                      for r in sheet(f, "Candidate-Buyer Match")])
        b.ins("exclusions", [(s(r["Entity"]), s(r.get("Category")), scrub(s(r.get("Reason / Evidence"))), tag(f, "Excluded & Why (Combined)")) for r in sheet(f, "Excluded & Why (Combined)")])
    for f in sorted(PRIVATE_RAW.glob("*.docx")):
        import docx
        d = docx.Document(f); body = "\n".join(p.text for p in d.paragraphs if p.text.strip())
        for t in d.tables: body += "\n" + "\n".join(" | ".join(c.text for c in row.cells) for row in t.rows)
        b.ins("documents", [(hid(f.name), d.paragraphs[0].text[:120], "sell_side_process", scrub(body), f.name)])

if __name__ == "__main__":
    p = build(private="--private" in sys.argv); con = duckdb.connect(str(p), read_only=True); print(p)
    for (t,) in con.execute("select table_name from information_schema.tables where table_type='BASE TABLE' order by 1").fetchall():
        print(f"{t:22s}", con.execute(f"select count(*) from {t}").fetchone()[0])
