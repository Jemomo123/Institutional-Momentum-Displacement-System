import streamlit as st
import pandas as pd
from engine import InstitutionalEngine

# Force clean, mobile-responsive dark styling
st.set_page_config(page_title="DISPLACEMENT_LIFECYCLE_V2", layout="centered")
st.markdown("""
    <style>
        body, .main, .block-container { background-color: #0b0e11 !important; color: #eaecef !important; font-family: 'Courier New', monospace; }
        h1, h2, h3 { color: #f0b90b !important; text-align: center; font-size: 1.1rem !important; }
        div[data-testid="stHtmlBlock"] table { background-color: #12161a !important; border-radius: 4px; padding: 5px; width: 100% !important; margin: 0 auto; }
        th { color: #848e9c !important; font-size: 0.75rem !important; text-transform: uppercase; border-bottom: 1px solid #2b3139 !important; }
        td { font-size: 0.8rem !important; padding: 8px !important; border-bottom: 1px dashed #2b3139 !important; }
        .badge-mega { background-color: #f0b90b; color: #000; padding: 2px 6px; font-weight: bold; border-radius: 3px; animation: blinker 1.5s linear infinite; }
        .badge-active { background-color: #f6465d; color: #fff; padding: 2px 6px; font-weight: bold; border-radius: 3px; }
        @keyframes blinker { 50% { opacity: 0; } }
    </style>
""", unsafe_allow_html=True)

st.title("⚡ JEREMIAH EDGE LIVE FEED MATRIX")

engine = InstitutionalEngine()
dashboard_rows = []
active_sources = set()

# Create a live placeholder text box right here for mobile tracking
progress_placeholder = st.empty()

# Use enumerate to count the items (1 to 25) as it scans
for index, symbol in enumerate(engine.watch_pool, start=1):
    # Dynamically update the phone screen with the active target item
    progress_placeholder.markdown(f"⏳ *Scanning Watchlist Item {index}/{len(engine.watch_pool)}:* **{symbol}**")
    
    tf_data = {}
    valid_token = True
    
    for tf in engine.timeframes:
        df, active_ex = engine.fetch_live_candles(symbol, tf)
        if df is not None:
            tf_data[tf] = engine.analyze_sequence(df)
            active_sources.add(active_ex.upper())
        else:
            valid_token = False
            break
            
    if not valid_token:
        continue
        
    is_mega = (tf_data["3m"]["sqz_status"] == "ALL TOGETHER" and 
               tf_data["5m"]["sqz_status"] == "ALL TOGETHER" and 
               tf_data["15m"]["sqz_status"] == "ALL TOGETHER")
    
    for tf in engine.timeframes:
        metrics = tf_data[tf]
        
        if is_mega:
            col1_output = '<span class="badge-mega">⚡ MEGA SQZ ⚡</span>'
        elif metrics["sqz_status"] == "ALL TOGETHER":
            col1_output = f"SQZ: {tf}"
        else:
            continue
            
        dashboard_rows.append({
            "COIN": f"<b style='color:#ffffff;'>{symbol.split(':')[0] if ':' in symbol else symbol}</b>",
            "Col 1: SQZ Status": col1_output,
            "Col 2: Expansion": metrics["expansion"],
            "Col 3: BOS Status": f"{tf} {metrics['bos_status']}" if metrics["bos_status"] != "NONE" else "NONE",
            "Col 4: OB Origin Zone": metrics["ob_zone"],
            "Col 5: Retest Status": f'<span class="badge-active">{metrics["retest_status"]}</span>' if "ACTIVE" in metrics["retest_status"] else metrics["retest_status"]
        })

# Clear out the scanning tracker text when execution completes so the screen stays clean
progress_placeholder.empty()

# Render final display table or scanning status message cleanly
if dashboard_rows:
    df_display = pd.DataFrame(dashboard_rows)
    st.write(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)
else:
    st.markdown("<p style='text-align:center;color:#848e9c;font-size:0.8rem;margin-top:2rem;'>Matrix Online. Scanning 25 asset vectors for independent squeeze clusters...</p>", unsafe_allow_html=True)
    
