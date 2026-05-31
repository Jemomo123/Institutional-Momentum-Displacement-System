# engine.py
import numpy as np
import pandas as pd
from typing import Dict, Any, Optional, Tuple, List

class InstitutionalScannerEngine:
    def __init__(self, lookback_window: int = 20):
        self.lookback = lookback_window

    def calculate_smas(self, df: pd.DataFrame) -> pd.DataFrame:
        df['sma20'] = df['close'].rolling(window=20).mean()
        df['sma100'] = df['close'].rolling(window=100).mean()
        df['sma200'] = df['close'].rolling(window=200).mean()
        return df

    def extract_confirmed_swings(self, df: pd.DataFrame, left: int = 4, right: int = 4) -> Tuple[List[float], List[float]]:
        """
        Extracts structural swing points validated entirely by structural closes.
        Avoids rolling local maxima/minima window traps.
        """
        swing_highs = []
        swing_lows = []
        
        for i in range(left, len(df) - right):
            current_high = df['high'].iloc[i]
            current_low = df['low'].iloc[i]
            
            # Check for structural containment
            is_high = all(current_high > df['high'].iloc[i - j] for j in range(1, left + 1)) and \
                      all(current_high > df['high'].iloc[i + j] for j in range(1, right + 1))
            is_low = all(current_low < df['low'].iloc[i - j] for j in range(1, left + 1)) and \
                     all(current_low < df['low'].iloc[i + j] for j in range(1, right + 1))
                     
            if is_high:
                swing_highs.append(float(current_high))
            if is_low:
                swing_lows.append(float(current_low))
                
        return swing_highs, swing_lows

    def evaluate_timeframe_squeeze(self, df: pd.DataFrame) -> Tuple[bool, bool, float]:
        """Evaluates 0.1% convergence constraints across individual timeframes."""
        if len(df) < 200:
            return False, False, 0.0
            
        last_idx = df.index[-1]
        close = float(df.loc[last_idx, 'close'])
        s20 = float(df.loc[last_idx, 'sma20'])
        s100 = float(df.loc[last_idx, 'sma100'])
        s200 = float(df.loc[last_idx, 'sma200'])
        
        if pd.isna(s20) or pd.isna(s100) or pd.isna(s200):
            return False, False, 0.0

        dev_20_100 = abs(s20 - s100) / min(s20, s100)
        dev_price_20 = abs(close - s20) / min(close, s20)
        dev_20_200 = abs(s20 - s200) / min(s20, s200)

        all_together = (dev_20_100 <= 0.001) and (dev_price_20 <= 0.001)
        special_one = (dev_20_200 <= 0.001) and (dev_price_20 <= 0.001)
        
        bodies = (df['close'] - df['open']).abs()
        avg_body = bodies.iloc[-self.lookback-1:-1].mean()
        current_body = bodies.iloc[-1]
        body_contraction = max(0.0, 1.0 - (current_body / (avg_body + 1e-8)))
        
        sqz_score = (body_contraction * 50.0) + (50.0 if (all_together or special_one) else 0.0)
        return all_together, special_one, sqz_score

    def trace_true_order_block(self, df: pd.DataFrame, direction: str) -> Dict[str, float]:
        """
        Scans backward past the breakout sequence to locate the true footprint origin.
        Isolates the final opposite-colored candle before the institutional displacement began.
        """
        idx = len(df) - 2
        origin_candle = df.iloc[idx]
        
        if direction == "LONG":
            while idx >= 0:
                if df['close'].iloc[idx] < df['open'].iloc[idx]: # Verified bearish origin
                    origin_candle = df.iloc[idx]
                    break
                idx -= 1
        else:
            while idx >= 0:
                if df['close'].iloc[idx] > df['open'].iloc[idx]: # Verified bullish origin
                    origin_candle = df.iloc[idx]
                    break
                idx -= 1
                
        return {
            "top": float(origin_candle['high']),
            "bottom": float(origin_candle['low'])
        }

    def evaluate_deep_liquidity_sweep(self, df: pd.DataFrame, window: int = 20) -> bool:
        """Parses support/resistance traps, liquidity pools, and stop hunts within a flexible window."""
        if len(df) < window + 1:
            return False
            
        recent = df.iloc[-1]
        historical = df.iloc[-window-1:-1]
        
        h_max = historical['high'].max()
        l_min = historical['low'].min()
        
        # Identify equal extreme footprints (Double Tops/Bottoms)
        eq_highs = np.isclose(historical['high'], h_max, rtol=1e-4).sum() >= 2
        eq_lows = np.isclose(historical['low'], l_min, rtol=1e-4).sum() >= 2
        
        sweep_high = (recent['high'] > h_max) and (recent['close'] < h_max)
        sweep_low = (recent['low'] < l_min) and (recent['close'] > l_min)
        
        return bool(sweep_high or sweep_low or (eq_highs and sweep_high) or (eq_lows and sweep_low))

    def evaluate_composite_expansion(self, df: pd.DataFrame, oi_series: pd.Series) -> Tuple[bool, float, float]:
        """
        Computes composite expansion vectors using weighted scoring definitions.
        Body (40%), Volume (25%), Open Interest (20%), Displacement (15%).
        """
        if len(df) < self.lookback + 1 or len(oi_series) < 2:
            return False, 0.0, 0.0
            
        # 1. Body Size Metric (40%)
        bodies = (df['close'] - df['open']).abs()
        avg_body = bodies.iloc[-self.lookback-1:-1].mean()
        body_ratio = bodies.iloc[-1] / (avg_body + 1e-8)
        
        if body_ratio < 1.0: # Enforce Jeremiah Edge 1x floor parameter
            return False, 0.0, 0.0
        score_body = min(40.0, (body_ratio / 2.0) * 40.0)
        
        # 2. Volume Expansion (25%)
        avg_vol = df['volume'].iloc[-self.lookback-1:-1].mean()
        vol_ratio = df['volume'].iloc[-1] / (avg_vol + 1e-8)
        score_volume = min(25.0, (vol_ratio / 2.0) * 25.0)
        
        # Low-volume breakouts are penalized
        if vol_ratio < 1.0:
            score_volume *= 0.2
            score_body *= 0.5
            
        # 3. Open Interest Magnitude Scale (20%)
        prev_oi = oi_series.iloc[-2]
        delta_oi = oi_series.iloc[-1] - prev_oi
        oi_pct = (delta_oi / (prev_oi + 1e-8)) * 100.0
        
        if oi_pct >= 5.0: score_oi = 20.0
        elif oi_pct >= 2.0: score_oi = 15.0
        elif oi_pct >= 1.0: score_oi = 10.0
        elif oi_pct >= 0.5: score_oi = 5.0
        else: score_oi = 0.0
        
        # 4. Pure Close-to-Open Displacement Distance (15%)
        high_low_range = (df['high'] - df['low']).iloc[-self.lookback-1:-1].mean()
        current_displacement = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        disp_ratio = current_displacement / (high_low_range + 1e-8)
        score_disp = min(15.0, (disp_ratio / 1.5) * 15.0)
        
        composite_score = score_body + score_volume + score_oi + score_disp
        return True, round(composite_score, 2), round(oi_pct, 2)

    def extract_htf_trend_alignment(self, df_1h: pd.DataFrame) -> str:
        if len(df_1h) < 200:
            return "NEUTRAL"
        df_1h = self.calculate_smas(df_1h)
        last_close = df_1h['close'].iloc[-1]
        sma200 = df_1h['sma200'].iloc[-1]
        return "LONG" if last_close > sma200 else "SHORT"

    def parse_market_state(self, mtf_matrices: Dict[str, pd.DataFrame], oi_series: pd.Series, df_1h: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Runs the displacement detection sequence on the processing matrices."""
        df_5m = mtf_matrices.get("5m")
        if df_5m is None or len(df_5m) < 50:
            return None
            
        df_5m = self.calculate_smas(df_5m)
        
        # Enforce strict multi-timeframe MEGA SQUEEZE constraints
        sqz_3m_all, sqz_3m_sp, _ = self.evaluate_timeframe_squeeze(self.calculate_smas(mtf_matrices["3m"]))
        sqz_5m_all, sqz_5m_sp, _ = self.evaluate_timeframe_squeeze(df_5m)
        sqz_15m_all, sqz_15m_sp, _ = self.evaluate_timeframe_squeeze(self.calculate_smas(mtf_matrices["15m"]))
        
        mega_sqz = (sqz_3m_all or sqz_3m_sp) and (sqz_5m_all or sqz_5m_sp) and (sqz_15m_all or sqz_15m_sp)
        
        # Confirm Market Structure Shift (BOS)
        s_highs, s_lows = self.extract_confirmed_swings(df_5m)
        if not s_highs or not s_lows:
            return None
            
        last_candle = df_5m.iloc[-1]
        
        # Enforce Close validation confirmation (Wicks alone are invalid)
        bos_long = last_candle['close'] > s_highs[-1]
        bos_short = last_candle['close'] < s_lows[-1]
        
        if not (bos_long or bos_short):
            return None
            
        direction = "LONG" if bos_long else "SHORT"
        
        is_expansion, expansion_score, oi_pct = self.evaluate_composite_expansion(df_5m, oi_series)
        if not is_expansion:
            return None
            
        ob_zone = self.trace_true_order_block(df_5m, direction)
        sweep_detected = self.evaluate_deep_liquidity_sweep(df_5m, window=20)
        htf_bias = self.extract_htf_trend_alignment(df_1h)
        
        return {
            "mega_sqz": mega_sqz,
            "direction": direction,
            "ob_zone": ob_zone,
            "sweep_detected": sweep_detected,
            "expansion_score": expansion_score,
            "oi_pct": oi_pct,
            "htf_bias": htf_bias,
            "timestamp": float(last_candle['timestamp'])
        }
