"""Terac is used ONLY for blue-collar owner verification. No buyer review; PE buyers are vetted by the owner."""
import json, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from rollupops import terac, review, trust
ROOT = pathlib.Path(__file__).resolve().parent.parent
def test_no_buyer_screening():
    assert not hasattr(terac, "buyer_screening") and not hasattr(terac, "screening_triggers")
    assert set(terac.TEMPLATES) == {"owner_verification"} and set(terac.QUOTES) == {"owner_verification"}
    assert review.KINDS == ("owner_verification",) and set(review.QUESTIONS) == {"owner_verification"}
def test_pe_buyer_manual():
    l = trust.buyer_ladder({"signals": [{"type": "addon_press"}]}, "pe")
    assert l["L3_terac"]["status"] == "owner_manual" and not l["L3_terac"]["flagged"]
def test_capture_rejects_buyer_kind():
    import shutil
    try: review.capture_consent("t-x", "buyer_screening", "x", True); assert False
    except AssertionError: pass
    shutil.rmtree(review.LOCAL / "t-x", ignore_errors=True)
def test_draft_owner_only():
    d = terac.opportunity_draft.__wrapped__ if hasattr(terac.opportunity_draft, "__wrapped__") else terac.opportunity_draft
    try: d("buyer_screening", "x"); assert False, "buyer draft allowed"
    except AssertionError as e: assert "buyer draft allowed" not in str(e)
def test_webhook_never_routes_buyer():
    js = (ROOT / "dashboard/api/whop-webhook.js").read_text()
    assert "buyer_screening" not in js and "human_check = 'none'" in js
def test_flush_has_no_buyer_queue():
    import tempfile; terac.QUEUE = pathlib.Path(tempfile.mkdtemp()) / "hc.json"
    out = terac.flush(); assert "buyer_screening" not in out
