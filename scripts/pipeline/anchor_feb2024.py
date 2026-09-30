"""Re-anchor pre-Feb-2024 share estimates on the 1 Feb 2024 NSE MCAP (closest available to listing).
shares_at_listing = shares_on_2024-02-01 / (split-bonus multiplier between listing and 2024-02-01)
multiplier = (listing raw close / Kite adj close at listing) / (raw close 2024-02-01 / Kite adj close 2024-02-01)
"""
import csv, io, time, zipfile
from pathlib import Path
import numpy as np, pandas as pd, requests
S=Path(__file__).parent
ENV=Path("/home/bhuvanesh.r/Documents/Bhuvan projects/IPO/.env")
v=dict(l.split("=",1) for l in ENV.read_text().splitlines() if "=" in l and not l.startswith("#"))
H={"X-Kite-Version":"3","Authorization":f"token {v['KITE_API_KEY'].strip()}:{v['KITE_ACCESS_TOKEN'].strip()}"}
PR=Path("/home/bhuvanesh.r/Documents/Bhuvan projects/IPO/data/raw/nse_pr")
def mcap(day):
    z=zipfile.ZipFile(PR/f"{day}.zip"); n=[x for x in z.namelist() if x.upper().startswith("MCAP")][0]
    m=pd.read_csv(io.BytesIO(z.read(n)),skipinitialspace=True); m.columns=[c.strip() for c in m.columns]
    m["Symbol"]=m.Symbol.astype(str).str.strip(); m["sh"]=pd.to_numeric(m["Issue Size"].astype(str).str.strip(),errors="coerce")
    return m.drop_duplicates("Symbol").set_index("Symbol").sh
FEB=mcap("2024-02-01")
z=zipfile.ZipFile(S/"bhav/cache/nse_o_20240201.zip"); raw=pd.read_csv(io.BytesIO(z.read(z.namelist()[0])))
raw.columns=[c.strip() for c in raw.columns]; raw=raw[raw.SERIES.str.strip().isin(["EQ","BE","SM","ST","BZ"])]
RAW=raw.assign(SYMBOL=raw.SYMBOL.str.strip()).drop_duplicates("SYMBOL").set_index("SYMBOL").CLOSE
inst={r["tradingsymbol"]:r["instrument_token"] for r in csv.DictReader(open(S/"kite_inst_NSE.csv")) if r["segment"]=="NSE"}
sc=pd.read_csv(S/"symbolchange.csv",header=None,names=["n","old","new","d"],skipinitialspace=True)
sc=sc.assign(old=sc.old.str.strip(),new=sc.new.str.strip(),d=pd.to_datetime(sc.d.str.strip(),format="%d-%b-%Y",errors="coerce"))
def sym_on(sym,since,until):
    seen=set()
    while sym not in seen:
        seen.add(sym); n=sc[(sc.old==sym)&(sc.d>=pd.Timestamp(since))&(sc.d<=pd.Timestamp(until))].sort_values("d")
        if n.empty: break
        sym=n.new.iloc[0]
    return sym
X=pd.read_csv(S/"size_work5.csv")
X=X[(X.listing_date<"2024-02-01")&X.nse_symbol.notna()&X.current_symbol.notna()]
out=[]
for r in X.itertuples():
    rec={"issue_id":r.issue_id}
    fsym=sym_on(r.nse_symbol,r.listing_date,"2024-02-01")
    rec["feb_symbol"]=fsym; rec["feb_shares"]=FEB.get(fsym,np.nan); rec["feb_raw_close"]=RAW.get(fsym,np.nan)
    tok=next((inst[s] for s in [r.current_symbol, r.current_symbol+"-SM", r.current_symbol+"-ST"] if s in inst),None)
    if tok and pd.notna(rec["feb_raw_close"]):
        rr=requests.get(f"https://api.kite.trade/instruments/historical/{tok}/day",headers=H,params={"from":"2024-02-01","to":"2024-02-01"},timeout=30); time.sleep(0.36)
        c=rr.json().get("data",{}).get("candles",[]) if rr.status_code==200 else []
        if c: rec["feb_kite_close"]=c[0][4]
    out.append(rec)
O=X.merge(pd.DataFrame(out),on="issue_id")
O["f_after"]=O.feb_raw_close/O.feb_kite_close
O["f_before"]=O.adj_factor/O.f_after
O.to_csv(S/"feb_anchor.csv",index=False)
print(len(O),"feb shares found",O.feb_shares.notna().sum(),"f_before computed",O.f_before.notna().sum())
print(O.f_before.round(3).value_counts().head(12))
