"""Terac = human-in-the-loop TRUST & FRAUD layer. Agents run the brokerage; humans guarantee trust.
Two tasks, both async/non-blocking, run ONLY on items that passed automated pre-screens, cap 5 participants per task:
  seller_verification: human call with owner -> business exists, owner identity, real sell intent; flag fraud.
  buyer_verification:  human check buyer is real (identity, proof-of-funds plausibility, not a scammer/data harvester)
                       BEFORE full deal memo / owner identity is released; flag fraud.
Disabled until TERAC_ENABLED=1 and a researcher org + TERAC_API_KEY exist."""
import os
ENABLED = os.environ.get("TERAC_ENABLED") == "1"
MCP = "https://terac.com/api/mcp"; CAP = 5
FLOW = ["terac_get_context", "terac_request_feasibility", "poll price", "terac_create_opportunity",
        "terac_launch_draft_opportunity", "poll terac_get_submissions", "terac_approve_submission"]
BADGE = {"verified": "Verified by human (Terac)", "flagged": "Flagged", "pending": "Human verification pending",
         "disabled": "Agent-vetted (human verification off)"}
_used = {"seller_verification": 0, "buyer_verification": 0}
def _task(kind, prescreen_ok, ref):
    if not prescreen_ok: return {"task": kind, "status": "not_sent", "reason": "failed automated pre-screen", "badge": BADGE["flagged"], "flagged": True}
    if not ENABLED: return {"task": kind, "status": "disabled", "badge": BADGE["disabled"], "flagged": False}
    if _used[kind] >= CAP: return {"task": kind, "status": "over_cap", "badge": BADGE["pending"], "flagged": False, "needs_shyam": "Terac spend over cap"}
    _used[kind] += 1
    # Live path (when enabled) walks FLOW via the Terac MCP; results land later via polling and flip the badge.
    return {"task": kind, "status": "pending", "badge": BADGE["pending"], "flagged": False, "ref": ref, "mcp": MCP}
def seller_verification(target): return _task("seller_verification", all(target["checks"].values()), target["id"])
def buyer_verification(buyer):
    pre = bool(buyer.get("signals")) and buyer.get("activity_score", 0) >= 25
    return _task("buyer_verification", pre, buyer["platform"])
SCRIPTS = {"seller_verification": "Disclosed: caller works with Impact Quadrant. Consent first; no recording without consent. Confirm business operates at stated location, speaker is an owner, and genuine interest in a confidential valuation/sale. Flag anything inconsistent.",
           "buyer_verification": "Confirm buyer identity (LinkedIn/firm site/ID match), plausibility of proof of funds vs. deal size, and acquisition intent. Flag data-harvesting or mismatched identity."}
