import pathlib, sys, tempfile
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from rollupops import prospecting as P

def _store(): return P.DuckStore(pathlib.Path(tempfile.mkdtemp()) / "p.duckdb")
ROWS = [
    {"title": "Acme Plumbing LLC", "website": "https://www.acmeplumb.com/", "phone": "(865) 555-0101", "address": "1 Main St, Knoxville, TN 37902"},
    {"title": "Acme Plumbing", "website": "acmeplumb.com", "phone": "", "address": ""},          # dup by domain
    {"title": "Beta Drains", "website": "", "phone": "865-555-0102", "address": "2 Oak, Knoxville, TN 37902"},
    {"title": "Roto-Rooter Knoxville", "website": "rotorooter.com", "phone": "8655550199"},       # chain
    {"title": "Gamma Pipes", "website": "gammapipes.com", "phone": "8655550103", "emails": "Owner@GammaPipes.com"},
]
def test_dedupe_chain_and_dnc():
    s = _store(); s.add_dnc("e:owner@gammapipes.com", "asked to stop")
    st = P.ingest(ROWS, s, "plumbing", "TN", "test")
    assert st == {"in": 5, "stored": 2, "dup": 1, "dnc": 1, "not_green": 0, "chain": 1, "no_key": 0}
    assert {p["name"] for p in s.all()} == {"Acme Plumbing LLC", "Beta Drains"}
def test_dnc_added_later_removes_and_blocks():
    s = _store(); P.ingest(ROWS[:1], s, "plumbing", "TN", "t"); s.add_dnc("d:acmeplumb.com", "x")
    assert P.contactable(s) == [] and P.ingest(ROWS[:1], s, "plumbing", "TN", "t")["dnc"] == 1
def test_non_green_state_rejected():
    s = _store(); st = P.ingest(ROWS[:1], s, "plumbing", "CA", "t")
    assert st["not_green"] == 1 and s.all() == []
def test_limit():
    s = _store(); assert P.ingest(ROWS, s, "plumbing", "TN", "t", limit=1)["stored"] == 1
def test_pe_logging_dedupes(tmp_path):
    reg = tmp_path / "r.csv"; p = P.normalize(ROWS[0], "plumbing", "TN", "t")
    assert P.log_pe_owner(p, "Foo Capital", "u", reg) and not P.log_pe_owner(p, "Foo Capital", "u", reg)
    assert reg.read_text().splitlines()[0].startswith("platform,pe_sponsor")
def test_enrich_uses_caps_and_logs(monkeypatch, tmp_path):
    class R:
        ok = True
        def __init__(s, j): s._j = j
        def json(s): return s._j
    class H:
        calls = 0
        def post(s, url, **k):
            H.calls += 1; return R({"results": [{"title": "Acme Plumbing acquired by Foo Capital Partners", "content": "Knoxville, TN", "url": "u"}]})
        def get(s, url, **k): H.calls += 1; return R({"data": {"total": 3}})
    monkeypatch.setenv("TAVILY_API_KEY", "x"); monkeypatch.setenv("HUNTER_API_KEY", "x")
    monkeypatch.setattr(P, "REGISTRY", tmp_path / "r.csv")
    s = _store(); P.ingest(ROWS[:1], s, "plumbing", "TN", "t")
    out = P.enrich(s, max_tavily=1, max_hunter=1, http=H())
    assert out["tavily"] == 1 and out["hunter"] == 1 and H.calls == 2
    assert out["pe_owned"][0]["sponsor"] == "Foo Capital Partners"

def test_pe_check_rejects_unrelated_hits(monkeypatch):
    class R:
        ok = True
        def json(s): return {"results": [{"title": "Valley Plumbing & Heating Ltd acquired by Lynx Equity", "content": "UK", "url": "u"}]}
    class H:
        def post(s, *a, **k): return R()
    monkeypatch.setenv("TAVILY_API_KEY", "x")
    p = P.normalize({"title": "Valley Plumbing, Inc.", "website": "valleyplumbingtn.com", "address": "x, Knoxville, TN 37919"}, "plumbing", "TN", "t")
    assert P.tavily_pe_check(p, H()) == ("", "")
