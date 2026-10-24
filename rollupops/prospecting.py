"""ImpactQuadrant prospecting pipeline: ingest -> GREEN gate -> dedupe -> DNC -> enrich -> store.

Store: Algolia when ALGOLIA_APP_ID + ALGOLIA_ADMIN_KEY are set, else local DuckDB (data/prospects.duckdb).
Do-not-contact (DNC) is enforced on every write AND every export: a DNC hit is never stored as a prospect
and never returned as contactable. Nothing here sends outreach. Secrets are read from env and never logged.
Enrichment is opt-in and capped (credits used sparingly): Tavily (PE-ownership check), Hunter (email count),
Context.dev (brand retrieve). PE owners found are appended to the PE buyer registry CSV.
"""
from __future__ import annotations
import csv, hashlib, json, os, re, datetime as dt
from pathlib import Path
from urllib.parse import urlparse
from . import jurisdiction

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.environ.get("PROSPECTS_DB", str(ROOT / "data/prospects.duckdb")))
REGISTRY = Path(os.environ.get("PE_REGISTRY_CSV", "/workspace/pipeline/outreach/impact-quadrant/pe-buyer-registry/registry.csv"))
REGISTRY_COLS = ["platform", "pe_sponsor", "portfolio_company", "city", "state", "trade", "acquired_date", "source_url",
                 "found_by", "date_found", "cross_ref", "reach_status"]
GREEN_COUNTRIES = {"BR", "CH", "DE", "ES", "JP", "MX"}
NATIONAL_CHAINS = re.compile(r"\b(roto-rooter|mr\.? rooter|benjamin franklin|one hour|aire serv|ars|home depot|lowe'?s|sears)\b", re.I)
PE_PAT = re.compile(r"(?:acquired by|partnered with|joins|backed by|investment from|portfolio company of)\s+([A-Z][\w&.,' -]{2,60}?(?:Capital|Partners|Equity|Group|Holdings|Investors|Services)(?: Partners| Group| Fund)?)", re.I)

