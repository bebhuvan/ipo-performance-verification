"""Append identity-checked IPOs from frozen official issue feeds and bhavcopies.

Usage: python3 scripts/update_listings.py --snapshot data/inputs/updates/2026-10-07
Listing-only update: post-listing returns, size and benchmarks retain their old cutoff.
"""
import argparse
import hashlib
import json
import re
import sys
from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "verify"))
import _bhav


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--snapshot", type=Path, required=True)
    args = ap.parse_args()
    snapshot = args.snapshot.resolve()
    meta = json.loads((snapshot / "sources.json").read_text())
    start, end = meta["previous_listing_cutoff"], meta["listing_as_of"]
    # Read only frozen downloads so a rerun does not silently change source evidence.
    _bhav.CACHE = snapshot / "bhavcopies"
    for filename in meta["bhavcopy_urls"]:
        assert (_bhav.CACHE / filename).is_file(), f"Missing frozen source: {filename}"
    nfeed = json.loads((snapshot / "nse_past_issues.json").read_text())
    candidates = {}
    for r in nfeed:
        if r.get("securityType") not in {"EQ", "BE", "SME"}:
            continue
        try:
            ds = datetime.strptime(r["listingDate"], "%d-%b-%Y").date().isoformat()
        except (ValueError, KeyError):
            continue
        if not start < ds <= end:
            continue
        hits = [x for x in _bhav.nse(date.fromisoformat(ds))
                if x["symbol"] == r["symbol"] and x["series"] in {"EQ", "BE", "SM", "ST"}]
        assert len(hits) == 1, (ds, r, hits)
        hit = hits[0]
        price = float(r["issuePrice"].strip())
        assert hit["prev_close"] == price, (r, hit)
        candidates[(ds, hit["isin"])] = dict(name=r["company"], price=price, n=hit,
            close_date=datetime.strptime(r["ipoEndDate"], "%d-%b-%Y").date().isoformat(),
            source="NSE public-past-issues", feed_note=("Final issue price differs from displayed price band; retained explicit final issuePrice, corroborated by NSE previous close and BSE IssuePrice."
                if (re.findall(r"[0-9]+(?:\.[0-9]+)?", r.get("priceRange", "")) and price > float(re.findall(r"[0-9]+(?:\.[0-9]+)?", r["priceRange"])[-1])) else ""))
    for flag in (1, 2):
        for r in json.loads((snapshot / f"bse_performance_{flag}.json").read_text())["Table"]:
            ds = r["ListedOn"][:10]
            if not start < ds <= end:
                continue
            code = r["IMAGE"].rstrip("/").split("/")[-1]
            hits = [x for x in _bhav.bse(date.fromisoformat(ds)) if x["code"] == code]
            assert len(hits) == 1, (r, hits)
            hit = hits[0]
            assert hit["prev_close"] == 0 and hit["close"] == r["ListingDayClose"], (r, hit)
            key = (ds, hit["isin"])
            if key in candidates:
                assert candidates[key]["price"] == float(r["IssuePrice"]), r
                candidates[key]["b"] = hit
            else:
                candidates[key] = dict(name=r["CompanyName"], price=float(r["IssuePrice"]),
                    b=hit, close_date=None, source="BSE MoreCompanyN IPO performance", feed_note="")
            assert (flag == 2) == (hit["series"] in {"M", "MT", "TS", "MS"}), r
    Vpath = ROOT / "data/verified/ipo_cohort_verified.csv"
    V = pd.read_csv(Vpath)
    Dpath = ROOT / "data/verified/verification_detail.csv"
    D = pd.read_csv(Dpath, dtype=str)
    new, detail, evidence = [], [], []
    for (ds, isin), r in sorted(candidates.items()):
        iid = f"ipo-{ds}-{isin.lower()}"
        if iid in set(V.issue_id):
            continue
        n, b = r.get("n"), r.get("b")
        own = n or b
        board = "SME Board" if own["series"] in {"SM", "ST", "M", "MT", "TS", "MS"} else "Main Board"
        bps = int(((Decimal(str(own["close"])) / Decimal(str(r["price"])) - 1) * 10000).quantize(Decimal(1), ROUND_HALF_UP))
        row = dict(issue_id=iid, company_name=r["name"], board_type=board, listing_date=ds,
            listing_year=int(ds[:4]), issue_price_inr=r["price"], venue="NSE + BSE" if n and b else "NSE only" if n else "BSE only",
            price_exchange=own["exchange"], listing_open_inr=own["open"], listing_close_inr=own["close"],
            return_bps=bps, return_pct=bps / 100, close_basis="official listing-day bhavcopy; identity matched by ISIN / scrip code",
            codex_status="new listing after original export", kite_check="not checked in listing-only update",
            note=r["feed_note"] or "Added from frozen official exchange issue feed; post-listing / size / benchmarks pending refresh.")
        dr = dict(issue_id=iid, company_name=r["name"], board_type=board, listing_date=ds, issue_price_inr=r["price"])
        for ex, x in (("nse", n), ("bse", b)):
            if x:
                row.update({f"{ex}_symbol": x["symbol"] if ex == "nse" else x["code"], f"{ex}_series": x["series"], f"{ex}_close": x["close"]})
                dr.update({f"{ex}_{k}": x[k] for k in ("isin", "symbol", "series", "open", "close")})
                if ex == "bse":
                    dr["bse_symbol"] = x["code"]
                dr[f"{ex}_prev"] = x["prev_close"]
                dr[f"{ex}_how"] = "exact identity match to official issue feed"
        new.append(row)
        detail.append(dr)
        evidence.append(dict(issue_id=iid, isin=isin, listing_date=ds, issue_price_source=r["source"],
            offer_close_date=r["close_date"], nse=n, bse=b, feed_note=r["feed_note"]))
    if new:
        pd.concat([V, pd.DataFrame(new).reindex(columns=V.columns)], ignore_index=True).to_csv(Vpath, index=False)
        pd.concat([D, pd.DataFrame(detail).reindex(columns=D.columns)], ignore_index=True).to_csv(Dpath, index=False)
        (snapshot / "additions.json").write_text(json.dumps(evidence, indent=2) + "\n")
    V = pd.read_csv(Vpath)
    # Preserve the original comparison columns, which refer to the frozen Codex export.
    sp = ROOT / "data/summaries/summary_by_year_board.csv"
    old = pd.read_csv(sp)
    rows = []
    for (board, year), g in V.groupby(["board_type", "listing_year"]):
        s = g.return_pct
        rows.append(dict(board_type=board, listing_year=year, n=len(s), **{"median_%":round(s.median(),2),
            "above_issue_%":round(s.gt(0).mean()*100,1), "flat_%":round(s.eq(0).mean()*100,1),
            "below_%":round(s.lt(0).mean()*100,1), "p25":round(s.quantile(.25),1), "p75":round(s.quantile(.75),1)}))
    pd.DataFrame(rows).merge(old[["board_type","listing_year","n_codex","median_%_codex","above_issue_%_codex"]], on=["board_type","listing_year"]).to_csv(sp,index=False)
    manifest = dict(listing_as_of=end, post_listing_as_of="2026-09-28", benchmark_as_of="2026-09-28",
        size_cohort_cutoff="2026-09-28", count=len(V), counts_by_board=V.board_type.value_counts().to_dict(),
        additions_count=len(candidates), snapshot=str(snapshot.relative_to(ROOT)),
        limitations="Listing-only update. New IPOs have no post-listing, market-adjusted return or size classification in this snapshot. Universe completeness is not certified.")
    paths = [Vpath, Dpath, sp] + list(snapshot.glob("*.json")) + list((snapshot / "bhavcopies").glob("*"))
    manifest["sha256"] = {str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}
    (ROOT / "data/verified/update_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({k:v for k,v in manifest.items() if k != "sha256"},indent=2))


if __name__ == "__main__":
    main()
