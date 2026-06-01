# failover_fetcher.py
import asyncio
import httpx
from typing import Dict, Any, List, Optional

class InterchangeableExchangeMatrix:
    def __init__(self):
        # Reduced priority matrix focusing tightly on your 4 core platforms
        self.exchanges_priority = ["binance", "okx", "mexc", "gateio"]
        
        # Public REST API base endpoints
        self.api_endpoints = {
            "binance": "https://fapi.binance.com",
            "okx": "https://www.okx.com",
            "mexc": "https://contract.mexc.com",
            "gateio": "https://api.gateio.ws/api/v4"
        }
        
        # Timeframe translation table for your preferred tracking intervals
        self.timeframe_maps = {
            "binance": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"},
            "okx": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H"},
            "mexc": {"3m": "Min3", "5m": "Min5", "15m": "Min15", "1h": "Min60", "4h": "Hour4"},
            "gateio": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}
        }

    async def fetch_candles_from_exchange(self, exchange: str, symbol: str, timeframe: str) -> Optional[List[List[Any]]]:
        """
        Handles raw HTTP requests for the 4 core exchange APIs with pinpoint symbol tracking.
        Logs the explicit URL, status code, and first 200 characters of a failure payload.
        """
        base_url = self.api_endpoints.get(exchange)
        tf_mapped = self.timeframe_maps[exchange].get(timeframe, "5m")
        
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        }
        
        # Strip any formatting artifacts out of the raw watchlist text token string
        clean_symbol = symbol.replace(":", "").replace("-", "").replace("_", "").upper()
        
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                if exchange == "binance":
                    # Binance Futures Format: BTCUSDT strictly uppercase
                    url = f"{base_url}/fapi/v1/klines"
                    params = {"symbol": clean_symbol, "interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            return data
                    
                    # Enhanced Failure Diagnostics Logging
                    print(f"❌ [FETCH ERROR] BINANCE Fail -> URL: {url} | Status: {res.status_code} | Body (200 chars): {res.text[:200]}")

                elif exchange == "okx":
                    # OKX Instrument ID Layout Format: BTC-USDT-SWAP
                    if clean_symbol.endswith("USDT"):
                        base_coin = clean_symbol.replace("USDT", "")
                        okx_inst = f"{base_coin}-USDT-SWAP"
                    else:
                        okx_inst = f"{clean_symbol}-SWAP"
                        
                    url = f"{base_url}/api/v5/market/candles"
                    params = {"instId": okx_inst, "bar": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    
                    if res.status_code == 200:
                        data = res.json().get("data", [])
                        if isinstance(data, list) and len(data) > 0:
                            return data
                            
                    print(f"❌ [FETCH ERROR] OKX Fail -> URL: {url} Params: {params} | Status: {res.status_code} | Body (200 chars): {res.text[:200]}")

                elif exchange == "mexc":
                    # MEXC Linear Swap Endpoint tracking path parameters
                    url = f"{base_url}/api/v1/contract/kline/{clean_symbol}"
                    params = {"interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    
                    if res.status_code == 200:
                        data = res.json().get("data", [])
                        if isinstance(data, list) and len(data) > 0:
                            return data
                            
                    print(f"❌ [FETCH ERROR] MEXC Fail -> URL: {url} | Status: {res.status_code} | Body (200 chars): {res.text[:200]}")

                elif exchange == "gateio":
                    # GateIO Delivery Layout Format: BTC_USDT passed as 'contract' parameter
                    if clean_symbol.endswith("USDT") and "_" not in clean_symbol:
                        gate_contract = clean_symbol.replace("USDT", "_USDT")
                    else:
                        gate_contract = clean_symbol
                        
                    url = f"{base_url}/futures/usdt/candlesticks"
                    params = {"contract": gate_contract, "interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    
                    if res.status_code == 200:
                        data = res.json()
                        if isinstance(data, list) and len(data) > 0:
                            return data
                            
                    print(f"❌ [FETCH ERROR] GATEIO Fail -> URL: {url} Params: {params} | Status: {res.status_code} | Body (200 chars): {res.text[:200]}")

                else:
                    return None
            except Exception as e:
                print(f"❌ [SYSTEM EXCEPTION] {exchange.upper()} Script Layer Error: {e}")
                return None
        return None

    async def fetch_candles_with_failover(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Iterates through the 4 core exchanges in priority order.
        Verifies non-empty arrays are returned before successfully shifting states.
        """
        for exchange in self.exchanges_priority:
            print(f"[FAILOVER MATRIX] Attempting data fetch on {exchange.upper()} for {symbol} ({timeframe})...")
            
            raw_candles = await self.fetch_candles_from_exchange(exchange, symbol, timeframe)
            if raw_candles and len(raw_candles) > 0:
                print(f"✅ [FAILOVER MATRIX] Successfully recovered data from {exchange.upper()}!")
                return {
                    "source_exchange": exchange,
                    "status": "SUCCESS",
                    "data": raw_candles
                }
                
            print(f"⚠️ [FAILOVER MATRIX] {exchange.upper()} API failed or timed out. Falling back...")
            
        # Cleaned up and confirmed syntax connection lines
        return {
            "source_exchange": None,
            "status": "CRITICAL_ALL_EXCHANGES_FAILED",
            "data": []
        }
