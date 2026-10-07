"""Check frozen update evidence, coverage and embedded report data; no network."""
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
m = json.loads((ROOT / "data/verified/update_manifest.json").read_text())
for name, digest in m["sha256"].items():
    assert hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest, name
v = pd.read_csv(ROOT / "data/verified/ipo_cohort_verified.csv")
b = pd.read_csv(ROOT / "data/verified/size_and_benchmark.csv")
r = pd.read_csv(ROOT / "data/verified/post_listing_returns.csv")
e = json.loads((ROOT / m["snapshot"] / "additions.json").read_text())
assert len(e) == m["additions_count"]
assert len({x["isin"] for x in e}) == len(e)
new_ids = {x["issue_id"] for x in e}
assert new_ids <= set(v.issue_id)
assert not new_ids & set(b.issue_id), "New IPOs must not have invented benchmark/size data"
assert not new_ids & set(r.issue_id), "New IPOs postdate the post-listing cutoff"
d = json.loads((ROOT / "data/verified/report_data.json").read_text())
assert d["coverage"]["listing"] == len(v) == m["count"]
assert d["coverage"]["benchmark"] == len(b)
assert d["coverage"]["post_listing_ipos"] == r.issue_id.nunique()
assert len(d["ipos"]) == len(v)
for board, tag in [("Main Board", "main"), ("SME Board", "sme")]:
    g = v[v.board_type == board]
    assert d["listing_overall"][tag]["median"] == round(g.return_pct.median(), 1)
    assert sum(d["counts"][tag]) == len(g)
    assert sum(x["n"] for x in d["hist"][tag]) == len(g)
    for x in d["listing"][tag]:
        h = g[g.listing_year == x["year"]]
        assert x["n"] == len(h)
        assert x["above"] == round(h.return_pct.gt(0).mean() * 100, 1)
html = (ROOT / "report/ipo-performance.html").read_text()
embedded = re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S)
assert json.loads(embedded[1]) == d
assert "__DATA__" not in html
print(f"PASS: {len(m['sha256'])} source/data hashes; {len(e)} additions; totals, distributions, coverage and embedded report agree.")
