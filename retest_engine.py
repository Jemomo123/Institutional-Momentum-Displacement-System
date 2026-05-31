# retest_engine.py
import time
from typing import Dict, Any, List

class TrackedOrderBlockProfile:
    def __init__(self, symbol: str, timeframe: str, impulse: Dict[str, Any]):
        self.symbol = symbol
        self.timeframe = timeframe
        self.direction = impulse["direction"]
        self.zone = impulse["ob_zone"]
        self.creation_timestamp = impulse["timestamp"]
        self.mega_sqz = impulse["mega_sqz"]
        self.sweep_detected = impulse["sweep_detected"]
        self.expansion_score = impulse["expansion_score"]
        self.oi_pct = impulse["oi_pct"]
        self.htf_bias = impulse["htf_bias"]
        
        # State Machine Matrix: ACTIVE -> LEFT_ZONE -> RETESTED -> INVALIDATED
        self.state = "ACTIVE"
        self.retest_index = 0
        self.is_inside_now = false
        self.quality_score = 100.0

class RetestContinuationEngine:
    def __init__(self):
        self.registry: List[TrackedOrderBlockProfile] = []

    def register_new_order_block(self, symbol: str, timeframe: str, impulse: Dict[str, Any]):
        """Registers verified breakthrough order blocks into the running monitoring registry array."""
        # Enforce unique constraint matching per symbol frame tracking state
        for item in self.registry:
            if item.symbol == symbol and item.timeframe == timeframe and item.direction == impulse["direction"]:
                return
        self.registry.append(TrackedOrderBlockProfile(symbol, timeframe, impulse))

    def evaluate_live_market_states(self, symbol: str, timeframe: str, current_close: float) -> List[Dict[str, Any]]:
        """Processes state transitions over order flow revisits and updates live metrics scores."""
        dispatched_alerts = []
        targets = [b for b in self.registry if b.symbol == symbol and b.timeframe == timeframe]
        
        for ob in targets:
            inside_zone = ob.zone["bottom"] <= current_close <= ob.zone["top"]
            
            # State 1: Active Tracking Init Phase
            if ob.state == "ACTIVE":
                if ob.direction == "LONG" and current_close > ob.zone["top"]:
                    ob.state = "LEFT_ZONE"
                elif ob.direction == "SHORT" and current_close < ob.zone["bottom"]:
                    ob.state = "LEFT_ZONE"
                continue
                
            # State 2: Boundary Break Verification Lifecycle State Loop Execution Check
            if ob.state == "LEFT_ZONE":
                if inside_zone:
                    ob.retest_index += 1
                    ob.is_inside_now = True
                    ob.state = "RETESTED"
                    
                    # Update scores dynamically based on the retest index
                    if ob.retest_index == 1: ob.quality_score = 100.0
                    elif ob.retest_index == 2: ob.quality_score = 75.0
                    elif ob.retest_index == 3: ob.quality_score = 50.0
                    else:
                        ob.state = "INVALIDATED"
                        continue
                        
                    # Evaluate strict criteria for Killer tier qualification
                    killer_qualified = (
                        ob.mega_sqz and 
                        ob.sweep_detected and 
                        ob.expansion_score >= 80.0 and 
                        ob.oi_pct >= 2.0 and 
                        ob.retest_index == 1 and 
                        ob.htf_bias == ob.direction
                    )
                    
                    tier = "KILLER" if killer_qualified else ("HIGH" if ob.expansion_score >= 60.0 else "MEDIUM")
                    
                    dispatched_alerts.append({
                        "symbol": ob.symbol,
                        "timeframe": ob.timeframe,
                        "direction": ob.direction,
                        "tier": tier,
                        "quality_score": float(ob.quality_score),
                        "retest_index": int(ob.retest_index),
                        "zone": ob.zone,
                        "msg": "Institutional Order Block Retest Acceleration Rebound Triggered",
                        "timestamp": float(time.time())
                    })
                else:
                    # Check for invalidation via complete structural breach
                    if ob.direction == "LONG" and current_close < ob.zone["bottom"]:
                        ob.state = "INVALIDATED"
                    elif ob.direction == "SHORT" and current_close > ob.zone["top"]:
                        ob.state = "INVALIDATED"
                        
            # State 3: Inside Retest Range Track Processing Logic
            elif ob.state == "RETESTED":
                if not inside_zone:
                    # Price cleanly exited back out of the range zone
                    if ob.direction == "LONG" and current_close > ob.zone["top"]:
                        ob.state = "LEFT_ZONE"
                        ob.is_inside_now = False
                    elif ob.direction == "SHORT" and current_close < ob.zone["bottom"]:
                        ob.state = "LEFT_ZONE"
                        ob.is_inside_now = False
                    elif ob.direction == "LONG" and current_close < ob.zone["bottom"]:
                        ob.state = "INVALIDATED"
                    elif ob.direction == "SHORT" and current_close > ob.zone["top"]:
                        ob.state = "INVALIDATED"

        # Clean the active arrays to prevent historical index overflow processing traps
        self.registry = [b for b in self.registry if b.state != "INVALIDATED"]
        return dispatched_alerts
