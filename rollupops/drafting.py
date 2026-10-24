"""Optional cheap drafting client (Nebius AI Studio, OpenAI-compatible). Drafts only; never posts or sends.
Needs NEBIUS_API_KEY (via the secure input box). Without it, draft() returns None and callers fall back to templates."""
import os
BASE = os.environ.get("NEBIUS_BASE_URL", "https://api.studio.nebius.com/v1")
MODEL = os.environ.get("NEBIUS_MODEL", "meta-llama/Meta-Llama-3.1-8B-Instruct")
BANNED = ("rollupops", "alpine investors", "skyline", "imperial capital")
SYSTEM = ("You draft marketing copy for ImpactQuadrant (one word). Plain, specific, no hype, no guarantees, "
          "no client or partner names. Output a draft for human review.")
def available(): return bool(os.environ.get("NEBIUS_API_KEY"))
def clean(text):
    low = (text or "").lower()
    if any(b in low for b in BANNED): raise ValueError("draft contains a banned name; discard")
    return text
def draft(prompt, max_tokens=600, http=None):
    if not available(): return None
    import requests; http = http or requests
    r = http.post(BASE + "/chat/completions", headers={"Authorization": "Bearer " + os.environ["NEBIUS_API_KEY"]},
                  json={"model": MODEL, "max_tokens": max_tokens, "temperature": 0.6,
                        "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}, timeout=60)
    r.raise_for_status()
    return clean(r.json()["choices"][0]["message"]["content"])
