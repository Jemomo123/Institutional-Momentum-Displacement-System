# failover_fetcher.py
import asyncio
import httpx
from typing import Dict, Any, List, Optional

class InterchangeableExchangeMatrix:
    def __init__(self):
        # Ordered list of your 7 interchangeable platforms
        self.exchanges_priority = ["binance", "bybit", "okx", "mexc", "gateio", "bingx", "weex"]
        
        # Public REST API base endpoints for perpetual futures / spot data
        self.api_endpoints = {
            "binance": "https://fapi.binance.com",
            "bybit": "https://api.bybit.com",
            "okx": "https://www.okx.com",
            "mexc": "https://contract.mexc.com",
            "gateio": "https://api.gateio.ws/api/v4",
            "bingx": "https://open-api.bingx.com",
            "weex": "https://api.weex.com"
        }
        
        # Uniform timeframe translation table mapping standard keys to exchange formats
        self.timeframe_maps = {
            "binance": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"},
            "bybit": {"3m": "3", "5m": "5", "15m": "15", "1h": "60", "4h": "240"},
            "okx": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1H", "4h": "4H"},
            "mexc": {"3m": "Min3", "5m": "Min5", "15m": "Min15", "1h": "Min60", "4h": "Hour4"},
            "gateio": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"},
            "bingx": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"},
            "weex": {"3m": "3m", "5m": "5m", "15m": "15m", "1h": "1h", "4h": "4h"}
        }

    async def fetch_candles_from_exchange(self, exchange: str, symbol: str, timeframe: str) -> Optional[List[List[Any]]]:
        """
        Handles the raw HTTP parsing logic for each individual exchange API endpoint format.
        """
        base_url = self.api_endpoints.get(exchange)
        tf_mapped = self.timeframe_maps[exchange].get(timeframe, "5m")
        
        # Added standard mobile agent headers to comfortably bypass automated traffic firewalls
        headers = {
            "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
        }
        
        # Raised connection timeout window to 10.0 seconds to give shared network paths ample time to handshake
        async with httpx.AsyncClient(timeout=10.0, headers=headers) as client:
            try:
                if exchange == "binance":
                    url = f"{base_url}/fapi/v1/klines"
                    params = {"symbol": symbol.replace(":", ""), "interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    if res.status_code == 200: return res.json()

                elif exchange == "bybit":
                    url = f"{base_url}/v5/market/kline"
                    params = {"category": "linear", "symbol": symbol.replace(":", ""), "interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    if res.status_code == 200: return res.json().get("result", {}).get("list", [])

                elif exchange == "okx":
                    url = f"{base_url}/api/v5/market/candles"
                    params = {"instId": f"{symbol}-SWAP", "bar": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    if res.status_code == 200: return res.json().get("data", [])

                elif exchange == "mexc":
                    url = f"{base_url}/api/v1/contract/kline/{symbol}"
                    params = {"interval": tf_mapped, "limit": 200}
                    res = await client.get(url, params=params)
                    if res.status_code == 200: return res.json().get("data", {})

                else:
                    return None
            except Exception:
                return None  
        return None

    async def fetch_candles_with_failover(self, symbol: str, timeframe: str) -> Dict[str, Any]:
        """
        Iterates through the 7 exchanges in priority order. 
        If an API fails, it immediately catches the error and drops to the next provider.
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
            
        return {
            "source_exchange": None,
            "status": "CRITICAL_ALL_EXCHANGES_FAILED",
            "data": []
        }
