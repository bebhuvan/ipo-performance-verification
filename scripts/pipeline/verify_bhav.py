"""Independent check of every IPO's listing-day close against official NSE/BSE bhavcopies.

Reads the de-duplicated universe (universe_dedup.csv) plus the WIP workbook pairing
(pairs_U_B.csv) for extra identifiers. Downloads each listing date's NSE and BSE
bhavcopy (cached under bhav/), locates the IPO's row by ISIN, symbol, or the
new-listing anchor (NSE prev close == issue price; BSE prev close == 0), and records
the official open/close on each exchange. Writes bhav_verification.csv.
"""
import csv, io, re, sys, time, zipfile, difflib
from datetime import date
from pathlib import Path
import pandas as pd
import requests

S = Path(__file__).parent
CACHE = S / "bhav" / "cache"; CACHE.mkdir(parents=True, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
      "Referer": "https://www.bseindia.com/"}
http = requests.Session(); http.headers.update(UA)
MON = ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]


def get(url: str, name: str) -> bytes | None:
    p = CACHE / name
    if p.exists():
        return p.read_bytes() or None
    for attempt in range(3):
        try:
            r = http.get(url, timeout=40)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1)); continue
        time.sleep(0.4)
        if r.status_code == 200 and len(r.content) > 500 and not r.content[:15].lower().startswith(b"<!doctype"):
            p.write_bytes(r.content); return r.content
        if r.status_code == 404:
            break
        time.sleep(2 * (attempt + 1))
    p.write_bytes(b"")  # negative cache
    return None


def unzip(b: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(b)); return z.read(z.namelist()[0]).decode("latin-1")


def f(x):
    try: return round(float(str(x).strip()), 2)
    except ValueError: return None


NEW_FMT = date(2024, 7, 8)


