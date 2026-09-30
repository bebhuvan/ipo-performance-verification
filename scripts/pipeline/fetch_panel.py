"""Build a daily raw price panel (NSE + BSE) for 2020-01-01..2026-09-28 from official bhavcopies.
NSE 2022-06-01..2026-09-17 comes from the data bank's nse_bhavcopy; everything else is downloaded
(and cached) using the same readers as verify_bhav.py. Output: panel/{nse,bse}_YYYY.parquet
Columns: date, ex, symbol, code, series, isin, open, close, prev, volume. Equity + SME series only.
"""
import glob, sys, time
from datetime import date
from pathlib import Path
import duckdb, pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import verify_bhav as vb   # nse_rows / bse_rows with caching + format switch

S = Path(__file__).parent; OUT = S / "panel"; OUT.mkdir(exist_ok=True)
DB = "<DATA_BANK>/"
con = duckdb.connect()
fs = glob.glob(DB + "data/warehouse/source_native/nifty_index_history/*.parquet")
cal = [d for d in con.execute(f"select distinct date from read_parquet({fs!r},union_by_name=true) where index_name='Nifty 500' and date between '2020-01-01' and '2026-09-28' order by 1").df().date.astype(str)]
nb = glob.glob(DB + "data/warehouse/source_native/nse_bhavcopy/**/*.parquet", recursive=True)
have_nse = set(con.execute(f"select distinct trade_date from read_parquet({nb!r},union_by_name=true)").df().trade_date.astype(str))
NSE_SER = {"EQ", "BE", "BZ", "SM", "ST", "SZ"}
BSE_GRP = {"A", "B", "T", "X", "XT", "Z", "M", "MT", "TS", "P", "MS", "ZP", "Y"}
by_year = {}
for i, ds in enumerate(cal):
    d = date.fromisoformat(ds)
    rows = []
    if ds not in have_nse:
        rows += [dict(date=ds, ex="NSE", symbol=r["sym"], code=None, series=r["ser"], isin=r["isin"], open=r["open"], close=r["close"], prev=r["prev"])
                 for r in vb.nse_rows(d) if r["ser"] in NSE_SER]
    rows += [dict(date=ds, ex="BSE", symbol=r["sym"], code=r.get("code"), series=r["ser"], isin=r["isin"], open=r["open"], close=r["close"], prev=r["prev"])
             for r in vb.bse_rows(d) if r["ser"].strip() in BSE_GRP]
    by_year.setdefault(ds[:4], []).extend(rows)
    if i % 50 == 0:
        print(i, len(cal), ds, len(rows), flush=True)
for y, rows in by_year.items():
    pd.DataFrame(rows).to_parquet(OUT / f"dl_{y}.parquet", index=False)
# NSE rows from data bank
q = f"""select trade_date as date, 'NSE' as ex, symbol, null as code, series, isin, open, close, prev_close as prev
        from read_parquet({nb!r},union_by_name=true) where series in ('EQ','BE','BZ','SM','ST','SZ')"""
con.execute(q).df().to_parquet(OUT / "nse_databank.parquet", index=False)
print("done", len(cal))
