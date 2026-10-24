"""Terac human-in-the-loop: EXACTLY ONE place. Everything else is fully automated.
  owner_verification - blue-collar business owner check, with consent, non-blocking, before a listing/teaser goes out.
NO buyer review of any kind: PE fund buyers are vetted personally by the owner (Shyam), never by Terac or any
automated review; there is no buyer screening code path.
NOT used for: buyers (any segment),  teasers, subscriptions, scoring, matching, marketing, checkout, service fulfillment
(fulfillment keeps the owner's own approval, not Terac).
Gated by TERAC_ENABLED=1 (queue) and TERAC_LIVE=1 + per-check owner approval (spend). Flag off -> item queued as pending_human; low-value paths never block."""
import os, json, datetime as dt
from pathlib import Path
ENABLED = os.environ.get("TERAC_ENABLED") == "1"
MCP = "https://terac.com/api/mcp"; CAP = 5
ROOT = Path(__file__).resolve().parent.parent
QUEUE = ROOT / "dashboard/public/data/human_checks.json"
BADGE = {"verified": "Verified by human (Terac)", "flagged": "Flagged", "pending": "Human verification pending",
         "pending_human": "Queued for human check (Terac off)"}
_used = {"owner_verification": 0}
_queue = {"owner_verification": []}
SCRIPTS = {"owner_verification": "Disclosed: caller works with Impact Quadrant. Consent first; no recording without consent. Confirm the business operates at the stated location, the speaker is an owner, and genuine interest in a confidential valuation/sale. Flag anything inconsistent."}
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
def flush():
    out = {"enabled": ENABLED, **_queue,
           "rules": {"owner_verification": "with consent, non-blocking, before a listing/teaser goes out",
                     "buyers": "never reviewed; PE fund buyers are vetted personally by the owner"}}
    QUEUE.parent.mkdir(parents=True, exist_ok=True); QUEUE.write_text(json.dumps(out, indent=1)); return out
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
# Evidence-review opportunities. Terac cannot book live calls or reach a named owner, so WE run the
# consented call (rollupops.review), and Terac reviewers open our token-gated reviewer page and submit a
# verdict there. review_type=manual_review => a reviewer is paid ONLY after we approve their submission.
from rollupops import review as _review
QUOTES = {"owner_verification": os.environ.get("TERAC_OWNER_QUOTE_ID", "mwz702ig9hff9q14w388nkni")}  # review-only quote (Oct 24); old call-style quote lr93jf2jqea9luyzr1haw3oh superseded
REVIEW_MINUTES = int(os.environ.get("TERAC_REVIEW_MINUTES", "15"))
BACKGROUNDS = ["M&A advisory or investment banking", "Private equity", "Business brokerage", "AML / KYC compliance", "Identity verification / fraud"]
def opportunity_draft(kind, check_id, feasibility_request_id=None, project_id=None):
    """Pure function: the draft payload (nothing sent). Task = interview on our hosted reviewer page."""
    assert kind in _review.KINDS
    label = "Owner verification"
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
