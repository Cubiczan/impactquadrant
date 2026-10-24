"""Creates one SYNTHETIC demo owner check (no real person) so the reviewer page can be tested end to end."""
import sys, pathlib; sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from rollupops import review as r
r.capture_consent("demo-owner-001", "owner_verification", "demo-target", True)
r.attach_evidence("demo-owner-001", "DEMO (synthetic). Speaker said they own a precision machining shop (~40 staff) in Ohio-style Midwest region, founded 1998, "
                  "described two product lines and named their CNC equipment consistently. Wants a confidential valuation within 12 months; succession reason (retirement). "
                  "Contact demo@example.com, 555-123-4567.", {"sector": "Precision machining", "size_band": "$5-10M revenue", "region": "US Midwest", "partner": "SHOULD BE STRIPPED"})
for c in ("demo-owner-001",): print(c, r.publish_bundle(c))
