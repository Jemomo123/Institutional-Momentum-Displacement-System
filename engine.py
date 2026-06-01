import numpy as np
import pandas as pd
import ccxt

class InstitutionalEngine:
    def __init__(self, watch_pool=None):
        # Your verified watchlist pool of 5 major tokens
        self.watch_pool = watch_pool or ["BTC/USDT", "ETH/USDT", "SOL/USDT", "PEPE/USDT", "BONK/USDT"]
        self.timeframes = ["3m", "5m", "15m"]
        
        # Interchangeable Failover Matrix instances
        self.exchanges = {
            "binance": ccxt.binance({'enableRateLimit': True, 'options': {'defaultType': 'future'}}),
            "okx": ccxt.okx({'enableRateLimit': True}),
            "mexc": ccxt.mexc({'enableRateLimit': True}),
            "gateio": ccxt.gateio({'enableRateLimit': True})
        }
        # The priority order for automatic failover
        self.exchange_priority = ["binance", "okx", "mexc", "gateio"]

    def fetch_live_candles(self, symbol, timeframe):
        """Attempts to fetch live candles using the interchangeable exchange matrix."""
        for ex_name in self.exchange_priority:
            try:
                exchange = self.exchanges[ex_name]
                # Fetch recent 120 candles to ensure enough space for a 100 SMA
                ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=120)
                if ohlcv and len(ohlcv) >= 100:
                    df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                    df['close'] = df['close'].astype(float)
                    df['open'] = df['open'].astype(float)
                    df['high'] = df['high'].astype(float)
                    df['low'] = df['low'].astype(float)
                    return df, ex_name
            except Exception:
                continue # If an API fails, it silently jumps to the next exchange in the matrix
        return None, None

    def calculate_smas(self, df):
        """Strict 20 and 100 SMA calculations only."""
        df = df.copy()
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma100'] = df['close'].rolling(window=100).mean()
        return df

    def check_compression(self, df):
        """Checks for the 0.1% 'ALL TOGETHER' Squeeze (Price, 20, 100 SMA)."""
        df = self.calculate_smas(df)
        idx = -2 # Check the last completed candle
        
        price = df['close'].iloc[idx]
        sma20 = df['sma20'].iloc[idx]
        sma100 = df['sma100'].iloc[idx]

        if pd.isna(sma20) or pd.isna(sma100):
            return False, 0

        vals = [price, sma20, sma100]
        deviation = (max(vals) - min(vals)) / min(vals)

        if deviation <= 0.001:  # Strict 0.1% rule
            # Trace cluster size (even if it's just 1 single candle)
            cluster_candles = []
            lookback = idx
            while lookback >= -20:
                p = df['close'].iloc[lookback]
                s20 = df['sma20'].iloc[lookback]
                s100 = df['sma100'].iloc[lookback]
                if pd.isna(s20) or pd.isna(s100): break
                v = [p, s20, s100]
                if (max(v) - min(v)) / min(v) <= 0.001:
                    cluster_candles.append(abs(df['close'].iloc[lookback] - df['open'].iloc[lookback]))
                    lookback -= 1
                else: break
            
            avg_cluster_body = np.mean(cluster_candles) if cluster_candles else abs(df['close'].iloc[idx] - df['open'].iloc[idx])
            return True, avg_cluster_body
            
        return False, 0

    def analyze_sequence(self, df):
        """Executes full sequence: SQZ -> 1x Expansion -> BOS -> OB Origin -> Retest"""
        is_sqz, avg_cluster_body = self.check_compression(df)
        
        result = {"sqz_status": "NONE", "expansion": "NONE", "bos_status": "NONE", "ob_zone": "NONE", "retest_status": "NONE", "direction": "NONE"}
        if not is_sqz: 
            return result

        result["sqz_status"] = "ALL TOGETHER"
        trigger_idx = -1 # Live developing candle
        trigger_body = abs(df['close'].iloc[trigger_idx] - df['open'].iloc[trigger_idx])
        
        # Strict 1x Elephant candle gate
        if trigger_body >= (1.0 * avg_cluster_body):
            is_long = df['close'].iloc[trigger_idx] > df['open'].iloc[trigger_idx]
            direction = "LONG" if is_long else "SHORT"
            result["direction"] = direction
            result["expansion"] = f"{round(trigger_body / avg_cluster_body, 1)}x Elephant"
            
            recent_candles = df.iloc[-15:-2]
            if is_long:
                swing_high = recent_candles['high'].max()
                if df['high'].iloc[trigger_idx] > swing_high:
                    result["bos_status"] = "BOS CONFIRMED"
                    ob_candles = df.iloc[-5:-1]
                    bearish_ob = ob_candles[ob_candles['close'] < ob_candles['open']]
                    if not bearish_ob.empty:
                        target_ob = bearish_ob.iloc[-1]
                        ob_low, ob_high = target_ob['low'], target_ob['high']
                        result["ob_zone"] = f"{round(ob_low, 4)} - {round(ob_high, 4)}"
                        current_price = df['close'].iloc[trigger_idx]
                        if current_price <= ob_high and current_price >= ob_low: result["retest_status"] = "🔥 RETEST ACTIVE"
                        elif current_price < ob_low: result["retest_status"] = "TRIGGERED"
                        else: result["retest_status"] = "STALKING"
            else:
                swing_low = recent_candles['low'].min()
                if df['low'].iloc[trigger_idx] < swing_low:
                    result["bos_status"] = "BOS CONFIRMED"
                    ob_candles = df.iloc[-5:-1]
                    bullish_ob = ob_candles[ob_candles['close'] > ob_candles['open']]
                    if not bullish_ob.empty:
                        target_ob = bullish_ob.iloc[-1]
                        ob_low, ob_high = target_ob['low'], target_ob['high']
                        result["ob_zone"] = f"{round(ob_low, 4)} - {round(ob_high, 4)}"
                        current_price = df['close'].iloc[trigger_idx]
                        if current_price >= ob_low and current_price <= ob_high: result["retest_status"] = "🔥 RETEST ACTIVE"
                        elif current_price > ob_high: result["retest_status"] = "TRIGGERED"
                        else: result["retest_status"] = "STALKING"
                            
        return result
      
