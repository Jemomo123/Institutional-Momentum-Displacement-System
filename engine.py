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

    def extract_swing_points(self, df: pd.DataFrame, strength: int = 5) -> Tuple[List[float], List[float]]:
        highs, lows = [], []
        for i in range(strength, len(df) - strength):
            cond_high = all(df['high'].iloc[i] > df['high'].iloc[i-j] for j in range(1, strength+1)) and \
                        all(df['high'].iloc[i] > df['high'].iloc[i+j] for j in range(1, strength+1))
            cond_low = all(df['low'].iloc[i] < df['low'].iloc[i-j] for j in range(1, strength+1)) and \
                       all(df['low'].iloc[i] < df['low'].iloc[i+j] for j in range(1, strength+1))
            if cond_high:
                highs.append(float(df['high'].iloc[i]))
            if cond_low:
                lows.append(float(df['low'].iloc[i]))
        return highs, lows

    def check_base_squeeze(self, df: pd.DataFrame) -> Tuple[bool, bool, float]:
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
        avg_body = bodies.iloc[-self.lookback:-1].mean()
        current_body = bodies.iloc[-1]
        body_contraction = max(0.0, 1.0 - (current_body / (avg_body + 1e-8)))
        sqz_score = (body_contraction * 50) + (50 if (all_together or special_one) else 0)
        
        return all_together, special_one, sqz_score

    def locate_true_order_block_origin(self, df: pd.DataFrame, direction: str) -> Dict[str, float]:
        idx = len(df) - 2
        found_candle = df.iloc[idx]
        
        if direction == "LONG":
            while idx > 0:
                if df['close'].iloc[idx] < df['open'].iloc[idx]:
                    found_candle = df.iloc[idx]
                    break
                idx -= 1
        else:
            while idx > 0:
                if df['close'].iloc[idx] > df['open'].iloc[idx]:
                    found_candle = df.iloc[idx]
                    break
                idx -= 1
                
        return {
            "top": float(found_candle['high']),
            "bottom": float(found_candle['low'])
        }

    def detect_session_liquidity_sweeps(self, df: pd.DataFrame) -> Dict[str, Any]:
        if len(df) < 60:
            return {"sweep_detected": False, "weight": 0.0}
            
        recent = df.iloc[-1]
        historical = df.iloc[-60:-1]
        
        eq_highs = np.isclose(historical['high'], historical['high'].max(), rtol=1e-4).sum() > 1
        eq_lows = np.isclose(historical['low'], historical['low'].min(), rtol=1e-4).sum() > 1
        
        sweep_high = (recent['high'] > historical['high'].max()) and (recent['close'] < historical['high'].max())
        sweep_low = (recent['low'] < historical['low'].min()) and (recent['close'] > historical['low'].min())
        
        is_sweep = sweep_high or sweep_low or (eq_highs and sweep_high) or (eq_lows and sweep_low)
        return {
            "sweep_detected": is_sweep,
            "weight": 35.0 if is_sweep else 0.0
        }

    def compute_composite_expansion(self, df: pd.DataFrame, oi_series: pd.Series) -> Tuple[bool, float, float]:
        if len(df) < self.lookback + 1 or len(oi_series) < 2:
            return False, 0.0, 0.0
            
        bodies = (df['close'] - df['open']).abs()
        avg_body = bodies.iloc[-self.lookback-1:-1].mean()
        body_ratio = bodies.iloc[-1] / (avg_body + 1e-8)
        score_body = min(100.0, (body_ratio / 1.0) * 40)
        
        avg_vol = df['volume'].iloc[-self.lookback-1:-1].mean()
        vol_ratio = df['volume'].iloc[-1] / (avg_vol + 1e-8)
        score_volume = min(25.0, (vol_ratio / 1.5) * 25)
        
        prev_oi = oi_series.iloc[-2]
        delta_oi = oi_series.iloc[-1] - prev_oi
        oi_change_pct = (delta_oi / (prev_oi + 1e-8)) * 100
        
        if oi_change_pct >= 5.0: score_oi = 20.0
        elif oi_change_pct >= 2.0: score_oi = 15.0
        elif oi_change_pct >= 1.0: score_oi = 10.0
        elif oi_change_pct >= 0.5: score_oi = 5.0
        else: score_oi = 0.0
        
        if vol_ratio < 0.8:
            score_volume = 0.0
            score_body *= 0.5
            
        atr = (df['high'] - df['low']).rolling(self.lookback).mean().iloc[-2]
        move_dist = abs(df['close'].iloc[-1] - df['open'].iloc[-1])
        dist_ratio = move_dist / (atr + 1e-8)
        score_dist = min(15.0, (dist_ratio / 1.0) * 15)
        
        composite_score = score_body + score_volume + score_oi + score_dist
        is_valid = body_ratio >= 1.0 and vol_ratio >= 0.9
        
        return is_valid, round(composite_score, 2), round(oi_change_pct, 2)

    def extract_htf_bias(self, df_1h: pd.DataFrame) -> str:
        if len(df_1h) < 200:
            return "NEUTRAL"
        df_1h = self.calculate_smas(df_1h)
        last_close = df_1h['close'].iloc[-1]
        sma200 = df_1h['sma200'].iloc[-1]
        return "LONG" if last_close > sma200 else "SHORT"

    def process_impulse(self, mtf_dfs: Dict[str, pd.DataFrame], oi_series: pd.Series, df_1h: pd.DataFrame) -> Optional[Dict[str, Any]]:
        df_primary = mtf_dfs.get("5m")
        if df_primary is None or len(df_primary) < 50:
            return None
            
        df_primary = self.calculate_smas(df_primary)
        
        sqz_3m_all, sqz_3m_sp, _ = self.check_base_squeeze(self.calculate_smas(mtf_dfs["3m"]))
        sqz_5m_all, sqz_5m_sp, _ = self.check_base_squeeze(df_primary)
        sqz_15m_all, sqz_15m_sp, _ = self.check_base_squeeze(self.calculate_smas(mtf_dfs["15m"]))
        
        mega_sqz = (sqz_3m_all or sqz_3m_sp) and (sqz_5m_all or sqz_5m_sp) and (sqz_15m_all or sqz_15m_sp)
        
        sw_highs, sw_lows = self.extract_swing_points(df_primary)
        if not sw_highs or not sw_lows:
            return None
            
        last_candle = df_primary.iloc[-1]
        bos_long = last_candle['close'] > sw_highs[-1]
        bos_short = last_candle['close'] < sw_lows[-1]
        
        if not (bos_long or bos_short):
            return None
            
        direction = "LONG" if bos_long else "SHORT"
        
        ob_zone = self.locate_true_order_block_origin(df_primary, direction)
        sweep_data = self.detect_session_liquidity_sweeps(df_primary)
        is_exp, exp_score, oi_pct = self.compute_composite_expansion(df_primary, oi_series)
        
        if not is_exp:
            return None
            
        htf_bias = self.extract_htf_bias(df_1h)
        bias_aligned = htf_bias == direction
        
        # Matches mandatory dictionary schemas exactly
        return {
            "timestamp": float(last_candle['timestamp']),
            "direction": direction,
            "mega_sqz": mega_sqz,
            "sweep_detected": sweep_data["sweep_detected"],
            "expansion_score": exp_score,
            "oi_pct": oi_pct,
            "htf_bias_aligned": bias_aligned,
            "ob_zone": ob_zone
        }
