import pathlib, sys, pytest
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))
from rollupops import drafting as D
def test_no_key_returns_none(monkeypatch):
    monkeypatch.delenv("NEBIUS_API_KEY", raising=False); assert D.draft("x") is None
def test_banned_names_rejected():
    for b in ("RollupOps", "Skyline"): 
        with pytest.raises(ValueError): D.clean("hi " + b)
def test_marketing_drafts_clean():
    root = pathlib.Path(__file__).resolve().parent.parent / "marketing/content"
    for f in root.glob("*"):
        t = f.read_text().lower(); assert not any(b in t for b in D.BANNED), f
