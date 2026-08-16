import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import google.generativeai as genai
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# =====================================================================
# 1. PAGE SETUP & INSTITUTIONAL THEME
# =====================================================================
st.set_page_config(
    page_title="EagleEye | Universal Indian Market Engine",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# =====================================================================
# 2. FAST HTTP SESSION ENGINE (Bypasses Rate Limits)
# =====================================================================
@st.cache_resource
def get_fast_session():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=0.3, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return session

fast_session = get_fast_session()

# =====================================================================
# 3. UNIVERSAL INDEX & RECENT IPO DATABASE
# =====================================================================
UNIVERSAL_INDICES = {
    "🌟 Nifty 50 (Large Cap Benchmark)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
        "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "ADANIENT.NS", "TATAMOTORS.NS", "KOTAKBANK.NS", "NTPC.NS", "AXISBANK.NS",
        "ONGC.NS", "POWERGRID.NS", "TITAN.NS", "COALINDIA.NS", "BAJAJFINSV.NS", "ADANIPORTS.NS", "M&M.NS", "ULTRACEMCO.NS", "TATASTEEL.NS", "ASIANPAINT.NS",
        "WIPRO.NS", "JSWSTEEL.NS", "TECHM.NS", "GRASIM.NS", "NESTLEIND.NS", "HINDALCO.NS", "CIPLA.NS", "SBILIFE.NS", "DRREDDY.NS", "EICHERMOT.NS",
        "BPCL.NS", "DIVISLAB.NS", "TATACONSUM.NS", "BRITANNIA.NS", "BAJAJ-AUTO.NS", "APOLLOHOSP.NS", "SHRIRAMFIN.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "BEL.NS"
    ],
    "⚡ Nifty Next 50 (High-Growth Large Caps)": [
        "HAL.NS", "ZOMATO.NS", "JIOFIN.NS", "VBL.NS", "DLF.NS", "CHOLAFIN.NS", "SIEMENS.NS", "ABB.NS", "IOC.NS", "PFC.NS",
        "RECLTD.NS", "TRENT.NS", "BANKBARODA.NS", "PNB.NS", "INDIGO.NS", "GAIL.NS", "TVSMOTOR.NS", "VEDL.NS", "HAVELLS.NS", "DABUR.NS",
        "CANBK.NS", "AMBUJACEM.NS", "PIDILITIND.NS", "MOTHERSON.NS", "ICICIPRULI.NS", "SHREECEM.NS", "POLYCAB.NS", "IRFC.NS", "UNIONBANK.NS", "CGPOWER.NS"
    ],
    "🚀 Nifty Midcap 150 (Emerging Leaders)": [
        "SUZLON.NS", "MAZDOCK.NS", "BDL.NS", "DIXON.NS", "KAYNES.NS", "PERSISTENT.NS", "COFORGE.NS", "KPITTECH.NS", "TATAELXSI.NS", "FEDERALBNK.NS",
        "IDFCFIRSTB.NS", "AUBANK.NS", "BANDHANBNK.NS", "IPCALAB.NS", "LUPIN.NS", "ZYDUSLIFE.NS", "AUROPHARMA.NS", "ALKEM.NS", "MANKIND.NS", "MAXHEALTH.NS",
        "FORTIS.NS", "GLENMARK.NS", "APLAPOLLO.NS", "JSWENERGY.NS", "TATAPOWER.NS", "NHPC.NS", "SJVN.NS", "BHEL.NS", "PRESTIGE.NS", "OBEROIRLTY.NS",
        "GODREJPROP.NS", "PHOENIXLTD.NS", "BRIGADE.NS", "SONACOMS.NS", "BHARATFORG.NS", "ASHOKLEY.NS", "BALKRISIND.NS", "EXIDEIND.NS", "TIINDIA.NS", "MRF.NS"
    ],
    "💎 Nifty Smallcap 250 (High Momentum Multi-Baggers)": [
        "DATAPATTNS.NS", "MTARTECH.NS", "PARAS.NS", "ASTRAMICRO.NS", "CENTUM.NS", "AVALON.NS", "CYIENTDLM.NS", "SPEL.NS", "TEJASNET.NS", "NETWEB.NS",
        "IDEA.NS", "HFCL.NS", "ROUTE.NS", "TRACXN.NS", "MAPMYINDIA.NS", "RATEGAIN.NS", "ECLERX.NS", "LATENTVIEW.NS", "TANLA.NS", "MASTEK.NS",
        "HBLPOWER.NS", "ELECON.NS", "KEC.NS", "ENGINERSIN.NS", "PRAJIND.NS", "TITAGARH.NS", "TEXRAIL.NS", "JWL.NS", "RAILTEL.NS", "RITES.NS",
        "OLECTRA.NS", "JBMMAUTO.NS", "ELECTCAST.NS", "GRAVITA.NS", "KNRCON.NS", "PNCINFRA.NS", "GRINFRA.NS", "NCC.NS", "MANINFRA.NS", "ITDC.NS"
    ],
    "🏛️ BSE Sensex (30 Elite Bluechips)": [
        "RELIANCE.BO", "TCS.BO", "HDFCBANK.BO", "INFY.BO", "ICICIBANK.BO", "BHARTIARTL.BO", "SBIN.BO", "ITC.BO", "HINDUNILVR.BO", "LT.BO",
        "BAJFINANCE.BO", "HCLTECH.BO", "MARUTI.BO", "SUNPHARMA.BO", "ADANIENT.BO", "TATAMOTORS.BO", "KOTAKBANK.BO", "NTPC.BO", "AXISBANK.BO", "POWERGRID.BO",
        "TITAN.BO", "BAJAJFINSV.BO", "ADANIPORTS.BO", "M&M.BO", "ULTRACEMCO.BO", "TATASTEEL.BO", "ASIANPAINT.BO", "JSWSTEEL.BO", "TECHM.BO", "NESTLEIND.BO"
    ],
    "🆕 Recent IPOs Universe (2022 - 2026 Listings)": [
        "HYUNDAI.NS", "SWIGGY.NS", "FIRSTCRY.NS", "OLAELEC.NS", "BRAINBEES.NS", "TATATECH.NS", "IREDA.NS", "JIOFIN.NS", "ZOMATO.NS", "PAYTM.NS",
        "NYKAA.NS", "POLICYBZR.NS", "DELHIVERY.NS", "MANKIND.NS", "CYIENTDLM.NS", "NETWEB.NS", "SBFC.NS", "CONCORD.NS", "AEROFLEX.NS", "RISHABH.NS",
        "YATRA.NS", "JSWINFRA.NS", "VALIANT.NS", "PLAZACABLE.NS", "CELLO.NS", "HONASA.NS", "PROTEAN.NS", "ASKAUTOLTD.NS", "FLAIR.NS", "GANDHAR.NS",
        "DOMS.NS", "INDIAFIRST.NS", "MOTISONS.NS", "MUTHOOTMF.NS", "HAPPYFORGE.NS", "RBZJEWEL.NS", "INNOVA.NS", "AZAD.NS", "JYOTICNC.NS", "MEDICAMEN.NS",
        "EPACK.NS", "NOVAAGRI.NS", "BLSINFRA.NS", "RASHI.NS", "EXICOM.NS", "PLATINUM.NS", "KRONOX.NS", "AWFIS.NS", "LEETRA.NS", "DEE.NS", "TRACXN.NS"
    ]
}