# ---------- normalisation / keys ----------
def domain_of(url: str | None) -> str:
    if not url: return ""
    u = url if "://" in url else "http://" + url
    h = (urlparse(u).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h
def phone_digits(p: str | None) -> str:
    d = re.sub(r"\D", "", p or "")
    return d[-10:] if len(d) >= 10 else d
def norm_name(n: str | None) -> str:
    n = re.sub(r"[^a-z0-9 ]", "", (n or "").lower())
    return re.sub(r"\b(llc|inc|co|company|corp|the)\b", "", n).strip()
def keys(p: dict) -> list[str]:
    ks = []
    if p.get("domain"): ks.append("d:" + p["domain"])
    if p.get("phone"): ks.append("p:" + p["phone"])
    for e in p.get("emails") or []: ks.append("e:" + e.lower())
    if p.get("name"): ks.append("n:" + norm_name(p["name"]) + "|" + (p.get("city") or "").lower())
    return ks
def object_id(p: dict) -> str:
    return hashlib.sha1(keys(p)[0].encode()).hexdigest()[:16]

def normalize(row: dict, trade: str, state: str, source: str) -> dict:
    web = row.get("website") or row.get("web_site") or ""
    emails = [e.strip().lower() for e in re.split(r"[,;\s]+", row.get("emails") or row.get("email") or "") if "@" in e]
    addr = row.get("address") or ""
    city = row.get("city") or ""
    if not city and addr:
        m = re.search(r",\s*([A-Za-z .]+),\s*([A-Z]{2})\s*\d{5}", addr)
        if m: city = m.group(1).strip(); state = state or m.group(2)
    p = {"name": (row.get("title") or row.get("name") or "").strip(), "domain": domain_of(web), "website": web,
         "phone": phone_digits(row.get("phone")), "emails": emails, "address": addr, "city": city, "state": state.upper(),
         "country": "US", "trade": trade, "rating": row.get("review_rating") or row.get("rating") or "",
         "reviews": row.get("review_count") or "", "source": source, "created": dt.date.today().isoformat(),
         "pe_owner": "", "pe_evidence": "", "status": "new"}
    p["objectID"] = object_id(p) if keys(p) else ""
    return p

def green_ok(p: dict) -> bool:
    if p.get("country", "US") != "US": return p["country"] in GREEN_COUNTRIES
    return jurisdiction.lookup("US", p.get("state")).get("status") == "GREEN"

# ---------- stores ----------
class DuckStore:
    def __init__(self, path: Path = DB_PATH):
        import duckdb
        path.parent.mkdir(parents=True, exist_ok=True)
        self.c = duckdb.connect(str(path))
        self.c.execute("create table if not exists prospects(objectID varchar primary key, k varchar[], data json)")
        self.c.execute("create table if not exists dnc(k varchar primary key, reason varchar, added varchar)")
    def dnc_hit(self, ks): 
        if not ks: return None
        r = self.c.execute("select k from dnc where k in (select unnest(?))", [ks]).fetchone()
        return r[0] if r else None
    def add_dnc(self, k, reason):
        self.c.execute("insert or replace into dnc values (?,?,?)", [k, reason, dt.date.today().isoformat()])
        self.c.execute("delete from prospects where list_contains(k, ?)", [k])
    def find_dup(self, ks):
        r = self.c.execute("select objectID from prospects where len(list_intersect(k, ?))>0", [ks]).fetchone()
        return r[0] if r else None
    def upsert(self, p):
        self.c.execute("insert or replace into prospects values (?,?,?)", [p["objectID"], keys(p), json.dumps(p)])
    def all(self):
        return [json.loads(r[0]) for r in self.c.execute("select data from prospects").fetchall()]
    def count_dnc(self): return self.c.execute("select count(*) from dnc").fetchone()[0]

class AlgoliaStore:
    """Indices: iq_prospects, iq_dnc (objectID = key). Uses the REST API; admin key from env only."""
    def __init__(self):
        import requests
        self.r = requests; self.app = os.environ["ALGOLIA_APP_ID"]
        self.h = {"X-Algolia-Application-Id": self.app, "X-Algolia-API-Key": os.environ["ALGOLIA_ADMIN_KEY"]}
        self.base = f"https://{self.app}.algolia.net/1/indexes"
    def _get(self, idx, oid):
        x = self.r.get(f"{self.base}/{idx}/{oid}", headers=self.h, timeout=20); return x.json() if x.ok else None
    def dnc_hit(self, ks):
        for k in ks:
            if self._get("iq_dnc", hashlib.sha1(k.encode()).hexdigest()): return k
    def add_dnc(self, k, reason):
        self.r.put(f"{self.base}/iq_dnc/{hashlib.sha1(k.encode()).hexdigest()}", headers=self.h, json={"k": k, "reason": reason}, timeout=20)
        self.r.post(f"{self.base}/iq_prospects/deleteByQuery", headers=self.h, json={"filters": f'k:"{k}"'}, timeout=20)
    def find_dup(self, ks):
        f = " OR ".join(f'k:"{k}"' for k in ks)
        x = self.r.post(f"{self.base}/iq_prospects/query", headers=self.h, json={"filters": f, "hitsPerPage": 1}, timeout=20).json()
        return (x.get("hits") or [{}])[0].get("objectID")
    def upsert(self, p):
        self.r.put(f"{self.base}/iq_prospects/{p['objectID']}", headers=self.h, json={**p, "k": keys(p)}, timeout=20)
    def all(self):
        return self.r.post(f"{self.base}/iq_prospects/browse", headers=self.h, json={}, timeout=30).json().get("hits", [])
    def count_dnc(self): return None

def get_store():
    if os.environ.get("ALGOLIA_APP_ID") and os.environ.get("ALGOLIA_ADMIN_KEY"): return AlgoliaStore()
    return DuckStore()

# ---------- pipeline ----------
def ingest(rows, store, trade, state, source, limit=25):
    st = {"in": 0, "stored": 0, "dup": 0, "dnc": 0, "not_green": 0, "chain": 0, "no_key": 0}
    for row in rows:
        if st["stored"] >= limit: break
        st["in"] += 1
        p = normalize(row, trade, state, source)
        if not p["objectID"]: st["no_key"] += 1; continue
        if not green_ok(p): st["not_green"] += 1; continue
        if NATIONAL_CHAINS.search(p["name"]): st["chain"] += 1; continue
        ks = keys(p)
        if store.dnc_hit(ks): st["dnc"] += 1; continue
        dup = store.find_dup(ks)
        if dup: st["dup"] += 1; continue
        store.upsert(p); st["stored"] += 1
    return st

def contactable(store):
    """Export view: re-checks DNC at read time so later DNC additions always win."""
    return [p for p in store.all() if not store.dnc_hit(keys(p))]

# ---------- enrichment (capped, opt-in) ----------
def tavily_pe_check(p, http=None):
    import requests; http = http or requests
    q = f'"{p["name"]}" {p["city"]} {p["state"]} acquired OR "partnered with" private equity'
    r = http.post("https://api.tavily.com/search", json={"query": q, "max_results": 5, "search_depth": "basic"},
                  headers={"Authorization": "Bearer " + os.environ["TAVILY_API_KEY"]}, timeout=40)
    res = r.json().get("results", []) if r.ok else []
    nm = norm_name(p["name"])
    for x in res:
        txt = (x.get("title", "") + " " + x.get("content", ""))
        low = re.sub(r"[^a-z0-9 ]", "", txt.lower())
        i = low.find(nm) if nm else -1
        if i < 0: continue                      # full company name must appear (cuts false positives)
        if p.get("state") and p["state"].lower() not in low.split() and (p.get("city") or "~").lower() not in low and p.get("domain", "~") not in txt.lower():
            continue                            # and some locality / domain evidence
        for m in PE_PAT.finditer(txt):
            if abs(m.start() - txt.lower().find(nm.split()[0])) <= 250:
                return m.group(1).strip(" ,."), x.get("url", "")
    return "", ""

def hunter_count(domain, http=None):
    import requests; http = http or requests
    r = http.get("https://api.hunter.io/v2/email-count", params={"domain": domain, "api_key": os.environ["HUNTER_API_KEY"]}, timeout=30)
    return (r.json().get("data") or {}).get("total") if r.ok else None   # email-count is free on Hunter

def context_brand(domain, http=None):
    import requests; http = http or requests
    r = http.post("https://api.context.dev/v1/brand/retrieve", json={"type": "by_domain", "domain": domain},
                  headers={"Authorization": "Bearer " + os.environ["CONTEXT_DEV_API_KEY"]}, timeout=120)
    return r.json().get("brand", {}) if r.ok else {}

def log_pe_owner(p, sponsor, url, registry=None):
    registry = Path(registry or REGISTRY)
    registry.parent.mkdir(parents=True, exist_ok=True)
    seen = set()
    if registry.exists():
        seen = {(r.get("pe_sponsor", "").lower(), norm_name(r.get("portfolio_company"))) for r in csv.DictReader(registry.open())}
    if (sponsor.lower(), norm_name(p["name"])) in seen: return False
    new = not registry.exists()
    with registry.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=REGISTRY_COLS)
        if new: w.writeheader()
        w.writerow({"platform": "", "pe_sponsor": sponsor, "portfolio_company": p["name"], "city": p["city"], "state": p["state"],
                    "trade": p["trade"], "acquired_date": "", "source_url": url, "found_by": "impactquadrant.prospecting/tavily",
                    "date_found": dt.date.today().isoformat(), "cross_ref": "unverified: needs owner review", "reach_status": ""})
    return True

