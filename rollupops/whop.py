"""Minimal Whop REST client. SANDBOX ONLY unless WHOP_LIVE=1 AND NEEDS_SHYAM_APPROVED=1."""
import os, json, urllib.request, urllib.error
LIVE = os.environ.get("WHOP_LIVE") == "1" and os.environ.get("NEEDS_SHYAM_APPROVED") == "1"
PROD_BIZ = "biz_hBjAsGrR4pbWup"  # production business (Cubiczan)
BIZ = os.environ.get("WHOP_COMPANY_ID", PROD_BIZ if LIVE else "biz_a5nrqqjxL9lLAv")
BASE = "https://api.whop.com/api/v1" if LIVE else "https://sandbox-api.whop.com/api/v1"

def call(method, path, body=None):
    key = os.environ["WHOP_PROD_API_KEY" if LIVE else "WHOP_API_KEY"]
    req = urllib.request.Request(BASE + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return {"error": e.code, "body": e.read().decode()[:800]}

def create_product(title, description, plan_type, price, renewal=None, period=None, metadata=None):
    po = {"plan_type": plan_type, "base_currency": "usd", "initial_price": price}
    if renewal is not None: po.update(renewal_price=renewal, billing_period=period, initial_price=0)
    return call("POST", "/products", {"account_id": BIZ, "title": title, "description": description,
        "plan_options": po, "metadata": metadata or {}})

def checkout(plan_id=None, plan=None, metadata=None, redirect_url=None):
    b = {"mode": "payment", "metadata": metadata or {}}
    if plan_id: b["plan_id"] = plan_id
    if plan: b["plan"] = plan
    if redirect_url: b["redirect_url"] = redirect_url
    return call("POST", "/checkout_configurations", b)
