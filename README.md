# 🔴 DISPLACEMENT_LIFECYCLE_V2

A real-time, institutional order-flow tracking scanner optimized for mobile browsers. The engine independently monitors asset timeframes across an interchangeable exchange network (Binance, OKX, MEXC, Gate.io) to detect high-probability market manipulation setups.

---

## ⚡ The 5-Step Order Flow Sequence

The dashboard is structured in a strict left-to-right 5-column assembly line to monitor the precise lifecycle of institutional capital:

### 1. Column 1: SQZ Status
Tracks tight market compression. A valid squeeze requires the **Price, 20 SMA, and 100 SMA to converge within 0.1%** of each other. 
* **Independent SQZ:** Discovered on single independent timeframes (`3m`, `5m`, or `15m`).
* **Compression Cluster:** Can be as tight as a **single candle** forming the 0.1% coil.
* **MEGA SQZ:** Triggered when the 0.1% "All Together" condition aligns across all three primary timeframes (`3m`, `5m`, and `15m`) simultaneously.

### 2. Column 2: Expansion
Monitors the sudden release of compressed energy. Validated immediately when the body of a breakout candle matches or exceeds a strict **1x** threshold of the average candle body size inside the squeeze cluster (The Elephant Bar).

### 3. Column 3: BOS Status (Break of Structure)
Filters out range chop and fakeouts. The expansion candle must aggressively break and close past the independent timeframe's recent swing high (Bullish BOS) or swing low (Bearish BOS) to confirm a local regime shift.

### 4. Column 4: OB Origin Zone
Traces the exact coordinate footprint of institutional entry. Identifies the price high/low boundaries of the origin candle (the last opposite close candle before the 1x expansion blast-off) where resting limit orders are sitting on the books.

### 5. Column 5: Retest Status
The ultimate trade execution window. Tracks the live interactions of market price with the identified Order Block boundaries:
* **`STALKING`**: Price is extending or hovering away from the structural zone.
* **`🔥 RETEST ACTIVE`**: Price has returned to actively tap the resting order block boundaries.
* **`TRIGGERED`**: Structural confirmation achieved inside the block; the continuation trade is live.

---

## 🛠️ Repository Architecture

* `engine.py` - Core mathematical processing, SMA deviations, cluster tracking, and sequence state logic.
* `app.py` - Light-weight Streamlit multi-timeframe dashboard compiler styled for Dark-UI mobile optimization.
* `requirements.txt` - Python module environment manifests (`streamlit`, `pandas`, `numpy`, `ccxt`).

---
*System Parameter Note: Timeframes operate 100% independently unless synchronized into a MEGA SQZ state. Special One (200 SMA) filters are currently disabled.*
