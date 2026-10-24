"""Terac human-in-the-loop: EXACTLY two places. Everything else is fully automated.
  1. owner_verification  - with consent, non-blocking, before a listing/teaser goes out.
  2. buyer_screening     - ONLY when flagged high-value: (a) new/unverified buyer requests confidential deal boxes,
                           (b) anyone moves toward the commission retainer or a >= $15k fee path, or
                           (c) anomaly score >= ANOMALY_THRESHOLD. Human checks intent + fraud.
NOT used for: teasers, subscriptions, scoring, matching, marketing, checkout, service fulfillment
(fulfillment keeps the owner's own approval, not Terac).
Gated by TERAC_ENABLED=1 (queue) and TERAC_LIVE=1 + per-check owner approval (spend). Flag off -> item queued as pending_human; low-value paths never block."""
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

# ---------------------------------------------------------------------------------------------
# Real Terac REST client (v2, https://terac.com/api/external/v2). Key from env TERAC_API_KEY only.
# Spend safety: nothing here launches unless TERAC_LIVE=1 AND the specific check id is approved in
# data/terac_approvals.json (untracked) by the owner. Drafts/feasibility cost nothing but are only
# created by an explicit call; the orchestrator never calls them.
import urllib.request, urllib.error
API = "https://terac.com/api/external/v2"
LIVE = os.environ.get("TERAC_LIVE") == "1"
APPROVALS = ROOT / "data/terac_approvals.json"
TEMPLATES = {
    "owner_verification": {
        "task": "With the owner's consent, confirm a small business operates at its stated location, the person is an owner, and they genuinely want a confidential valuation or sale. Disclose the caller works with Impact Quadrant; no recording without consent. Flag inconsistencies.",
        "panel": "US-based business researchers / verification specialists experienced with small-business due diligence or KYC; English.",
        "count": 1, "timeline_hours": 72, "business_type": "b2b"},
    "buyer_screening": {
        "task": "Verify a prospective acquirer: identity (firm site, firm-domain email, public profile match), plausibility of funds versus deal size, and real acquisition intent. Flag data harvesting, competitor fishing or mismatched identity. Upload a short written finding.",
        "panel": "US-only reviewers with an M&A, private equity, business brokerage, AML or identity-verification background; English.",
        "count": 1, "timeline_hours": 48, "business_type": "b2b"},
}
def _req(method, path, body=None):
    key = os.environ.get("TERAC_API_KEY")
    if not key: return {"error": "TERAC_API_KEY not set"}
    r = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=30) as resp: return json.loads(resp.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:300]}
def context(): return _req("GET", "/organizations/current/context")              # read-only
def list_opportunities(): return _req("GET", "/opportunities")                    # read-only
def get_feasibility(rid): return _req("GET", f"/feasibility/requests/{rid}")       # read-only
def get_submissions(opp_id): return _req("GET", f"/opportunities/{opp_id}/submissions")  # read-only
def request_feasibility(kind):
    """Free quote request (POST /feasibility/requests). Explicit call only."""
    t = TEMPLATES[kind]
    return _req("POST", "/feasibility/requests", {"taskDescription": t["task"], "panelDescription": t["panel"],
                                                  "submissionCount": t["count"], "timelineHours": t["timeline_hours"]})
def _approved(check_id):
    return APPROVALS.exists() and json.loads(APPROVALS.read_text()).get(check_id) is True
def launch(opp_id, check_id):
    """Spends credit. Requires TERAC_LIVE=1 and owner approval of this exact check id."""
    if not LIVE: return {"launched": False, "reason": "TERAC_LIVE!=1"}
    if not _approved(check_id): return {"launched": False, "reason": f"check {check_id} not approved in data/terac_approvals.json"}
    return _req("POST", f"/opportunities/{opp_id}/launch", {})

