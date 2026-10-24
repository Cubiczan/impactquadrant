"""Evidence-review flow for the two Terac human checks.
Terac cannot book live calls or reach a named person, so:
  1. WE run the consented identity-and-intent call (owner verification / flagged buyer screening).
  2. capture_consent() MUST be recorded before any recording or notes are stored.
  3. attach_evidence() stores the recording reference/notes + minimal context (local, untracked: data/reviews/).
  4. publish_bundle() writes a REDACTED bundle for the hosted reviewer page and returns a token-gated URL.
  5. Terac panel reviewers open that page and submit verified / concerns / fail + reasons (stored in private Vercel Blob).
  6. We approve the Terac submission (manual_review) only after we accept their work -> only then are they paid.
Redaction: partner names and NDA-gated fields never leave this machine."""
import os, re, json, hmac, hashlib, datetime as dt
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
LOCAL = ROOT / "data/reviews"                      # untracked: raw consent + evidence
BUNDLES = ROOT / "dashboard/review_evidence"       # redacted bundles shipped to the reviewer API (untracked except demo-*)
SECRET_FILE = ROOT / "data/review_secret"          # untracked; same value as Vercel env REVIEW_TOKEN_SECRET
BASE_URL = os.environ.get("REVIEW_BASE_URL", "https://dashboard-six-fawn-83.vercel.app")
KINDS = ("owner_verification", "buyer_screening")
VERDICTS = ("verified", "concerns", "fail")
CONSENT_SCRIPT = ("This call is with Impact Quadrant. With your permission we will record it (or take notes) so that one "
                  "independent reviewer can confirm your identity and intent. Only a redacted summary is shared; you can "
                  "stop at any time and ask us to delete the recording. Do you consent?")
# Never shipped to reviewers. Extra private terms come from env RU_BLOCKED_TERMS (comma-separated) or data/raw/private/blocked_terms.txt.
_BUILTIN = ["alp" + "ine", "sky" + "line", "imp" + "erial"]
NDA_FIELDS = {"partner", "partners", "sponsor", "backer", "buyer_firm_confidential", "deal_terms", "price", "ebitda_exact",
              "address", "street", "phone", "email", "ssn", "tax_id", "bank", "nda", "cim", "loi", "financials"}
def _blocked():
    t = list(_BUILTIN) + [x.strip() for x in os.environ.get("RU_BLOCKED_TERMS", "").split(",") if x.strip()]
    f = ROOT / "data/raw/private/blocked_terms.txt"
    if f.exists(): t += [x.strip() for x in f.read_text().splitlines() if x.strip()]
    return t
def redact_text(s):
    s = str(s)
    for t in _blocked(): s = re.sub(re.escape(t), "[redacted]", s, flags=re.I)
    s = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "[email]", s)
    s = re.sub(r"\+?\d[\d\s().-]{8,}\d", "[phone]", s)
    return s
def redact(obj):
    if isinstance(obj, dict): return {k: redact(v) for k, v in obj.items() if k.lower() not in NDA_FIELDS}
    if isinstance(obj, list): return [redact(v) for v in obj]
    return redact_text(obj) if isinstance(obj, str) else obj
def _secret():
    s = os.environ.get("REVIEW_TOKEN_SECRET") or (SECRET_FILE.read_text().strip() if SECRET_FILE.exists() else "")
    if not s: raise RuntimeError("REVIEW_TOKEN_SECRET not set (data/review_secret)")
    return s.encode()
def token(check_id): return hmac.new(_secret(), check_id.encode(), hashlib.sha256).hexdigest()[:32]
def reviewer_url(check_id): return f"{BASE_URL}/review.html?c={check_id}&t={token(check_id)}"
def _dir(check_id):
    if not re.fullmatch(r"[a-z0-9-]{3,64}", check_id): raise ValueError("check_id must be [a-z0-9-]")
    d = LOCAL / check_id; d.mkdir(parents=True, exist_ok=True); return d
def capture_consent(check_id, kind, subject_ref, consented, method="verbal-on-call", recorded=True, captured_by="Impact Quadrant"):
    """Step 1, BEFORE recording. Read CONSENT_SCRIPT aloud; record the answer. No consent -> nothing is recorded."""
    assert kind in KINDS
    rec = {"check_id": check_id, "kind": kind, "subject_ref": subject_ref, "consented": bool(consented), "recording_allowed": bool(consented and recorded),
           "method": method, "script": CONSENT_SCRIPT, "captured_by": captured_by, "at": dt.datetime.now().isoformat(timespec="seconds")}
    (_dir(check_id) / "consent.json").write_text(json.dumps(rec, indent=1)); return rec
def consent(check_id):
    f = LOCAL / check_id / "consent.json"
    return json.loads(f.read_text()) if f.exists() else None
def attach_evidence(check_id, notes, context=None, recording_path=None, transcript=None):
    c = consent(check_id)
    if not c or not c["consented"]: raise PermissionError("no consent on file: run capture_consent() first; nothing stored")
    if recording_path and not c["recording_allowed"]: raise PermissionError("subject did not allow recording; store notes only")
    ev = {"notes": notes, "transcript": transcript, "context": context or {}, "recording_path": str(recording_path) if recording_path else None,
          "at": dt.datetime.now().isoformat(timespec="seconds")}
    (_dir(check_id) / "evidence.json").write_text(json.dumps(ev, indent=1)); return ev
QUESTIONS = {
    "owner_verification": ["Does the person credibly present as an owner or authorized seller of the described business?",
                           "Is the business plausibly operating as described (sector, size band, region)?",
                           "Is the stated intent to sell or value the business genuine and consistent?"],
    "buyer_screening": ["Does the stated identity match the firm evidence provided (firm site, domain, public profile)?",
                        "Are funds / capacity plausible for the deal size band?",
                        "Is acquisition intent genuine (no data harvesting, competitor fishing or identity mismatch)?"]}
def publish_bundle(check_id):
    """Writes the redacted reviewer bundle; returns the token-gated reviewer URL. Requires consent + evidence."""
    c = consent(check_id); e = LOCAL / check_id / "evidence.json"
    if not c or not c["consented"] or not e.exists(): raise PermissionError("consent and evidence required before publishing")
    ev = json.loads(e.read_text())
    b = {"check_id": check_id, "kind": c["kind"], "consent": {"given": True, "method": c["method"], "at": c["at"], "recording_allowed": c["recording_allowed"]},
         "context": redact(ev.get("context") or {}), "notes": redact_text(ev.get("notes") or ""),
         "transcript": redact_text(ev["transcript"]) if ev.get("transcript") else None,
         "recording": "Recording held by Impact Quadrant; summary/transcript shown here." if ev.get("recording_path") else None,
         "questions": QUESTIONS[c["kind"]], "verdicts": list(VERDICTS)}
    blob = json.dumps(b).lower()
    assert not any(t.lower() in blob for t in _blocked()), "blocked term survived redaction"
    BUNDLES.mkdir(parents=True, exist_ok=True); (BUNDLES / f"{check_id}.json").write_text(json.dumps(b, indent=1))
    return reviewer_url(check_id)
