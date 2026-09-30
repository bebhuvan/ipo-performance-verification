"""Minimal readers for official NSE and BSE equity bhavcopies (end-of-day price files).

Formats change on 8 July 2024 for both exchanges:
  NSE old  : nsearchives.nseindia.com/content/historical/EQUITIES/YYYY/MON/cmDDMONYYYYbhav.csv.zip
  NSE UDiFF: nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_YYYYMMDD_F_0000.csv.zip
  BSE old  : www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_DDMMYY.zip
  BSE new  : www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_YYYYMMDD_F_0000.CSV
Files are cached under verify/.cache/. Each row is returned as a dict with
exchange, symbol, code (BSE scrip code), series, isin, open, close, prev_close.
"""
from __future__ import annotations

import csv
import io
import time
import zipfile
from datetime import date
from pathlib import Path

import requests

CACHE = Path(__file__).parent / ".cache"
CACHE.mkdir(exist_ok=True)
NEW_FORMAT = date(2024, 7, 8)
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/128 Safari/537.36",
                        "Referer": "https://www.bseindia.com/"})


def _get(url: str, name: str) -> bytes | None:
    path = CACHE / name
    if path.exists():
        return path.read_bytes() or None
    for attempt in range(3):
        try:
            r = SESSION.get(url, timeout=40)
        except requests.RequestException:
            time.sleep(2 * (attempt + 1))
            continue
        time.sleep(0.4)
        if r.status_code == 200 and len(r.content) > 500 and not r.content[:15].lower().startswith(b"<!doctype"):
            path.write_bytes(r.content)
            return r.content
        if r.status_code == 404:
            break
        time.sleep(2 * (attempt + 1))
    return None


def _unzip(b: bytes) -> str:
    z = zipfile.ZipFile(io.BytesIO(b))
    return z.read(z.namelist()[0]).decode("latin-1")


def _f(x):
    try:
        return round(float(str(x).strip()), 2)
    except ValueError:
        return None


def _g(row, key):
    return (row.get(key) or "").strip()


def nse(d: date) -> list[dict]:
    if d >= NEW_FORMAT:
        b = _get(f"https://nsearchives.nseindia.com/content/cm/BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip", f"nse_{d:%Y%m%d}.zip")
        if not b:
            return []
        return [dict(exchange="NSE", symbol=_g(r, "TckrSymb"), code="", series=_g(r, "SctySrs"), isin=_g(r, "ISIN"),
                     open=_f(r["OpnPric"]), close=_f(r["ClsPric"]), prev_close=_f(r["PrvsClsgPric"]))
                for r in csv.DictReader(io.StringIO(_unzip(b)))]
    m = MONTHS[d.month - 1]
    b = _get(f"https://nsearchives.nseindia.com/content/historical/EQUITIES/{d.year}/{m}/cm{d:%d}{m}{d.year}bhav.csv.zip", f"nse_{d:%Y%m%d}.zip")
    if not b:
        return []
    out = []
    for r in csv.DictReader(io.StringIO(_unzip(b))):
        r = {k.strip(): v for k, v in r.items() if k}
        out.append(dict(exchange="NSE", symbol=_g(r, "SYMBOL"), code="", series=_g(r, "SERIES"), isin=_g(r, "ISIN"),
                        open=_f(r["OPEN"]), close=_f(r["CLOSE"]), prev_close=_f(r["PREVCLOSE"])))
    return out


def bse(d: date) -> list[dict]:
    if d >= NEW_FORMAT:
        b = _get(f"https://www.bseindia.com/download/BhavCopy/Equity/BhavCopy_BSE_CM_0_0_0_{d:%Y%m%d}_F_0000.CSV", f"bse_{d:%Y%m%d}.csv")
        if not b:
            return []
        return [dict(exchange="BSE", symbol=_g(r, "TckrSymb"), code=_g(r, "FinInstrmId"), series=_g(r, "SctySrs"), isin=_g(r, "ISIN"),
                     open=_f(r["OpnPric"]), close=_f(r["ClsPric"]), prev_close=_f(r["PrvsClsgPric"]))
                for r in csv.DictReader(io.StringIO(b.decode("latin-1")))]
    b = _get(f"https://www.bseindia.com/download/BhavCopy/Equity/EQ_ISINCODE_{d:%d%m%y}.zip", f"bse_{d:%Y%m%d}.zip")
    if not b:
        return []
    return [dict(exchange="BSE", symbol="", code=_g(r, "SC_CODE"), series=_g(r, "SC_GROUP"), isin=_g(r, "ISIN_CODE"),
                 open=_f(r["OPEN"]), close=_f(r["CLOSE"]), prev_close=_f(r["PREVCLOSE"]))
            for r in csv.DictReader(io.StringIO(_unzip(b)))]
