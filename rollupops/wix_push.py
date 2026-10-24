"""Push blind teasers to Wix (Velo http-function) or export CSV for manual CMS import.
POST https://impactquadrant.info/_functions/targets with header x-rollupops-secret=$WIX_PUSH_SECRET."""
import os, json, csv, urllib.request
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
FIELDS = ['targetId','title','trade','region','revenueBand','earningsBand','yearsInBusiness','strengths','dealType','valuationBand','score','verified','status','checkoutUrl','checkoutUrlIndividual','individualUnlockPrice','equityHint','trustBadge','country','stale_after']
def rows():
    return [{k: (" · ".join(l[k]) if k == "strengths" else l.get(k)) for k in FIELDS} for l in json.loads((ROOT/"out/03_listings.json").read_text())]
def export_csv():
    p = ROOT/"wix/targets_import.csv"
    with open(p, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(rows())
    return p
def push(dry=True):
    sec = os.environ.get("WIX_PUSH_SECRET"); url = os.environ.get("WIX_SITE", "https://impactquadrant.info") + "/_functions/targets"
    body = [dict(r, staleAfter=r.pop("stale_after"), strengths=r["strengths"].split(" · ")) for r in rows()]
    if dry or not sec: print(f"DRY RUN: would POST {len(body)} teasers to {url}"); return
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json", "x-rollupops-secret": sec})
    print(urllib.request.urlopen(req, timeout=30).read().decode())
if __name__ == "__main__":
    import sys; print(export_csv()); push(dry="--send" not in sys.argv)
