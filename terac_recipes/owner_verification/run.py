"""ImpactQuadrant owner-verification Terac recipe runner. Replay is free; launch needs --confirm and human approval."""
import json, os, sys, urllib.request
from pathlib import Path
HERE = Path(__file__).parent
BASE = "https://terac.com/api/external/v2"

def _req(method, path, body=None):
    key = os.environ.get("TERAC_API_KEY")
    if not key: sys.exit("TERAC_API_KEY not set")
    r = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(r, timeout=60))

def validate(result):
    assert result["verdict"] in ("verified", "concerns", "fail") and result["reasons"] and isinstance(result["red_flags"], list)
    return result

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "replay"
    if cmd == "replay":
        print(json.dumps(validate(json.loads((HERE/"replay_result.json").read_text())), indent=2))
    elif cmd == "draft":
        spec = json.loads((HERE/"study.json").read_text()); spec.pop("_note")
        spec["project_id"] = os.environ.get("TERAC_PROJECT_ID", "idiu4cu84mqd8quklfehcig9")
        o = _req("POST", "/opportunities", spec); print(o["id"], o["pricing"])
    elif cmd == "launch":
        if "--confirm" not in sys.argv or os.environ.get("TERAC_LIVE") != "1": sys.exit("refusing: needs TERAC_LIVE=1 and --confirm (human-approved)")
        print(_req("POST", f"/opportunities/{sys.argv[-1]}/launch", {}))
