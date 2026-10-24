"""Inline the latest free teardown into wix/pages/free-teardown.js -> wix/build/free-teardown.js"""
import json, pathlib
r = pathlib.Path(__file__).resolve().parent.parent; (r/"wix/build").mkdir(exist_ok=True)
src = (r/"wix/pages/free-teardown.js").read_text().replace("__FREE_TEARDOWN__", (r/"out/07_free_teardown.json").read_text())
(r/"wix/build/free-teardown.js").write_text(src); print("wrote wix/build/free-teardown.js")
