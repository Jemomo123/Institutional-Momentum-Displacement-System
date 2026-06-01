import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional

class RetestContinuationEngine:
    def __init__(self):
        self.tracked_blocks = []

    def register_block(self, symbol: str, direction: str, trigger_price: float, zone_high: float, zone_low: float):
        for block in self.tracked_blocks:
            if block.get("symbol") == symbol and block.get("direction") == direction:
                return
        
        profile = {
            "symbol": symbol,
            "direction": direction,
            "trigger_price": trigger_price,
            "zone_high": zone_high,
            "zone_low": zone_low,
            "has_left_zone": False,
            "is_invalidated": False,
            "status": "TRACKING"
        }
        self.tracked_blocks.append(profile)

    def evaluate_live_lifecycle(self, symbol, df_3m, df_5m, df_15m, df_1h, *args, **kwargs):
        """
        Ingests multi-timeframe candles safely. 
        *args and **kwargs protect the entry points from parameter routing errors.
        """
        alerts = []
        active_blocks = [b for b in self.tracked_blocks if not b.get("is_invalidated")]

        if not active_blocks:
            return alerts

        # Safely pull the absolute latest close price from the 3m matrix
        if df_3m is None or df_3m.empty:
            return alerts
            
        current_price = float(df_3m['close'].iloc[-1])

        for block in active_blocks:
            # 1. Track clean exit from structural block zone
            if not block["has_left_zone"]:
                if block["direction"] == "BULLISH" and current_price > block["zone_high"]:
                    block["has_left_zone"] = True
                elif block["direction"] == "BEARISH" and current_price < block["zone_low"]:
                    block["has_left_zone"] = True
                continue

            # 2. Hard Invalidation breaks if price breaches the opposing extreme
            if block["direction"] == "BULLISH":
                if current_price < block["zone_low"]:
                    block["is_invalidated"] = True
                    block["status"] = "INVALIDATED"
                    continue
                
                # Check for Bullish Retest entry trigger condition (Price returns to tap top of zone)
                if current_price <= block["zone_high"] and current_price >= block["zone_low"]:
                    block["is_invalidated"] = True  # Triggered once
                    block["status"] = "TRIGGERED"
                    alerts.append({
                        "symbol": symbol,
                        "direction": "BULLISH_RETEST",
                        "price": current_price,
                        "msg": f"🔥 BULLISH RETEST: {symbol} triggered entry at {current_price}"
                    })

            elif block["direction"] == "BEARISH":
                if current_price > block["zone_high"]:
                    block["is_invalidated"] = True
                    block["status"] = "INVALIDATED"
                    continue

                # Check for Bearish Retest entry trigger condition (Price returns to tap bottom of zone)
                if current_price >= block["zone_low"] and current_price <= block["zone_high"]:
                    block["is_invalidated"] = True  # Triggered once
                    block["status"] = "TRIGGERED"
                    alerts.append({
                        "symbol": symbol,
                        "direction": "BEARISH_RETEST",
                        "price": current_price,
                        "msg": f"💥 BEARISH RETEST: {symbol} triggered entry at {current_price}"
                    })

        return alerts