def enrich(store, max_tavily=25, max_hunter=10, max_context=0, http=None):
    out = {"tavily": 0, "hunter": 0, "context": 0, "pe_owned": []}
    for p in store.all():
        ch = False
        if out["tavily"] < max_tavily and os.environ.get("TAVILY_API_KEY") and not p.get("pe_checked"):
            s, u = tavily_pe_check(p, http); out["tavily"] += 1; p["pe_checked"] = True; ch = True
            if s:
                p["pe_owner"], p["pe_evidence"], p["status"] = s, u, "pe_owned"
                out["pe_owned"].append({"company": p["name"], "sponsor": s, "url": u, "logged": log_pe_owner(p, s, u)})
        if p["domain"] and out["hunter"] < max_hunter and os.environ.get("HUNTER_API_KEY") and "hunter_emails" not in p:
            p["hunter_emails"] = hunter_count(p["domain"], http); out["hunter"] += 1; ch = True
        if p["domain"] and out["context"] < max_context and os.environ.get("CONTEXT_DEV_API_KEY") and "brand" not in p:
            b = context_brand(p["domain"], http); p["brand"] = {k: b.get(k) for k in ("title", "description", "address") if b.get(k)}
            out["context"] += 1; ch = True
        if ch: store.upsert(p)
    return out

def load_gmaps_csv(path):
    return list(csv.DictReader(open(path, newline="", encoding="utf-8")))

if __name__ == "__main__":
    import argparse
    a = argparse.ArgumentParser(); a.add_argument("csv"); a.add_argument("--trade", required=True); a.add_argument("--state", required=True)
    a.add_argument("--limit", type=int, default=25); a.add_argument("--dnc", action="append", default=[])
    a.add_argument("--max-tavily", type=int, default=25); a.add_argument("--max-hunter", type=int, default=10); a.add_argument("--max-context", type=int, default=0)
    x = a.parse_args(); s = get_store()
    for k in x.dnc: s.add_dnc(k, "manual")
    st = ingest(load_gmaps_csv(x.csv), s, x.trade, x.state, "gmaps:" + Path(x.csv).name, x.limit)
    en = enrich(s, x.max_tavily, x.max_hunter, x.max_context)
    print(json.dumps({"store": type(s).__name__, "ingest": st, "enrich": en, "contactable": len(contactable(s))}, indent=1))