def nse_rows(d: date):
    b = d >= NEW_FMT and get(f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip", f"nse_u_{d:%Y%m%d}.zip")
    if b:
        for r in csv.DictReader(io.StringIO(unzip(b))):
            yield dict(ex="NSE", sym=(r.get("TckrSymb") or "").strip(), ser=(r.get("SctySrs") or "").strip(), isin=(r.get("ISIN") or "").strip(), name=r.get("FinInstrmNm", ""),
                       open=f(r["OpnPric"]), close=f(r["ClsPric"]), prev=f(r["PrvsClsgPric"]))
        return
    b = get(f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{MON[d.month-1]}/cm{d:%d}{MON[d.month-1]}{d.year}bhav.csv.zip",
            f"nse_o_{d:%Y%m%d}.zip")
    if b:
        for r in csv.DictReader(io.StringIO(unzip(b))):
            r = {k.strip(): v for k, v in r.items() if k}
            yield dict(ex="NSE", sym=(r.get("SYMBOL") or "").strip(), ser=(r.get("SERIES") or "").strip(), isin=(r.get("ISIN") or "").strip(), name="",
                       open=f(r["OPEN"]), close=f(r["CLOSE"]), prev=f(r["PREVCLOSE"]))


def bse_rows(d: date):
    b = d >= NEW_FMT and get(f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d:%Y%m%d}_F_0000.CSV", f"bse_n_{d:%Y%m%d}.csv")
    if b:
        for r in csv.DictReader(io.StringIO(b.decode("latin-1"))):
            yield dict(ex="BSE", sym=(r.get("TckrSymb") or "").strip(), code=(r.get("FinInstrmId") or "").strip(), ser=(r.get("SctySrs") or "").strip(), isin=(r.get("ISIN") or "").strip(),
                       name=r["FinInstrmNm"], open=f(r["OpnPric"]), close=f(r["ClsPric"]), prev=f(r["PrvsClsgPric"]))
        return
    b = get(f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{d:%d%m%y}.zip", f"bse_o_{d:%Y%m%d}.zip")
    if b:
        for r in csv.DictReader(io.StringIO(unzip(b))):
            yield dict(ex="BSE", sym="", code=(r.get("SC_CODE") or "").strip(), ser=(r.get("SC_GROUP") or "").strip(), isin=(r.get("ISIN_CODE") or "").strip(), name=r["SC_NAME"],
                       open=f(r["OPEN"]), close=f(r["CLOSE"]), prev=f(r["PREVCLOSE"]))


def norm(s):
    s = str(s).lower().replace("&", "and")
    s = re.sub(r"\b(limited|ltd|the|india|pvt|private)\b", "", s)
    return re.sub(r"[^a-z0-9]", "", s)


def pick(rows, ipo):
    """Return (row, method) for this IPO within one exchange's rows, or (None, reason)."""
    ip = ipo["issue_price"]
    by_isin = [r for r in rows if r["isin"] and r["isin"] in ipo["isins"]]
    new = [r for r in rows if (r["ex"] == "NSE" and r["prev"] == ip) or (r["ex"] == "BSE" and r["prev"] in (0.0, ip))]
    if len(by_isin) == 1:
        return by_isin[0], "isin"
    by_sym = [r for r in rows if (r["sym"] and r["sym"] in ipo["syms"]) or (r.get("code") and r["code"] in ipo["codes"])]
    by_sym = [r for r in by_sym if r in new] or by_sym
    if len(by_sym) == 1:
        return by_sym[0], "symbol"
    named = [r for r in new if r["name"] and difflib.SequenceMatcher(None, norm(r["name"]), ipo["nk"]).ratio() >= 0.6]
    if len(named) == 1:
        return named[0], "new-listing+name"
    if ipo["ex_hint"] in (r["ex"] for r in new):
        cands = [r for r in new if r["ex"] == "NSE" and r["prev"] == ip]
        if len(cands) == 1:
            return cands[0], "new-listing anchor (prev close = issue price)"
    return None, f"no unique row (isin:{len(by_isin)} sym:{len(by_sym)} new:{len(new)})"


def main():
    U = pd.read_csv(S / "universe_dedup.csv", dtype=str)
    P = pd.read_csv(S / "pairs_U_B.csv", dtype=str)
    extra = P.drop_duplicates("issue_id").set_index("issue_id").to_dict("index")
    out = []
    dates = sorted(U.listing_date.unique())
    for i, ds in enumerate(dates):
        d = date.fromisoformat(ds)
        nse, bse = list(nse_rows(d)), list(bse_rows(d))
        for ipo in U[U.listing_date == ds].to_dict("records"):
            e = extra.get(ipo["issue_id"], {})
            ok = lambda x: isinstance(x, str) and x and x != "nan"
            isins = {x for x in [ipo.get("isin"), e.get("ISIN")] if ok(x) and x.startswith("IN")}
            syms = {x for x in [ipo.get("symbol"), e.get("Trading Symbol")] if ok(x) and not x.isdigit()}
            codes = {e["BSE Scrip Code"].split(".")[0]} if ok(e.get("BSE Scrip Code")) else set()
            src = str(ipo.get("listing_price_source") or "")
            info = dict(issue_price=round(int(ipo["issue_price_paise"]) / 100, 2), isins=isins, syms=syms, codes=codes,
                        nk=norm(ipo["company_name"]), ex_hint="BSE" if src.startswith("bse") else "NSE")
            row = dict(issue_id=ipo["issue_id"], company_name=ipo["company_name"], board_type=ipo["board_type"],
                       listing_date=ds, issue_price_inr=info["issue_price"],
                       codex_close=f(ipo["listing_close_inr"]) if ipo.get("listing_close_inr") else None,
                       codex_source=src, nse_file=bool(nse), bse_file=bool(bse))
            for ex, rows in (("nse", nse), ("bse", bse)):
                r, how = pick(rows, info) if rows else (None, "file unavailable")
                row[f"{ex}_how"] = how
                if r:
                    row.update({f"{ex}_symbol": r["sym"] or r.get("code"), f"{ex}_isin": r["isin"], f"{ex}_series": r["ser"],
                                f"{ex}_prev": r["prev"], f"{ex}_open": r["open"], f"{ex}_close": r["close"]})
            out.append(row)
        if i % 25 == 0:
            print(f"{i+1}/{len(dates)} {ds}", flush=True)
    pd.DataFrame(out).to_csv(S / "bhav_verification.csv", index=False)
    print("done", len(out))


if __name__ == "__main__":
    main()
