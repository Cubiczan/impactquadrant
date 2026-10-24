"""Terac human-in-the-loop: EXACTLY two places. Everything else is fully automated.
  1. owner_verification  - with consent, non-blocking, before a listing/teaser goes out.
  2. buyer_screening     - ONLY when flagged high-value: (a) new/unverified buyer requests confidential deal boxes,
                           (b) anyone moves toward the commission retainer or a >= $15k fee path, or
                           (c) anomaly score >= ANOMALY_THRESHOLD. Human checks intent + fraud.
NOT used for: teasers, subscriptions, scoring, matching, marketing, checkout, service fulfillment
(fulfillment keeps the owner's own approval, not Terac).
Gated by TERAC_ENABLED=1 (org pending). Flag off -> item queued as pending_human; low-value paths never block."""
import os, json, datetime as dt
from pathlib import Path
ENABLED = os.environ.get("TERAC_ENABLED") == "1"
MCP = "https://terac.com/api/mcp"; CAP = 5
FEE_THRESHOLD = 15000.0
ANOMALY_THRESHOLD = float(os.environ.get("TERAC_ANOMALY_THRESHOLD", "0.7"))
ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "dashboard/public/data/human_checks.json"
BADGE = {"verified": "Verified by human (Terac)", "flagged": "Flagged", "pending": "Human verification pending",
         "pending_human": "Queued for human check (Terac off)"}
_used = {"owner_verification": 0, "buyer_screening": 0}
_queue = {"owner_verification": [], "buyer_screening": []}
SCRIPTS = {"owner_verification": "Disclosed: caller works with Impact Quadrant. Consent first; no recording without consent. Confirm the business operates at the stated location, the speaker is an owner, and genuine interest in a confidential valuation/sale. Flag anything inconsistent.",
           "buyer_screening": "Confirm buyer identity (firm site / firm-domain email / ID match), plausibility of funds vs. deal size, and real acquisition intent. Flag data harvesting, competitor fishing or mismatched identity."}
def _enqueue(kind, ref, reason, blocking):
    if ENABLED and _used[kind] < CAP:
        _used[kind] += 1; status = "pending"  # live path walks the Terac MCP flow; results flip status later
    else:
        status = "pending_human"
    item = {"kind": kind, "ref": ref, "reason": reason, "status": status, "blocking": blocking,
            "badge": BADGE[status], "queued_at": dt.datetime.now().isoformat(timespec="seconds")}
    _queue[kind].append(item); return item
def owner_verification(target):
    """Non-blocking: the listing goes out on automated checks; human call runs in parallel with owner consent."""
    if not all(target["checks"].values()):
        return {"kind": "owner_verification", "status": "not_sent", "reason": "failed automated pre-screen", "badge": BADGE["flagged"], "flagged": True, "blocking": False}
    return {**_enqueue("owner_verification", target["id"], "consented owner check before listing/teaser", blocking=False), "flagged": False}
def screening_triggers(event):
    """event: {buyer, buyer_verified, action, fee, anomaly}. Returns list of trigger reasons (empty = no human)."""
    r = []
    if event.get("action") == "confidential_deal_box" and not event.get("buyer_verified"): r.append("unverified buyer requested confidential deal box")
    if event.get("action") == "commission_retainer": r.append("moving toward commission retainer")
    if float(event.get("fee") or 0) >= FEE_THRESHOLD: r.append(f"fee path >= ${FEE_THRESHOLD:,.0f}")
    if float(event.get("anomaly") or 0) >= ANOMALY_THRESHOLD: r.append(f"anomaly score >= {ANOMALY_THRESHOLD}")
    return r
def buyer_screening(event):
    """Only flagged high-value events reach a human. These block the high-value step until cleared; nothing else blocks."""
    why = screening_triggers(event)
    if not why: return {"kind": "buyer_screening", "status": "not_needed", "blocking": False}
    return _enqueue("buyer_screening", event.get("buyer"), "; ".join(why), blocking=True)
def flush():
    out = {"enabled": ENABLED, "anomaly_threshold": ANOMALY_THRESHOLD, "fee_threshold": FEE_THRESHOLD, **_queue,
           "rules": {"owner_verification": "with consent, non-blocking, before a listing/teaser goes out",
                     "buyer_screening": "unverified buyer requests confidential deal box OR commission retainer / >= $15k fee path OR anomaly >= threshold"}}
    QUEUE.parent.mkdir(parents=True, exist_ok=True); QUEUE.write_text(json.dumps(out, indent=1)); return out
if __name__ == "__main__":
    for e in [{"buyer": "demo-new", "action": "teaser_view"}, {"buyer": "demo-new", "action": "confidential_deal_box"},
              {"buyer": "demo-v", "buyer_verified": True, "action": "checkout", "fee": 499}, {"buyer": "demo-v", "buyer_verified": True, "action": "fee", "fee": 42000},
              {"buyer": "demo-x", "action": "subscribe", "anomaly": 0.9}]:
        print(e["action"], "->", buyer_screening(e)["status"])