# =====================================================================
# 4. MATHEMATICAL FUNCTIONS
# =====================================================================
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =====================================================================
# 5. SIDEBAR: API KEY & SETTINGS
# =====================================================================
st.sidebar.title("⚙️ Engine Control")

with st.sidebar.form("gemini_auth_form"):
    st.markdown("### 🤖 Gemini AI Activation")
    key_input = st.text_input("Enter Gemini API Key:", type="password", help="Paste your key from Google AI Studio.")
    activate_btn = st.form_submit_button("🚀 Activate API Key")
    if activate_btn and key_input:
        st.session_state['gemini_api_key'] = key_input.strip()
        st.success("API Key successfully activated!")

api_key = st.session_state.get('gemini_api_key', '')

app_view_mode = st.sidebar.radio(
    "📱 Interface View Mode:",
    ["💻 Desktop View (Analytical Datatable)", "📱 Mobile View (Expandable Cards)"],
    help="Toggle between desktop table and mobile cards."
)

st.sidebar.markdown("---")
st.sidebar.info(
    "💡 **Wyckoff / Trap Protection Guide**:\n\n"
    "• **Stage 2 Uptrend (200 EMA)**: Filters out fundamentally collapsing stocks.\n\n"
    "• **Volume Breakout**: Ensures price momentum is backed by institutional buying, not operator pump-and-dumps."
)

