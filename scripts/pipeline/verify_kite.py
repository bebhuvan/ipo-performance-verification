"""Third-source check: Kite daily candles on each IPO's listing date.

Maps each IPO to a current Kite instrument using the listing-day identifiers found in
the official bhavcopy (BSE scrip code / ticker, NSE symbol with SME suffixes), then
fetches daily candles around the listing date. A candle is accepted only if it is the
instrument's first candle and falls on the published listing date.
Writes kite_verification.csv. Access token is read from .env and never printed.
"""
import csv, time
from datetime import date, timedelta
from pathlib import Path
import pandas as pd
import requests

S = Path(__file__).parent
ENV = Path("/home/bhuvanesh.r/Documents/Bhuvan projects/IPO/.env")
v = dict(l.split("=", 1) for l in ENV.read_text().splitlines() if "=" in l and not l.startswith("#"))
H = {"X-Kite-Version": "3", "Authorization": f"token {v['KITE_API_KEY'].strip()}:{v['KITE_ACCESS_TOKEN'].strip()}"}


def load(ex):
    rows = [r for r in csv.DictReader(open(S / f"kite_inst_{ex}.csv")) if r["instrument_type"] == "EQ" and r["segment"] == ex]
    return {r["tradingsymbol"]: r for r in rows}, {r["exchange_token"]: r for r in rows}


NSE_SYM, _ = load("NSE")
BSE_SYM, BSE_CODE = load("BSE")


def candles(token, start, end):
    for attempt in range(4):
        r = requests.get(f"https://api.kite.trade/instruments/historical/{token}/day", headers=H,
                         params={"from": start.isoformat(), "to": end.isoformat()}, timeout=30)
        time.sleep(0.36)  # documented limit: 3 req/s
        if r.status_code == 429:
            time.sleep(2 * (attempt + 1)); continue
        if r.status_code != 200:
            return None, f"HTTP {r.status_code}"
        return r.json()["data"]["candles"], "ok"
    return None, "rate limited"


def nse_candidates(row):
    syms = [s for s in [row.get("nse_symbol"), row.get("symbol")] if isinstance(s, str) and s and not s.isdigit()]
    out = []
    for s in syms:
        out += [s, f"{s}-SM", f"{s}-ST", f"{s}-BE", f"{s}-BZ"]
    return [NSE_SYM[s] for s in dict.fromkeys(out) if s in NSE_SYM]


def bse_candidates(row):
    out = []
    code = str(row.get("bse_code") or "").split(".")[0]
    if code in BSE_CODE:
        out.append(BSE_CODE[code])
    s = row.get("bse_symbol")
    if isinstance(s, str) and s in BSE_SYM and BSE_SYM[s] not in out:
        out.append(BSE_SYM[s])
    return out


def main():
    V = pd.read_csv(S / "bhav_verification.csv", dtype=str)
    U = pd.read_csv(S / "universe_dedup.csv", dtype=str)[["issue_id", "symbol"]]
    V = V.merge(U, on="issue_id", how="left")
    # old-format BSE rows store the scrip code in bse_symbol; new-format store the ticker
    V["bse_code"] = V.bse_symbol.where(V.bse_symbol.fillna("").str.isdigit())
    out = []
    for i, row in enumerate(V.to_dict("records")):
        ld = date.fromisoformat(row["listing_date"])
        rec = {"issue_id": row["issue_id"]}
        for ex, cands in (("nse", nse_candidates(row)), ("bse", bse_candidates(row))):
            rec[f"kite_{ex}_status"] = "no instrument in current Kite master"
            for inst in cands:
                cs, st = candles(inst["instrument_token"], ld - timedelta(days=21), ld + timedelta(days=3))
                if cs is None:
                    rec[f"kite_{ex}_status"] = st; continue
                if not cs:
                    rec[f"kite_{ex}_status"] = "no candles in window"; continue
                first = cs[0][0][:10]
                on_day = [c for c in cs if c[0][:10] == row["listing_date"]]
                if first != row["listing_date"]:
                    rec[f"kite_{ex}_status"] = f"first candle {first} != listing date"
                    if on_day:  # keep the value for inspection, but not as verified
                        rec[f"kite_{ex}_close_unverified"] = on_day[0][4]
                    continue
                c = on_day[0]
                rec.update({f"kite_{ex}_symbol": inst["tradingsymbol"], f"kite_{ex}_open": c[1], f"kite_{ex}_close": c[4],
                            f"kite_{ex}_status": "ok"})
                break
        out.append(rec)
        if i % 100 == 0:
            print(i, len(V), flush=True)
    pd.DataFrame(out).to_csv(S / "kite_verification.csv", index=False)
    print("done", len(out))


if __name__ == "__main__":
    main()
