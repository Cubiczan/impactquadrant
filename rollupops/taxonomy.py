import re
# ordered: first hit = primary vertical
KW = [("veterinar|vet |pet ", "veterinary"), ("entrance|automatic door|commercial door|access system|access /", "commercial_access"),
 ("window|door|opening", "openings"), ("roof|exterior|siding|gutter", "exterior"), ("restor|mold|water damage|fire damage", "restoration"),
 ("tree|arbor", "tree_care"), ("hvac|plumb|electric|heating|cooling|\\bmep\\b|air condition", "home_services_mep"),
 ("facilit|janitor|field service", "facilities"), ("pest", "pest_control"), ("landscap|lawn", "landscaping"),
 ("property|association|hoa|vacation rental", "property_mgmt"), ("wealth|\\bria\\b|investment advis", "wealth"),
 ("home health|healthcare|hospice", "home_healthcare"), ("software|saas|platform for", "software"),
 ("machin|cnc", "precision_machining"), ("distribut|mro|bearing|fluid", "distribution"), ("automation", "industrial_automation"),
 ("manufactur|fabricat|stamping|industrial", "manufacturing"), ("accounting|cpa|legal|consult|engineering|professional|insurance", "professional_services")]
def verticals(text):
    t = " " + (text or "").lower() + " "; out = [v for k, v in KW if re.search(k, t)]
    return list(dict.fromkeys(out)) or ["other"]
from pathlib import Path as _P
import json as _json
_LANES = _P(__file__).resolve().parent.parent / "data/raw/private/partner_lanes.json"  # untracked private overlay
PARTNER_LANES = _json.loads(_LANES.read_text()) if _LANES.exists() else {}
US = {"alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA","colorado":"CO","connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA","hawaii":"HI","idaho":"ID","illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS","kentucky":"KY","louisiana":"LA","maine":"ME","maryland":"MD","massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS","missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ","new mexico":"NM","new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK","oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC","south dakota":"SD","tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT","virginia":"VA","washington":"WA","west virginia":"WV","wisconsin":"WI","wyoming":"WY","district of columbia":"DC"}
def state(s):
    if not s: return None
    s = str(s).strip(); m = re.search(r"\b([A-Z]{2})\b", s)
    if s.lower() in US: return US[s.lower()]
    for k, v in US.items():
        if k in s.lower(): return v
    return m.group(1) if m else None
