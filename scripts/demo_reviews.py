"""Creates two SYNTHETIC demo checks (no real person) so the reviewer page can be tested end to end."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from rollupops import review as r
r.capture_consent("demo-owner-001", "owner_verification", "demo-target", True)
r.attach_evidence("demo-owner-001", "DEMO (synthetic). Speaker said they own a precision machining shop (~40 staff) in Ohio-style Midwest region, founded 1998, "
                  "described two product lines and named their CNC equipment consistently. Wants a confidential valuation within 12 months; succession reason (retirement). "
                  "Contact demo@example.com, 555-123-4567.", {"sector": "Precision machining", "size_band": "$5-10M revenue", "region": "US Midwest", "partner": "SHOULD BE STRIPPED"})
r.capture_consent("demo-buyer-001", "buyer_screening", "demo-buyer", True, recorded=False)
r.attach_evidence("demo-buyer-001", "DEMO (synthetic). Caller presented as a principal at a lower-middle-market search fund; firm-domain email verified; "
                  "described two prior platform acquisitions; target check size consistent with $3-8M EV. Trigger: unverified buyer requested confidential deal box.",
                  {"trigger": "unverified buyer requested confidential deal box", "deal_size_band": "$3-8M EV", "firm_type": "Search fund", "price": "STRIPPED"})
for c in ("demo-owner-001", "demo-buyer-001"): print(c, r.publish_bundle(c))
