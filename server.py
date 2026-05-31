# server.py
import asyncio
import json
import os
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from engine import InstitutionalScannerEngine
from retest_engine import RetestContinuationEngine
from failover_fetcher import InterchangeableExchangeMatrix  # Live failover link

app = FastAPI(title="Institutional Momentum Displacement Terminal")

base_dir = os.path.dirname(os.path.abspath(__file__))
templates = Jinja2Templates(directory=os.path.join(base_dir, "templates"))

engine = InstitutionalScannerEngine()
retest_engine = RetestContinuationEngine()
fetcher_matrix = InterchangeableExchangeMatrix()

# Your production 25-asset tracking watchlist
WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "PEPEUSDT", "DOGEUSDT", 
    "BONKUSDT", "XRPUSDT", "ADAUSDT", "AVAXUSDT", "LINKUSDT",
    "DOTUSDT", "MATICUSDT", "SHIBUSDT", "LTCUSDT", "BCHUSDT",
    "ATOMUSDT", "XLMUSDT", "NEARUSDT", "TIAUSDT", "INJUSDT",
    "OPUSDT", "ARBUSDT", "SUIUSDT", "APTUSDT", "WIFUSDT"
]

LIVE_TRACKING_ALERTS = []

def process_raw_exchange_candles(raw_data: list, exchange: str) -> pd.DataFrame:
    """
    Standardizes historical structures across arbitrary API schemas 
    into a unified pandas processing layout.
    """
    try:
        if exchange == "binance":
            df = pd.DataFrame(raw_data).iloc[:, :6]
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        elif exchange == "bybit":
            df = pd.DataFrame(raw_data)
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'turnover']
        elif exchange == "okx":
            df = pd.DataFrame(raw_data).iloc[:, :6]
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        elif exchange == "mexc":
            df = pd.DataFrame(raw_data)
            df = df[['time', 'open', 'high', 'low', 'close', 'vol']]
            df.columns = ['timestamp', 'open', 'high', 'low', 'close', 'volume']
        else:
            return pd.DataFrame()

        df['timestamp'] = df['timestamp'].astype(float) / 1000 if float(raw_data[0][0]) > 2e9 else df['timestamp'].astype(float)
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        return df.sort_values('timestamp').reset_index(drop=True)
    except Exception:
        return pd.DataFrame()

async def production_market_feed_loop():
    global LIVE_TRACKING_ALERTS
    while True:
        for symbol in WATCHLIST:
            try:
                # 1. Fetch live charts for your preferred execution intervals via failover matrix
                res_3m = await fetcher_matrix.fetch_candles_with_failover(symbol, "3m")
                res_5m = await fetcher_matrix.fetch_candles_with_failover(symbol, "5m")
                res_15m = await fetcher_matrix.fetch_candles_with_failover(symbol, "15m")
                res_1h = await fetcher_matrix.fetch_candles_with_failover(symbol, "1h")

                if "SUCCESS" in [res_3m["status"], res_5m["status"], res_15m["status"], res_1h["status"]]:
                    df_3m = process_raw_exchange_candles(res_3m["data"], res_3m["source_exchange"])
                    df_5m = process_raw_exchange_candles(res_5m["data"], res_5m["source_exchange"])
                    df_15m = process_raw_exchange_candles(res_15m["data"], res_15m["source_exchange"])
                    df_1h = process_raw_exchange_candles(res_1h["data"], res_1h["source_exchange"])

                    if df_3m.empty or df_5m.empty or df_15m.empty or df_1h.empty:
                        continue

                    # DEBUG CHECK 1: Verify data rows are loaded successfully
                    print(f"{symbol} 3m={len(df_3m)} 5m={len(df_5m)} 15m={len(df_15m)} 1h={len(df_1h)}")

                    mtf_context = {"3m": df_3m, "5m": df_5m, "15m": df_15m}
                    
                    # Generate a baseline Open Interest proxy tracking metric vector matching schemas
                    oi_mock_series = pd.Series([100000.0, 105000.0], index=[0, 1]) 
                    
                    # 2. Feed live data into the Core Engine
                    impulse = engine.process_impulse(mtf_context, oi_mock_series, df_1h)
                    
                    # DEBUG CHECK 2: See exactly what the engine is returning (or if it returns None)
                    print(f"{symbol} IMPULSE={impulse}")
                    
                    if impulse:
                        retest_engine.register_block(symbol, "5m", impulse)
                    
                    # 3. Track live retests using real-time price tick data
                    current_live_price = float(df_5m['close'].iloc[-1])
                    dispatched = retest_engine.evaluate_live_lifecycle(symbol, "5m", current_live_price)
                    
                    # DEBUG CHECK 3: See if the retest engine processed any matching rules
                    print(f"{symbol} ALERTS={len(dispatched)}")
                    
                    if dispatched:
                        # Append new alerts securely without clearing previous active states
                        for new_alert in dispatched:
                            if new_alert not in LIVE_TRACKING_ALERTS:
                                LIVE_TRACKING_ALERTS.append(new_alert)
                                # DEBUG CHECK 4: Confirm alert is officially saved to global memory
                                print(f"ALERT CREATED: {new_alert}")

            except Exception as e:
                print(f"[LIVE PRODUCTION ROUTING ERROR] Exception on {symbol}: {e}")
            
            # Tiny sleep interval between assets to stay completely under exchange API rate limits
            await asyncio.sleep(0.5)
            
        # Complete rest interval before cycling the full watchlist matrix again
        await asyncio.sleep(5)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(production_market_feed_loop())

@app.get("/", response_class=HTMLResponse)
async def desktop_gateway(request: Request):
    return templates.TemplateResponse(request, "index.html")

@app.get("/stream/signals")
async def stream_signals(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            yield f"data: {json.dumps(LIVE_TRACKING_ALERTS)}\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
            
