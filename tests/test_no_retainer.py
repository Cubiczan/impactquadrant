from rollupops import commission, marketing
import inspect

def test_no_retainer_in_engagement_or_checkouts():
    listing = {"targetId": "T-TEST1", "country": "US", "stateProvince": "NC", "_val_lo": 2e6}
    o = commission.offer(listing, ("US", "NC"), do_whop=False)
    assert "retainer_checkout" not in o
    if "agreement" in o:
        assert "no retainer" in o["agreement"]["text"]
        assert "Optional $" not in o["agreement"]["text"]
    assert not hasattr(commission, "RETAINER")

def test_marketing_has_no_retainer_template():
    assert "sell_side_retainer" not in inspect.getsource(marketing)
