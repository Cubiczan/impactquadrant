"""Exa search (env EXA_API_KEY). Returns [] when no key, so the pipeline uses curated data/."""
import os, json, urllib.request
def _search(q, n=8):
    k = os.environ.get("EXA_API_KEY")
    if not k: return []
    req = urllib.request.Request("https://api.exa.ai/search", data=json.dumps({"query": q, "numResults": n, "type": "auto", "contents": {"summary": True}}).encode(),
                                 headers={"x-api-key": k, "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=40) as r: return json.loads(r.read()).get("results", [])
    except Exception as e: print("exa error", e); return []
def discover_buyers():
    out = []
    for r in _search("press release 2026: private-equity-backed platform completes add-on acquisition of a family-owned precision machining or industrial distribution company"):
        out.append({"platform": r.get("title", "")[:80], "sponsor": "see source", "sector": "precision machining" if "machin" in (r.get("summary") or "").lower() else "industrial distribution",
                    "regions": ["US"], "signals": [{"type": "addon_press", "date": (r.get("publishedDate") or "")[:7], "note": (r.get("summary") or "")[:200], "url": r["url"]}]})
    return out
def source_targets():
    out = []
    for q, trade in [("family-owned CNC precision machine shop in the Carolinas, AS9100, founded decades ago", "precision machining"),
                     ("family-owned industrial distributor of bearings, power transmission and MRO in the Southeast US", "industrial distribution")]:
        for r in _search(q):
            out.append({"name": r.get("title", "")[:60], "trade": trade, "town": "", "state": "", "website": r["url"], "notes": (r.get("summary") or "")[:300], "src": "exa"})
    return out