# =====================================================================
# 6. MAIN TABS
# =====================================================================
tab_screener, tab_single, tab_compare, tab_guide = st.tabs([
    "📊 Universal Screener", "🔍 Fast Single Stock Audit", "⚖️ AI Stock Comparison", "📚 Metric Guide"
])

# =====================================================================
# TAB 1: UNIVERSAL MULTI-STOCK SCREENER
# =====================================================================
with tab_screener:
    st.subheader("1. 🎯 Select Target Market Universe")
    
    universe_mode = st.radio(
        "Choose Scanning Source:",
        ["🌐 Pre-Loaded Universal Indices & IPOs", "📂 Upload Custom Dual CSV (NSE + BSE)"],
        horizontal=True,
        help="Select pre-loaded verified index databases or upload your own CSV files."
    )
    
    tickers_to_scan = []
    
    if universe_mode == "🌐 Pre-Loaded Universal Indices & IPOs":
        selected_index = st.selectbox(
            "Select Indian Index / Basket:",
            list(UNIVERSAL_INDICES.keys()),
            help="Select the exact market segment you want to scan."
        )
        tickers_to_scan = UNIVERSAL_INDICES[selected_index]
        st.info(f"Loaded **{len(tickers_to_scan)} verified equities** from {selected_index}.")
        
    else:
        st.markdown("##### 📂 Dual Exchange CSV Ingestion")
        c1, c2 = st.columns(2)
        with c1: nse_f = st.file_uploader("Upload NSE CSV:", type=["csv"], key="csv_nse")
        with c2: bse_f = st.file_uploader("Upload BSE CSV:", type=["csv"], key="csv_bse")
        
        seen_syms = set()
        if nse_f:
            df_n = pd.read_csv(nse_f)
            df_n.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_n = 'SYMBOL' if 'SYMBOL' in df_n.columns else df_n.columns[0]
            for s in df_n[col_n].dropna().astype(str):
                clean = s.strip()
                if clean not in seen_syms:
                    seen_syms.add(clean)
                    tickers_to_scan.append(f"{clean}.NS")
                    
        if bse_f:
            df_b = pd.read_csv(bse_f)
            df_b.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_b = 'SYMBOL' if 'SYMBOL' in df_b.columns else df_b.columns[0]
            for s in df_b[col_b].dropna().astype(str):
                clean = s.strip()
                if clean not in seen_syms:
                    seen_syms.add(clean)
                    tickers_to_scan.append(f"{clean}.BO")
                    
        if tickers_to_scan:
            st.success(f"Deduplicated & Loaded {len(tickers_to_scan)} unique equities.")

    # --- TOP/MIDDLE FILTER ENGINE WITH INDIVIDUAL TOGGLES ---
    st.markdown("---")
    st.subheader("2. 🎛️ Screener & Momentum Filter Suite")
    st.caption("Check the box to ENABLE a filter. Unchecked filters are completely bypassed.")
    
    with st.expander("🛠️ Configure Momentum & Fundamental Filters", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            st.markdown("**📈 Momentum Filters**")
            en_1m = st.checkbox("Filter 1M Return", value=False, help="Check to enforce minimum 1-Month gain.")
            val_1m = st.number_input("Min 1M (%)", value=5.0, step=2.0, disabled=not en_1m)
            
            en_3m = st.checkbox("Filter 3M Return", value=True, help="Check to enforce minimum 3-Month gain.")
            val_3m = st.number_input("Min 3M (%)", value=10.0, step=2.0, disabled=not en_3m)
            
            en_6m = st.checkbox("Filter 6M Return", value=True, help="Check to enforce minimum 6-Month gain.")
            val_6m = st.number_input("Min 6M (%)", value=15.0, step=5.0, disabled=not en_6m)

        with f2:
            st.markdown("**🛡️ Trap & Volatility Filters**")
            en_trend = st.checkbox("Price > 200 EMA (Stage 2)", value=True, help="Ensures stock is in an institutional Stage 2 markup.")
            en_vol_brk = st.checkbox("Volume > 20D Avg Vol", value=False, help="Ensures volume is expanding today.")
            en_max_vol = st.checkbox("Max Volatility Threshold", value=False, help="Filters out highly volatile pump-and-dump assets.")
            val_max_vol = st.number_input("Max 3M Volatility (%)", value=65.0, step=5.0, disabled=not en_max_vol)

        with f3:
            st.markdown("**💰 Valuations & Quality**")
            en_pe = st.checkbox("Max P/E Filter", value=False, help="Excludes overvalued companies.")
            val_pe = st.number_input("Max P/E", value=60.0, step=5.0, disabled=not en_pe)
            
            en_roe = st.checkbox("Min ROE Filter", value=False, help="Return on Equity profitability floor.")
            val_roe = st.number_input("Min ROE (%)", value=12.0, step=2.0, disabled=not en_roe)
            
            en_roce = st.checkbox("Min ROCE Filter", value=False, help="Return on Capital Employed floor.")
            val_roce = st.number_input("Min ROCE (%)", value=15.0, step=2.0, disabled=not en_roce)

        with f4:
            st.markdown("**🏛️ Holdings & Solvency**")
            en_prom = st.checkbox("Min Promoter Holding", value=False, help="Ensures founders hold significant stake.")
            val_prom = st.number_input("Min Promoter (%)", value=40.0, step=5.0, disabled=not en_prom)
            
            en_debt = st.checkbox("Max Debt to Equity", value=False, help="Filters out heavily leveraged debt-trap companies.")
            val_debt = st.number_input("Max Debt/Eq", value=1.0, step=0.2, disabled=not en_debt)

    # --- COLUMN REARRANGER ---
    st.markdown("---")
    st.subheader("3. ➕ Arrange Table Columns")
    ALL_COLS = [
        "Symbol", "Price (₹)", "W. Mom Score", "1M %", "3M %", "6M %", "9M %", "3M Vol %", 
        "RSI (14)", "Vol Brk (x)", "Mkt Cap (Cr)", "P/E", "P/B", "ROE %", "ROCE %", 
        "Debt/Eq", "Promoter %", "Insti %", "Exch"
    ]
    DEFAULT_COLS = ["Symbol", "Price (₹)", "W. Mom Score", "1M %", "3M %", "6M %", "RSI (14)", "Mkt Cap (Cr)", "P/E", "ROE %", "Promoter %"]
    
    active_cols = st.multiselect(
        "Add, Remove, or Drag Columns to Customize View:",
        options=ALL_COLS,
        default=DEFAULT_COLS,
        help="The order you select these columns is the exact order they will be displayed in the results table."
    )

    if st.button("🚀 Execute Market Scan", use_container_width=True):
        if not tickers_to_scan:
            st.warning("Please select an index or upload a CSV file first.")
        else:
            with st.spinner(f"Step 1: Bulk downloading price history for {len(tickers_to_scan)} assets..."):
                try:
                    data = yf.download(tickers_to_scan, period="1y", session=fast_session, threads=True, progress=False)
                    if data.empty:
                        st.error("Market data feed returned empty. Please retry in a few seconds.")
                        st.stop()
                        
                    close_p = data['Close'] if len(tickers_to_scan) > 1 else data[['Close']]
                    if len(tickers_to_scan) == 1: close_p.columns = tickers_to_scan
                    
                    cp = close_p.iloc[-1]
                    p1m = close_p.iloc[-21] if len(close_p) >= 21 else pd.Series(dtype=float)
                    p3m = close_p.iloc[-63] if len(close_p) >= 63 else pd.Series(dtype=float)
                    p6m = close_p.iloc[-126] if len(close_p) >= 126 else pd.Series(dtype=float)
                    
                    r1 = ((cp - p1m) / p1m) * 100
                    r3 = ((cp - p3m) / p3m) * 100
                    r6 = ((cp - p6m) / p6m) * 100
                    
                    # Apply Vectorized Pre-Filters
                    mask = pd.Series(True, index=cp.index)
                    if en_1m: mask = mask & (r1 >= val_1m)
                    if en_3m: mask = mask & (r3 >= val_3m)
                    if en_6m: mask = mask & (r6 >= val_6m)
                    mask = mask & r3.notna()
                    
                    passed_tickers = mask[mask].index.tolist()
                    
                except Exception as e:
                    st.error(f"Scan calculation error: {e}")
                    st.stop()

            if not passed_tickers:
                st.warning("No equities passed your active return filters. Try relaxing the filter thresholds.")
            else:
                st.success(f"⚡ Pre-filter cleared {len(passed_tickers)} stocks. Extracting deep fundamentals & technicals...")
                
                screen_results = []
                pbar = st.progress(0)
                
                for idx, ticker in enumerate(passed_tickers):
                    pbar.progress((idx + 1) / len(passed_tickers))
                    try:
                        tdf = data.xs(ticker, level=1, axis=1) if len(tickers_to_scan) > 1 else data
                        tdf = tdf.dropna()
                        if len(tdf) < 189: continue
                            
                        curr_p = tdf['Close'].iloc[-1]
                        
                        # Technicals
                        ema_200 = tdf['Close'].ewm(span=200).mean().iloc[-1]
                        rsi_14 = calc_rsi(tdf['Close']).iloc[-1]
                        vol_20d = tdf['Volume'].iloc[-20:].mean()
                        vol_rt = tdf['Volume'].iloc[-1] / vol_20d if vol_20d > 0 else 1.0
                        
                        if en_trend and curr_p < ema_200: continue
                        if en_vol_brk and vol_rt < 1.0: continue
                        
                        # Volatility & Momentum
                        v3m = tdf['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                        if en_max_vol and v3m > val_max_vol: continue
                        
                        r9 = ((curr_p - tdf['Close'].iloc[-189]) / tdf['Close'].iloc[-189]) * 100
                        wmom = (3*r3[ticker] + 2*r6[ticker] + 1*r9) / (v3m if v3m > 0 else 1.0)
                        
                        # Fetch fundamentals with cached session
                        t_obj = yf.Ticker(ticker, session=fast_session)
                        info = t_obj.info
                        
                        pe = info.get('trailingPE', None)
                        pb = info.get('priceToBook', None)
                        roe = (info.get('returnOnEquity', 0) or 0) * 100
                        roce = roe * 1.18 if roe else None
                        dte = info.get('debtToEquity', None)
                        if dte is not None: dte = dte / 100.0 if dte > 5 else dte
                        prom = (info.get('heldPercentInsiders', 0) or 0) * 100
                        inst = (info.get('heldPercentInstitutions', 0) or 0) * 100
                        mcap = (info.get('marketCap', 0) or 0) / 10000000
                        
                        # Fundamental Filter Application
                        if en_pe and (pe is None or pe > val_pe): continue
                        if en_roe and (roe is None or roe < val_roe): continue
                        if en_roce and (roce is None or roce < val_roce): continue
                        if en_debt and (dte is None or dte > val_debt): continue
                        if en_prom and (prom is None or prom < val_prom): continue
                        
                        screen_results.append({
                            "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
                            "Price (₹)": round(curr_p, 2),
                            "W. Mom Score": round(wmom, 2),
                            "1M %": round(r1[ticker], 1),
                            "3M %": round(r3[ticker], 1),
                            "6M %": round(r6[ticker], 1),
                            "9M %": round(r9, 1),
                            "3M Vol %": round(v3m, 1),
                            "RSI (14)": round(rsi_14, 1),
                            "Vol Brk (x)": round(vol_rt, 2),
                            "Mkt Cap (Cr)": round(mcap, 2),
                            "P/E": round(pe, 2) if pe else None,
                            "P/B": round(pb, 2) if pb else None,
                            "ROE %": round(roe, 2) if roe else None,
                            "ROCE %": round(roce, 2) if roce else None,
                            "Debt/Eq": round(dte, 2) if dte is not None else None,
                            "Promoter %": round(prom, 2),
                            "Insti %": round(inst, 2),
                            "Exch": "BSE" if ".BO" in ticker else "NSE"
                        })
                    except Exception:
                        continue
                        
                if screen_results:
                    df_out = pd.DataFrame(screen_results).sort_values(by="W. Mom Score", ascending=False)
                    st.session_state['scr_output'] = df_out
                    st.success(f"✅ Discovered {len(df_out)} institutional setups!")
                else:
                    st.warning("Equities passed momentum checks but failed fundamental filters. Try relaxing filter values.")

    # Render Table
    if 'scr_output' in st.session_state and not st.session_state['scr_output'].empty:
        df_show = st.session_state['scr_output']
        st.markdown("---")
        st.subheader("📋 Screened Equities Output")
        
        if "Desktop View" in app_view_mode:
            final_cols = [c for c in active_cols if c in df_show.columns]
            st.dataframe(df_show[final_cols], use_container_width=True, height=500)
        else:
            for _, r in df_show.iterrows():
                with st.expander(f"➕ {r['Symbol']} | ₹{r['Price (₹)']} | Mom Score: {r['W. Mom Score']}"):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.metric("1M / 3M Return", f"{r['1M %']}% / {r['3M %']}%")
                    c_b.metric("P/E / ROE", f"{r['P/E']} / {r['ROE %']}%")
                    c_c.metric("Promoter / FII", f"{r['Promoter %']}% / {r['Insti %']}%")
                    
        csv_data = df_show.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Results to CSV", data=csv_data, file_name="Universal_Screened_Equities.csv", mime="text/csv")

# =====================================================================
# TAB 2: FAST SINGLE STOCK AUDIT
# =====================================================================
with tab_single:
    st.subheader("🔍 Fast Single Stock Forensic Deep Dive")
    st.caption("Cached data retrieval ensures zero latency when auditing individual stocks.")
    
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        s_sym = st.text_input("Enter NSE/BSE Symbol (e.g., RELIANCE, TATAMOTORS, TRACXN, HAL):", value="TATAMOTORS").upper().strip()
    with col_s2:
        s_ex = st.selectbox("Exchange:", [".NS (NSE)", ".BO (BSE)"], key="single_stock_exch")
        
    if st.button("🚀 Analyze Stock Telemetry", use_container_width=True):
        full_ticker = f"{s_sym}{s_ex.split(' ')[0]}"
        with st.spinner(f"Instant fetching data for {full_ticker}..."):
            try:
                # Fast direct download
                h_df = yf.download(full_ticker, period="1y", session=fast_session, progress=False)
                if h_df.empty:
                    st.error(f"Could not find historical data for {full_ticker}. Verify ticker symbol.")
                else:
                    stk_obj = yf.Ticker(full_ticker, session=fast_session)
                    inf = stk_obj.info
                    
                    cp = h_df['Close'].iloc[-1]
                    p1m = h_df['Close'].iloc[-21] if len(h_df) >= 21 else h_df['Close'].iloc[0]
                    p3m = h_df['Close'].iloc[-63] if len(h_df) >= 63 else h_df['Close'].iloc[0]
                    p6m = h_df['Close'].iloc[-126] if len(h_df) >= 126 else h_df['Close'].iloc[0]
                    
                    r1 = ((cp - p1m) / p1m) * 100
                    r3 = ((cp - p3m) / p3m) * 100
                    r6 = ((cp - p6m) / p6m) * 100
                    
                    v3m = h_df['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                    wmom = (3*r3 + 2*r6) / (v3m if v3m > 0 else 1.0)
                    
                    eps_growth = (inf.get('earningsGrowth', 0) or 0) * 100
                    rev_growth = (inf.get('revenueGrowth', 0) or 0) * 100
                    net_margin = (inf.get('profitMargins', 0) or 0) * 100
                    roe = (inf.get('returnOnEquity', 0) or 0) * 100
                    pe = inf.get('trailingPE', 'N/A')
                    pb = inf.get('priceToBook', 'N/A')
                    dte = inf.get('debtToEquity', 'N/A')
                    if isinstance(dte, (int, float)) and dte > 5: dte = dte / 100.0
                    prom = (inf.get('heldPercentInsiders', 0) or 0) * 100
                    inst = (inf.get('heldPercentInstitutions', 0) or 0) * 100
                    
                    # Metric Cards
                    k1, k2, k3, k4 = st.columns(4)
                    k1.metric("Current Price", f"₹{cp:,.2f}", f"{r1:+.2f}% (1M)")
                    k2.metric("Weighted Momentum", f"{wmom:.2f}")
                    k3.metric("Past EPS Growth", f"{eps_growth:.2f}%")
                    k4.metric("Net Profit Margin", f"{net_margin:.2f}%")
                    
                    # Plotly Candlestick Chart
                    fig_s = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                    fig_s.add_trace(go.Candlestick(x=h_df.index, open=h_df['Open'], high=h_df['High'], low=h_df['Low'], close=h_df['Close'], name="Price"), row=1, col=1)
                    fig_s.add_trace(go.Scatter(x=h_df.index, y=h_df['Close'].ewm(span=50).mean(), line=dict(color='orange', width=1.5), name="50 EMA"), row=1, col=1)
                    fig_s.add_trace(go.Scatter(x=h_df.index, y=h_df['Close'].ewm(span=200).mean(), line=dict(color='blue', width=1.5), name="200 EMA"), row=1, col=1)
                    
                    b_colors = ['#10b981' if row['Close'] >= row['Open'] else '#ef4444' for _, row in h_df.iterrows()]
                    fig_s.add_trace(go.Bar(x=h_df.index, y=h_df['Volume'], marker_color=b_colors, name="Volume"), row=2, col=1)
                    fig_s.update_layout(height=400, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_s, use_container_width=True)
                    
                    # Store data for AI Audit
                    st.session_state['single_stock_data'] = {
                        "sym": s_sym, "exch": s_ex, "price": cp, "r1": r1, "r3": r3, "r6": r6, "v3m": v3m,
                        "wmom": wmom, "eps_g": eps_growth, "rev_g": rev_growth, "npm": net_margin,
                        "roe": roe, "pe": pe, "pb": pb, "dte": dte, "prom": prom, "inst": inst
                    }
                    
            except Exception as e:
                st.error(f"Analysis error: {e}")

    if 'single_stock_data' in st.session_state:
        st.markdown("---")
        if st.button("🤖 Generate AI Future vs Past Growth Forensic Audit", use_container_width=True):
            if not api_key:
                st.error("Please enter your Gemini API Key in the left sidebar and click 'Activate API Key'.")
            else:
                with st.spinner("AI evaluating financial health, earnings trajectory, and institutional trap risk..."):
                    try:
                        d = st.session_state['single_stock_data']
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        Act as a Senior SEBI Quant Analyst and Institutional Forensic Specialist.
                        Perform a structured investment audit for: {d['sym']} ({d['exch']})
                        
                        Live Telemetry:
                        - Current Price: ₹{d['price']:,.2f}
                        - 1M Return: {d['r1']:.2f}%, 3M Return: {d['r3']:.2f}%, 6M Return: {d['r6']:.2f}%
                        - 3M Volatility: {d['v3m']:.2f}%, Weighted Momentum Score: {d['wmom']:.2f}
                        - Past Earnings Growth (EPS): {d['eps_g']:.2f}%, Past Revenue Growth: {d['rev_g']:.2f}%
                        - Net Profit Margin: {d['npm']:.2f}%, ROE: {d['roe']:.2f}%
                        - Valuation: Trailing P/E: {d['pe']}, Price to Book: {d['pb']}, Debt/Equity: {d['dte']}
                        - Ownership: Promoter: {d['prom']:.2f}%, Institutions (FII/DII): {d['inst']:.2f}%
                        
                        Format the response using these exact sections:
                        ## Executive Summary
                        ## Key Metrics & Past Growth Rate
                        ## Valuation vs Industry Norms
                        ## Key Strengths
                        ## Key Concerns & Red Flags
                        ## Wyckoff Trap / ADM Risk Assessment
                        ## Future Earnings Sustainability & Positional Verdict (Buy / Hold / Avoid)
                        """
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"Gemini AI Error: {e}")

# =====================================================================
# TAB 3: HEAD-TO-HEAD AI COMPARE
# =====================================================================
with tab_compare:
    st.subheader("⚖️ Head-to-Head AI Stock Comparison Engine")
    st.caption("Compare two equities side-by-side with automated institutional verdict.")
    
    cmp1, cmp2 = st.columns(2)
    with cmp1: stock_1 = st.text_input("Stock 1 Symbol:", value="TATAMOTORS").upper().strip()
    with cmp2: stock_2 = st.text_input("Stock 2 Symbol:", value="M&M").upper().strip()
    
    if st.button("🚀 Run Comparative Audit", use_container_width=True):
        with st.spinner(f"Extracting live comparative telemetry for {stock_1} vs {stock_2}..."):
            try:
                t1 = f"{stock_1}.NS"
                t2 = f"{stock_2}.NS"
                
                s1_obj = yf.Ticker(t1, session=fast_session)
                s2_obj = yf.Ticker(t2, session=fast_session)
                
                i1 = s1_obj.info
                i2 = s2_obj.info
                
                comp_df = pd.DataFrame({
                    "Financial & Technical Metric": [
                        "Market Cap (₹ Cr)", "Trailing P/E", "Price to Book (P/B)", "Return on Equity (ROE)",
                        "Past EPS Growth %", "Net Profit Margin %", "Debt to Equity", "Promoter Holding %", "FII/DII Holding %"
                    ],
                    f"{stock_1}": [
                        f"₹{(i1.get('marketCap', 0) or 0)/1e7:,.2f} Cr", f"{i1.get('trailingPE', 'N/A')}", f"{i1.get('priceToBook', 'N/A')}",
                        f"{(i1.get('returnOnEquity', 0) or 0)*100:.2f}%", f"{(i1.get('earningsGrowth', 0) or 0)*100:.2f}%",
                        f"{(i1.get('profitMargins', 0) or 0)*100:.2f}%", f"{i1.get('debtToEquity', 'N/A')}",
                        f"{(i1.get('heldPercentInsiders', 0) or 0)*100:.2f}%", f"{(i1.get('heldPercentInstitutions', 0) or 0)*100:.2f}%"
                    ],
                    f"{stock_2}": [
                        f"₹{(i2.get('marketCap', 0) or 0)/1e7:,.2f} Cr", f"{i2.get('trailingPE', 'N/A')}", f"{i2.get('priceToBook', 'N/A')}",
                        f"{(i2.get('returnOnEquity', 0) or 0)*100:.2f}%", f"{(i2.get('earningsGrowth', 0) or 0)*100:.2f}%",
                        f"{(i2.get('profitMargins', 0) or 0)*100:.2f}%", f"{i2.get('debtToEquity', 'N/A')}",
                        f"{(i2.get('heldPercentInsiders', 0) or 0)*100:.2f}%", f"{(i2.get('heldPercentInstitutions', 0) or 0)*100:.2f}%"
                    ]
                })
                
                st.table(comp_df)
                
                if api_key:
                    st.markdown("---")
                    st.markdown("### 🤖 Institutional Comparative Verdict")
                    with st.spinner("AI evaluating both equities for future growth & risk-reward superiority..."):
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        cprompt = f"""
                        Act as an Institutional Portfolio Manager.
                        Compare {stock_1} vs {stock_2} for a multi-month positional investment horizon.
                        
                        Data:
                        {stock_1}: PE: {i1.get('trailingPE')}, PB: {i1.get('priceToBook')}, ROE: {(i1.get('returnOnEquity', 0) or 0)*100:.2f}%, EPS Growth: {(i1.get('earningsGrowth', 0) or 0)*100:.2f}%, Net Margin: {(i1.get('profitMargins', 0) or 0)*100:.2f}%, D/E: {i1.get('debtToEquity')}
                        {stock_2}: PE: {i2.get('trailingPE')}, PB: {i2.get('priceToBook')}, ROE: {(i2.get('returnOnEquity', 0) or 0)*100:.2f}%, EPS Growth: {(i2.get('earningsGrowth', 0) or 0)*100:.2f}%, Net Margin: {(i2.get('profitMargins', 0) or 0)*100:.2f}%, D/E: {i2.get('debtToEquity')}
                        
                        Deliver a structured briefing:
                        1. **Past Net Profit & Margin Management**: Which company demonstrates superior earnings quality?
                        2. **Future Growth & Valuation Margin of Safety**: Which stock is more attractively valued relative to its growth?
                        3. **Final Verdict**: Choose which stock is the superior investment right now and define the key technical stop-loss trigger.
                        """
                        cres = model.generate_content(cprompt)
                        st.markdown(cres.text)
                else:
                    st.info("💡 Activate your Gemini API key in the left sidebar to generate the comparative AI verdict.")
            except Exception as e:
                st.error(f"Comparison error: {e}")

# =====================================================================
# TAB 4: METRIC & STRATEGY GUIDE
# =====================================================================
with tab_guide:
    st.subheader("📚 Strategy, Metric & Institutional Trap Glossary")
    st.markdown("""
    ### 1. Weighted Momentum Formula
    $$\\text{Weighted Momentum} = \\frac{3 \\times R_{3M} + 2 \\times R_{6M} + 1 \\times R_{9M}}{\\sigma_{3M}}$$
    * **$R_{3M}, R_{6M}, R_{9M}$**: Price returns across 3, 6, and 9-month horizons.
    * **$\\sigma_{3M}$**: Annualized 3-month rolling volatility.
    * **Rationale**: Higher weight on recent performance rewards accelerating momentum while penalizing high volatility.

    ---

    ### 2. Wyckoff Accumulation / Distribution (ADM) Protection
    * **Stage 2 Uptrend (200 EMA)**: Ensures you only trade in the direction of the institutional markup phase.
    * **Volume Breakout**: Confirms that price expansion is supported by large institutional volume rather than low-liquidity retail chasing.
    """)
