"""Copy prospects + DNC from data/prospects.duckdb to Algolia (iq_prospects, iq_dnc). Prints counts only."""
import json, sys
from rollupops.prospecting import AlgoliaStore, DuckStore, keys
a = AlgoliaStore()
if not a.can_write():
    sys.exit("Algolia key lacks write ACL (needs addObject, deleteObject, editSettings). Use the Admin API key.")
d = DuckStore(); a.ensure_settings()
dnc = d.c.execute("select k, reason from dnc").fetchall()
for k, r in dnc: a.add_dnc(k, r or "migrated")
n = 0
for p in d.all():
    if a.dnc_hit(keys(p)): continue
    a.upsert(p); n += 1
print(json.dumps({"duck_prospects": len(d.all()), "duck_dnc": len(dnc), "migrated": n}))
