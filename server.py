# server.py
import asyncio
import json
import time
import numpy as np
import pandas as pd
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from engine import InstitutionalScannerEngine
from retest_engine import RetestContinuationEngine

app = FastAPI(title="HQ Liquidation Order Flow Matrix v2")
templates = Jinja2Templates(directory="templates")

engine = InstitutionalScannerEngine()
retest_engine = RetestContinuationEngine()

LIVE_ALERTS_BROADCAST_QUEUE = []

async def execute_order_flow_streaming_pipeline():
    """Asynchronous pipeline to stream live ticks, check multi-timeframe structures, and catch retests."""
    global LIVE_ALERTS_BROADCAST_QUEUE
    while True:
        try:
            current_time = int(time.time())
            timestamps = pd.date_range(start="2026-05-31", periods=220, freq="5m").astype(int) // 10**9
            
            # Construct synthetic primary test frame structures
            df_mock = pd.DataFrame({
                'timestamp': timestamps,
                'open': np.linspace(150.0, 152.0, 220),
                'high': np.linspace(150.5, 153.0, 220),
                'low': np.linspace(149.8, 151.8, 220),
                'close': np.linspace(150.2, 152.8, 220),
                'volume': np.random.uniform(5000, 12000, 220)
            })
            
            # Force an institutional breakout candle to validate the pipeline structures
            df_mock.loc[df_mock.index[-1], ['open', 'high', 'low', 'close', 'volume']] = [152.0, 158.5, 151.9, 158.0, 45000]
            oi_series = pd.Series(np.linspace(120000, 126000, 220))
            
            mtf_matrices = {"3m": df_mock, "5m": df_mock, "15m": df_mock}
            df_1h = pd.DataFrame({'close': np.linspace(150, 160, 220), 'high': 161, 'low': 148, 'open': 150})
            
            impulse = engine.parse_market_state(mtf_matrices, oi_series, df_1h)
            if impulse:
                retest_engine.register_new_order_block("SOLUSDT", "5m", impulse)
            
            # Simulate a continuous trace return entry to verify the state container
            simulated_retest_price = 154.5
            alerts = retest_engine.evaluate_live_market_states("SOLUSDT", "5m", simulated_retest_price)
            if alerts:
                LIVE_ALERTS_BROADCAST_QUEUE = alerts
                
        except Exception as e:
            print(f"[PIPELINE ERROR INITIALIZING CORE LOOP] {e}")
            
        await asyncio.sleep(1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(execute_order_flow_streaming_pipeline())

@app.get("/", response_class=HTMLResponse)
async def desktop_gateway(request: Request):
    return templates.TemplateResponse(request, "index.html")
@app.get("/stream/signals")
async def stream_signals(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            payload = list(LIVE_ALERTS_BROADCAST_QUEUE)
            yield f"data: {json.dumps(payload)}\n\n"
            await asyncio.sleep(1)
            
    return StreamingResponse(event_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    # Use single-worker binding to prevent duplicate background calculation threads
    uvicorn.run(app, host="0.0.0.0", port=10000)
