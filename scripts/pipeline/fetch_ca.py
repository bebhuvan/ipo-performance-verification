"""Fetch NSE corporate actions since listing for every NSE-listed IPO (current symbol). Cached per symbol."""
import json, time
from pathlib import Path
import pandas as pd
from nse_mcp import MCP
S=Path(__file__).parent; C=S/'ca_cache'; C.mkdir(exist_ok=True)
X=pd.read_csv(S/'size_work4.csv')
X=X[X.nse_symbol.notna()]
m=MCP('https://mcp.nseindia.in/bhavcopy/cm/mcp')
for i,r in enumerate(X.itertuples()):
    sym=r.current_symbol if isinstance(r.current_symbol,str) else r.nse_symbol
    sym=sym.replace('-SM','').replace('-ST','')
    p=C/f'{r.issue_id}.json'
    if p.exists(): continue
    for attempt in range(3):
        try:
            res=m.call('get_corporate_actions',{'symbol':sym,'fromDate':r.listing_date,'toDate':'2026-09-30'})
            txt=res['result']['content'][0]['text']; p.write_text(json.dumps({'symbol':sym,'raw':txt,'isError':res['result'].get('isError')})); break
        except Exception as e:
            time.sleep(3*(attempt+1))
            if attempt==1: m=MCP('https://mcp.nseindia.in/bhavcopy/cm/mcp')
    if i%100==0: print(i,len(X),flush=True)
print('done',len(X))
