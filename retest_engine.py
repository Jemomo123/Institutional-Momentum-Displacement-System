# retest_engine.py
import time
from typing import Dict, Any, List

class TrackingOrderBlockProfile:
    def __init__(self, symbol: str, timeframe: str, impulse_data: Dict[str, Any]):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = impulse_data["direction"]
        self.zone = impulse_data["ob_zone"]
        self.creation_time = impulse_data["timestamp"]
        self.mega_sqz = impulse_data["mega_sqz"]
        self.sweep_detected = impulse_data["sweep_detected"]
        self.expansion_score = impulse_data["expansion_score"]
        self.oi_pct = impulse_data["oi_pct"]
        self.htf_bias_aligned = impulse_data["htf_bias_aligned"]
        
        self.has_left_zone = False
        self.currently_inside_zone = False  # Fixed counting logic flag
        self.retest_count = 0
        self.is_invalidated = False

class RetestContinuationEngine:
    def __init__(self):
        # Fixed typography breaking code bug split
        self.tracked_blocks: List[TrackingOrderBlockProfile] = []

    def register_block(self, symbol: str, timeframe: str, impulse_data: Dict[str, Any]):
        for block in self.tracked_blocks:
            if block.symbol == symbol and block.timeframe == timeframe and block.direction == impulse_data["direction"]:
                return
        profile = TrackingOrderBlockProfile(symbol, timeframe, impulse_data)
        self.tracked_blocks.append(profile)

    def evaluate_live_lifecycle(self, symbol: str, timeframe: str, current_price: float) -> List[Dict[str, Any]]:
        alerts = []
        active_blocks = [b for b in self.tracked_blocks if b.symbol == symbol and b.timeframe == timeframe and not b.is_invalidated]
        
        for block in active_blocks:
            # 1. Track clean exit from original block boundaries
            if not block.has_left_zone:
                if block.direction == "LONG" and current_price > block.zone["top"]:
                    block.has_left_zone = True
                elif block.direction == "SHORT" and current_price < block.zone["bottom"]:
                    block.has_left_zone = True
                continue
                
            # 2. Hard Invalidation validation breach check
            if block.direction == "LONG" and current_price < block.zone["bottom"]:
                block.is_invalidated = True
                continue
            elif block.direction == "SHORT" and current_price > block.zone["top"]:
                block.is_invalidated = True
                continue
                
            inside_zone = block.zone["bottom"] <= current_price <= block.zone["top"]
            
            # 3. Fixed Retest Increment Rules
            if inside_zone:
                if not block.currently_inside_zone:
                    # Outside -> Inside (Increment Once)
                    block.retest_count += 1
                    block.currently_inside_zone = True
                    
                    if block.retest_count >= 4:
                        block.is_invalidated = True
                        continue
                        
                    # Calculate decaying score values
                    quality_score = 100.0
                    if block.retest_count == 2: quality_score = 75.0
                    elif block.retest_count == 3: quality_score = 50.0
                    
                    # Killer Rule evaluation criteria validation 
                    killer_qualified = (
                        block.mega_sqz and 
                        block.sweep_detected and 
                        block.expansion_score >= 80.0 and 
                        block.oi_pct >= 2.0 and 
                        block.retest_count == 1 and 
                        block.htf_bias_aligned
                    )
                    
                    tier = "KILLER" if killer_qualified else "HIGH"
                    
                    # Matches mandatory frontend alert schema dictionary exactly
                    alerts.append({
                        "symbol": str(block.symbol),
                        "timeframe": str(block.timeframe),
                        "direction": str(block.direction),
                        "tier": str(tier),
                        "quality_score": float(quality_score),
                        "retest_index": int(block.retest_count),
                        "zone": block.zone,
                        "msg": "Order Block Retest Continuation Entry Active",
                        "timestamp": float(time.time())
                    })
                else:
                    # Inside -> Inside (Do NOT increment)
                    pass
            else:
                # Inside -> Outside (Reset edge tracking state framework)
                block.currently_inside_zone = False
                
        self.tracked_blocks = [b for b in self.tracked_blocks if not b.is_invalidated]
        return alerts