# ---------------------------------------------------------------------------------------------
# Evidence-review opportunities. Terac cannot book live calls or reach a named owner/buyer, so WE run the
# consented call (rollupops.review), and Terac reviewers open our token-gated reviewer page and submit a
# verdict there. review_type=manual_review => a reviewer is paid ONLY after we approve their submission.
from rollupops import review as _review
QUOTES = {"owner_verification": "lr93jf2jqea9luyzr1haw3oh", "buyer_screening": "kq09ob6qhi2ruiji24nyefnh"}
REVIEW_MINUTES = int(os.environ.get("TERAC_REVIEW_MINUTES", "15"))
BACKGROUNDS = ["M&A advisory or investment banking", "Private equity", "Business brokerage", "AML / KYC compliance", "Identity verification / fraud"]
def opportunity_draft(kind, check_id, feasibility_request_id=None, project_id=None):
    """Pure function: the draft payload (nothing sent). Task = interview on our hosted reviewer page."""
    assert kind in _review.KINDS
    label = "Owner verification" if kind == "owner_verification" else "Buyer screening"
    return {
        "title": f"Review a consented identity-and-intent call ({label})",
        "internal_title": f"RollupOps {kind} {check_id}",
        "description": ("Review redacted evidence from a short, consented identity-and-intent call we ran, then submit a verdict "
                        "(verified / concerns / fail) with reasons on our page. ~15 min. Paid after we approve your review."),
        "project_id": project_id or os.environ.get("TERAC_PROJECT_ID", ""),
        "num_participants": 1, "business_type": "b2b", "customer_screening_review": "manual_review",
        "filters": [{"multi_select--country": {"$in": ["US"]}}],
        "screening_questions": [
            {"key": "bg", "pick": "any", "text": "Which of these have you worked in professionally for at least 2 years?",
             "answers": [{"text": b, "qualify_logic": "must_one_of"} for b in BACKGROUNDS] + [{"text": "None of these", "qualify_logic": "reject"}]},
            {"key": "conf", "pick": "boolean", "text": "Will you keep the reviewed material confidential and not try to identify or contact anyone in it?",
             "answers": [{"text": "Yes", "qualify_logic": "must"}, {"text": "No", "qualify_logic": "reject"}]}],
        "tasks": [{"sequence": 1, "task_type": "interview", "review_type": "manual_review", "duration_minutes": REVIEW_MINUTES,
                   "title": "Review evidence and submit verdict", "task_url": _review.reviewer_url(check_id),
                   "description": "Open the page, read the redacted consent, context and call notes, answer the questions and submit verified / concerns / fail with reasons."}],
        "expected_days_to_complete": 5,
        **({"feasibility_request_id": feasibility_request_id} if feasibility_request_id else {}),
    }
def create_review_draft(kind, check_id, use_quote=True):
    """Creates the DRAFT on Terac (free, but still gated): TERAC_LIVE=1 AND data/terac_approvals.json[check_id] is true.
    Launch stays a separate gated call (launch()). Never called by the orchestrator."""
    body = opportunity_draft(kind, check_id, QUOTES.get(kind) if use_quote else None)
    if not LIVE: return {"created": False, "reason": "TERAC_LIVE!=1", "draft": body}
    if not _approved(check_id): return {"created": False, "reason": f"check {check_id} not approved in data/terac_approvals.json", "draft": body}
    if not body["project_id"]: return {"created": False, "reason": "TERAC_PROJECT_ID not set", "draft": body}
    if body.get("feasibility_request_id") and get_feasibility(body["feasibility_request_id"]).get("status") != "RESPONDED":
        body.pop("feasibility_request_id")  # quote not priced yet -> Terac estimates; review price before launch
    return _req("POST", "/opportunities", body)
def approve_submission(submission_id, check_id):
    """Pays the reviewer. Only after WE accepted their verdict; same gate as launch."""
    if not LIVE or not _approved(check_id): return {"approved": False, "reason": "TERAC_LIVE!=1 or check not approved"}
    return _req("POST", f"/submissions/{submission_id}/approve", {})
