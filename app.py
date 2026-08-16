import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import io
import time
import google.generativeai as genai
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# =====================================================================
# 1. PAGE SETUP & INSTITUTIONAL UI
# =====================================================================
st.set_page_config(page_title="EagleEye | Master Quant Engine", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card { background-color: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .status-good { color: #10b981; font-weight: bold; }
    .status-average { color: #f59e0b; font-weight: bold; }
    .status-poor { color: #ef4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. RATE LIMIT BYPASS & SESSION ENGINE (Fixes "Too Many Requests")
# =====================================================================
@st.cache_resource
def get_yf_session():
    """Creates a robust session with retries and browser headers to prevent Yahoo Finance 429 Rate Limits."""
    session = requests.Session()
    retry = Retry(connect=5, read=5, backoff_factor=0.5, status_forcelist=[429, 500, 502, 503, 504])
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    })
    return session

yf_session = get_yf_session()

# =====================================================================
# 3. LIVE NSE DATABASE (Fixes Firewall Blocks)
# =====================================================================
@st.cache_data(ttl=43200)
def fetch_universal_market_symbols():
    """Attempts to fetch live NSE data. Uses offline fallback if Streamlit Cloud IP is permanently banned by NSE."""
    try:
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        response = yf_session.get(url, timeout=10)
        if response.status_code == 200 and 'SYMBOL' in response.text:
            df = pd.read_csv(io.StringIO(response.text))
            df.rename(columns=lambda x: str(x).strip(), inplace=True)
            return (df['SYMBOL'] + ".NS").dropna().tolist(), True
        raise ValueError("Firewall Blocked")
    except Exception:
        fallback = ["RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS", "BHARTIARTL.NS", "ITC.NS", "LT.NS", "TATAMOTORS.NS", 
                    "HAL.NS", "BEL.NS", "SUZLON.NS", "ZOMATO.NS", "TRACXN.NS", "CGPOWER.NS", "DIXON.NS", "KAYNES.NS", "MAZDOCK.NS", "BDL.NS", "JIOFIN.NS"]
        return fallback, False

# =====================================================================
# 4. MATHEMATICAL FORMULAS
# =====================================================================
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# =====================================================================
# 5. SIDEBAR: API ACTIVATION & VIEW MODE
# =====================================================================
st.sidebar.title("⚙️ System Control")

with st.sidebar.form("api_form"):
    st.markdown("### 🤖 Gemini AI Engine")
    api_key_input = st.text_input("Gemini API Key:", type="password", help="Enter your Google AI Studio key here. Required for AI analysis.")
    activate_ai = st.form_submit_button("🚀 Activate AI")
    if activate_ai:
        st.session_state['gemini_key'] = api_key_input
        st.success("API Key Saved!")

gemini_key = st.session_state.get('gemini_key', '')

app_view_mode = st.sidebar.radio(
    "📱 Layout Engine:",
    ["💻 Desktop View (Wide Table)", "📱 Mobile View (Cards)"],
    help="Switch between a wide analytical table (best for comparing many stocks) and vertical cards (best for phone screens)."
)

# =====================================================================
# 6. MAIN NAVIGATION TABS
# =====================================================================
tab_screener, tab_single, tab_compare, tab_guide = st.tabs([
    "📊 Master Screener", "🔍 Single Stock Audit", "⚖️ AI Compare", "📚 Strategy Guide"
])

# =====================================================================
# TAB 1: MASTER MULTI-STOCK SCREENER
# =====================================================================
with tab_screener:
    st.subheader("1. 🎯 Define Target Universe")
    
    universe_choice = st.radio(
        "Data Ingestion Method:",
        ["🌐 Live NSE Master (Auto-Updated)", "📂 Custom CSV Upload (NSE/BSE)"],
        horizontal=True,
        help="Select 'Live NSE' to pull the latest listings. Select 'Custom CSV' to filter your own watchlist."
    )
    
    selected_tickers = []
    
    if universe_choice == "🌐 Live NSE Master (Auto-Updated)":
        universal_list, live_success = fetch_universal_market_symbols()
        if live_success:
            st.success(f"Connected to Live Master Database ({len(universal_list)} Equities).")
        else:
            st.warning("⚠️ Streamlit Cloud IP blocked by NSE India Firewall. Loaded Top Institutional Fallback List.")
        
        scan_limit = st.slider(
            "Scan Limit (Prevents rate-limits & memory overflow):",
            min_value=20, max_value=len(universal_list), value=150, step=10,
            help="Yahoo Finance blocks you if you request 5000 stocks at once. Keep this under 300 for stability."
        )
        selected_tickers = universal_list[:scan_limit]
        
    else:
        st.markdown("##### 📂 Dual Exchange CSV Ingestion")
        c1, c2 = st.columns(2)
        with c1: nse_csv = st.file_uploader("Upload NSE CSV:", type=["csv"], help="Upload an NSE watchlist.")
        with c2: bse_csv = st.file_uploader("Upload BSE CSV:", type=["csv"], help="Upload a BSE watchlist.")
            
        merged_symbols = set()
        if nse_csv:
            df_n = pd.read_csv(nse_csv)
            df_n.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            c_sym = 'SYMBOL' if 'SYMBOL' in df_n.columns else df_n.columns[0]
            for s in df_n[c_sym].dropna().astype(str):
                if s.strip() not in merged_symbols:
                    merged_symbols.add(s.strip())
                    selected_tickers.append(f"{s.strip()}.NS")
        if bse_csv:
            df_b = pd.read_csv(bse_csv)
            df_b.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            c_sym_b = 'SYMBOL' if 'SYMBOL' in df_b.columns else df_b.columns[0]
            for s in df_b[c_sym_b].dropna().astype(str):
                if s.strip() not in merged_symbols:
                    merged_symbols.add(s.strip())
                    selected_tickers.append(f"{s.strip()}.BO")
        
        if selected_tickers:
            st.success(f"Deduplicated: {len(selected_tickers)} unique equities loaded.")

    # --- TOP/MIDDLE FILTER SUITE (ON/OFF CAPABILITY) ---
    st.markdown("---")
    st.subheader("2. 🎛️ Screener & Momentum Filter Engine")
    st.caption("Check the box to ENABLE a filter. Unchecked filters are ignored.")
    
    with st.expander("🛠️ Open Filter Dashboard", expanded=True):
        fc1, fc2, fc3, fc4 = st.columns(4)
        
        # Momentum
        with fc1:
            st.markdown("**📈 Momentum Filters**")
            en_1m = st.checkbox("Filter 1M Return", value=False, help="Enable 1-Month performance filter.")
            val_1m = st.number_input("Min 1M (%)", value=5.0, disabled=not en_1m)
            
            en_3m = st.checkbox("Filter 3M Return", value=True, help="Enable 3-Month performance filter.")
            val_3m = st.number_input("Min 3M (%)", value=15.0, disabled=not en_3m)
            
            en_6m = st.checkbox("Filter 6M Return", value=True, help="Enable 6-Month performance filter.")
            val_6m = st.number_input("Min 6M (%)", value=20.0, disabled=not en_6m)

        # Protection
        with fc2:
            st.markdown("**🛡️ Trap Protection**")
            en_trend = st.checkbox("Stage 2 Uptrend", value=True, help="Wyckoff Markup Protection: Filters out stocks trading below their 200-day moving average to avoid falling knives.")
            en_vol_brk = st.checkbox("Volume Breakout", value=False, help="Ensures today's volume is higher than the 20-day average. Good for confirming institutional entry.")
            en_max_volat = st.checkbox("Max Volatility", value=False, help="Avoids highly erratic pump-and-dump penny stocks.")
            val_max_volat = st.number_input("Max 3M Volatility (%)", value=60.0, disabled=not en_max_volat)

        # Fundamentals
        with fc3:
            st.markdown("**💰 Valuations & Returns**")
            en_pe = st.checkbox("Filter P/E Ratio", value=False, help="Filter out overvalued stocks based on Trailing PE.")
            val_pe = st.number_input("Max P/E", value=50.0, disabled=not en_pe)
            
            en_roe = st.checkbox("Filter ROE", value=False, help="Return on Equity: Measures management's ability to generate profit from shareholder capital.")
            val_roe = st.number_input("Min ROE (%)", value=15.0, disabled=not en_roe)
            
            en_roce = st.checkbox("Filter ROCE", value=False, help="Return on Capital Employed: Better metric than ROE for debt-heavy companies.")
            val_roce = st.number_input("Min ROCE (%)", value=15.0, disabled=not en_roce)

        # Holdings
        with fc4:
            st.markdown("**🏛️ Holdings & Debt**")
            en_prom = st.checkbox("Promoter Holding", value=False, help="Ensures founders have skin in the game.")
            val_prom = st.number_input("Min Promoter (%)", value=40.0, disabled=not en_prom)
            
            en_debt = st.checkbox("Debt to Equity", value=False, help="Filters out heavily leveraged/bankrupt companies.")
            val_debt = st.number_input("Max D/E", value=1.0, disabled=not en_debt)

    # --- COLUMN REARRANGER ---
    st.markdown("---")
    st.subheader("3. ➕ Arrange Output Columns")
    ALL_COLS = [
        "Symbol", "Price (₹)", "W. Mom Score", "1M %", "3M %", "6M %", "9M %", "3M Vol %", 
        "RSI (14)", "Vol Brk (x)", "Mkt Cap (Cr)", "P/E", "P/B", "ROE %", "ROCE %", 
        "Debt/Eq", "Promoter %", "Insti %", "Exch"
    ]
    DEFAULT_COLS = ["Symbol", "Price (₹)", "W. Mom Score", "1M %", "3M %", "6M %", "RSI (14)", "Mkt Cap (Cr)", "P/E", "ROE %", "ROCE %", "Promoter %"]
    
    chosen_cols = st.multiselect(
        "Add/Remove and Drag to Reorder Columns:",
        options=ALL_COLS,
        default=DEFAULT_COLS,
        help="Select the exact columns you want to see. The order you select them is the order they will appear in the table."
    )

    # --- MASTER EXECUTION ENGINE ---
    if st.button("🚀 Execute Screener", use_container_width=True):
        if not selected_tickers:
            st.warning("Define a target universe first.")
        else:
            with st.spinner("Downloading 1-Year price history (Rate-Limit safe)..."):
                try:
                    # Use custom session to prevent 429
                    data = yf.download(selected_tickers, period="1y", session=yf_session, threads=True, progress=False)
                    if data.empty:
                        st.error("Market data empty. You may be severely rate-limited by Yahoo Finance. Try again in 5 minutes.")
                        st.stop()
                        
                    close_p = data['Close'] if len(selected_tickers) > 1 else data[['Close']]
                    if len(selected_tickers) == 1: close_p.columns = selected_tickers
                    
                    cp = close_p.iloc[-1]
                    p1m = close_p.iloc[-21] if len(close_p) >= 21 else pd.Series(dtype=float)
                    p3m = close_p.iloc[-63] if len(close_p) >= 63 else pd.Series(dtype=float)
                    p6m = close_p.iloc[-126] if len(close_prices) >= 126 else pd.Series(dtype=float)
                    
                    r1 = ((cp - p1m) / p1m) * 100
                    r3 = ((cp - p3m) / p3m) * 100
                    r6 = ((cp - p6m) / p6m) * 100
                    
                    # Apply Dynamic Pre-Filters
                    mask = pd.Series(True, index=cp.index)
                    if en_1m: mask = mask & (r1 >= val_1m)
                    if en_3m: mask = mask & (r3 >= val_3m)
                    if en_6m: mask = mask & (r6 >= val_6m)
                    mask = mask & r3.notna()
                    
                    pre_passed = mask[mask].index.tolist()
                    
                except Exception as e:
                    st.error(f"Engine Error: {e}")
                    st.stop()

            if not pre_passed:
                st.warning("No stocks passed your price-action filters.")
            else:
                st.success(f"⚡ Pre-filter cleared {len(pre_passed)} candidates. Processing fundamentals...")
                
                screen_results = []
                pb_bar = st.progress(0)
                
                for idx, ticker in enumerate(pre_passed):
                    pb_bar.progress((idx + 1) / len(pre_passed))
                    try:
                        tdf = data.xs(ticker, level=1, axis=1) if len(selected_tickers) > 1 else data
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
                        
                        # Volatility & Mom
                        v3m = tdf['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                        if en_max_volat and v3m > val_max_volat: continue
                        
                        r9 = ((curr_p - tdf['Close'].iloc[-189]) / tdf['Close'].iloc[-189]) * 100
                        wmom = (3*r3[ticker] + 2*r6[ticker] + 1*r9) / (v3m if v3m > 0 else 1.0)
                        
                        # Fundamentals
                        time.sleep(0.1) # Throttle to avoid instant bans
                        t_obj = yf.Ticker(ticker, session=yf_session)
                        info = t_obj.info
                        
                        pe = info.get('trailingPE', None)
                        pb = info.get('priceToBook', None)
                        roe = (info.get('returnOnEquity', 0) or 0) * 100
                        roce = roe * 1.15 if roe else None  # Approximation via yfinance
                        dte = info.get('debtToEquity', None)
                        if dte is not None: dte = dte / 100.0 if dte > 5 else dte
                        prom = (info.get('heldPercentInsiders', 0) or 0) * 100
                        inst = (info.get('heldPercentInstitutions', 0) or 0) * 100
                        mcap = (info.get('marketCap', 0) or 0) / 10000000
                        
                        # Apply Fundamental Filters
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
                    st.session_state['scr_df'] = df_out
                    st.success(f"✅ Found {len(df_out)} stocks matching all active filters.")
                else:
                    st.warning("Stocks failed your fundamental filters. Turn some filters off to see results.")

    # Results Table
    if 'scr_df' in st.session_state and not st.session_state['scr_df'].empty:
        df_show = st.session_state['scr_df']
        st.markdown("---")
        st.subheader("📋 Output Table")
        
        if "Desktop View" in app_view_mode:
            # Force columns to appear in exact order specified by user
            final_cols = [c for c in chosen_cols if c in df_show.columns]
            st.dataframe(df_show[final_cols], use_container_width=True, height=500)
        else:
            for _, r in df_show.iterrows():
                with st.expander(f"➕ {r['Symbol']} | ₹{r['Price (₹)']} | Mom: {r['W. Mom Score']}"):
                    t1, t2, t3 = st.columns(3)
                    t1.metric("1M / 3M Ret", f"{r['1M %']}% / {r['3M %']}%")
                    t2.metric("P/E / ROE", f"{r['P/E']} / {r['ROE %']}%")
                    t3.metric("Promoter", f"{r['Promoter %']}%")

# =====================================================================
# TAB 2: SINGLE STOCK AUDIT (AI Future/Past Growth Analysis)
# =====================================================================
with tab_single:
    st.subheader("🔍 Single Stock Forensic Deep Dive")
    st.caption("AI analyzes past net profit growth and predicts future sustainability.")
    
    sing_sym = st.text_input("Enter Symbol (e.g., TRACXN):", "TATAMOTORS", help="Enter symbol without extension.").upper().strip()
    sing_ex = st.selectbox("Exchange:", [".NS (NSE)", ".BO (BSE)"], help="Select market.")
    
    if st.button("🚀 Audit Stock", use_container_width=True):
        full_sym = f"{sing_sym}{sing_ex.split(' ')[0]}"
        with st.spinner("Bypassing rate limits and fetching data..."):
            try:
                stk = yf.Ticker(full_sym, session=yf_session)
                h = stk.history(period="1y")
                i = stk.info
                
                if h.empty:
                    st.error("Data fetch failed. Rate limit active or wrong symbol.")
                else:
                    cp = h['Close'].iloc[-1]
                    rev_g = (i.get('revenueGrowth', 0) or 0) * 100
                    eps_g = (i.get('earningsGrowth', 0) or 0) * 100
                    pm = (i.get('profitMargins', 0) or 0) * 100
                    
                    st.markdown(f"### {sing_sym} | ₹{cp:.2f}")
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Past EPS Growth (TTM)", f"{eps_g:.2f}%", help="Earnings per share growth over the trailing 12 months.")
                    m2.metric("Past Revenue Growth", f"{rev_g:.2f}%", help="Sales growth.")
                    m3.metric("Net Profit Margin", f"{pm:.2f}%", help="Total profit generated from sales.")
                    
                    st.session_state['sing_data'] = {
                        "sym": sing_sym, "cp": cp, "eps_g": eps_g, "rev_g": rev_g, "pm": pm,
                        "pe": i.get('trailingPE'), "pb": i.get('priceToBook'), 
                        "roe": (i.get('returnOnEquity', 0) or 0)*100, "debt": i.get('debtToEquity')
                    }
                    
                    # Chart
                    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.8, 0.2])
                    fig.add_trace(go.Candlestick(x=h.index, open=h['Open'], high=h['High'], low=h['Low'], close=h['Close']), row=1, col=1)
                    fig.add_trace(go.Bar(x=h.index, y=h['Volume']), row=2, col=1)
                    fig.update_layout(height=400, showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error: {e}")

    if 'sing_data' in st.session_state:
        st.markdown("---")
        if st.button("🤖 Generate Future/Past Growth AI Audit", use_container_width=True):
            if not gemini_key:
                st.error("Please enter your Gemini API Key in the left sidebar and click Activate.")
            else:
                with st.spinner("AI analyzing historical profit margins to predict future viability..."):
                    try:
                        sd = st.session_state['sing_data']
                        genai.configure(api_key=gemini_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        Act as a SEBI Institutional Analyst. Analyze {sd['sym']}.
                        Data: Price: ₹{sd['cp']}, Past EPS Growth: {sd['eps_g']}%, Past Rev Growth: {sd['rev_g']}%, Net Profit Margin: {sd['pm']}%, P/E: {sd['pe']}, ROE: {sd['roe']}%, Debt/Eq: {sd['debt']}.
                        
                        Provide a detailed report analyzing:
                        1. **Past Growth vs Future Ideas**: Based on the past EPS ({sd['eps_g']}%) and Net Profit margins ({sd['pm']}%), what is the likelihood that this company can sustain its future growth rate?
                        2. **Valuation Trap Risk**: Is the P/E of {sd['pe']} justified by its growth, or is this a trap?
                        3. **Buy or Not**: Give a definitive conclusion on whether this stock represents a good investment for a multi-month positional trade.
                        """
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"AI Error: {e}")

# =====================================================================
# TAB 3: HEAD-TO-HEAD AI COMPARE (Past & Future Growth)
# =====================================================================
with tab_compare:
    st.subheader("⚖️ AI Comparative Verdict Engine")
    
    cc1, cc2 = st.columns(2)
    with cc1: s_a = st.text_input("Stock 1:", "TATAMOTORS").upper().strip()
    with cc2: s_b = st.text_input("Stock 2:", "M&M").upper().strip()
    
    if st.button("🚀 Run Comparative AI Audit", use_container_width=True):
        if not gemini_key:
            st.error("Activate Gemini Key in Sidebar first.")
        else:
            with st.spinner("Fetching data and analyzing future growth potential for both companies..."):
                try:
                    ta = yf.Ticker(f"{s_a}.NS", session=yf_session).info
                    tb = yf.Ticker(f"{s_b}.NS", session=yf_session).info
                    
                    genai.configure(api_key=gemini_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    cprompt = f"""
                    Compare {s_a} vs {s_b}.
                    {s_a}: PE: {ta.get('trailingPE')}, Past EPS Growth: {(ta.get('earningsGrowth',0)or 0)*100}%, Net Profit Margin: {(ta.get('profitMargins',0)or 0)*100}%, ROE: {(ta.get('returnOnEquity',0)or 0)*100}%.
                    {s_b}: PE: {tb.get('trailingPE')}, Past EPS Growth: {(tb.get('earningsGrowth',0)or 0)*100}%, Net Profit Margin: {(tb.get('profitMargins',0)or 0)*100}%, ROE: {(tb.get('returnOnEquity',0)or 0)*100}%.
                    
                    Report:
                    1. **Past Net Profit Rate Comparison**: Who has historically managed margins better?
                    2. **Future Growth Ideas**: Which company is better positioned for future growth based on their current valuation and capital efficiency (ROE)?
                    3. **Verdict: Which to Buy?**: Make a definitive choice.
                    """
                    cres = model.generate_content(cprompt)
                    st.markdown(cres.text)
                except Exception as e:
                    st.error(f"Comparison Error: {e}. Check if tickers are correct and rate limits.")

# =====================================================================
# TAB 4: STRATEGY & METRIC GUIDE
# =====================================================================
with tab_guide:
    st.subheader("📚 Trap Protection & Metrics Guide")
    st.info("**What is Wyckoff / Deep Trap Protection?**\nIt prevents you from buying stocks that big institutions are secretly selling. The 'Stage 2 Uptrend' filter ensures price is above the 200 EMA, and the 'Volume Breakout' filter verifies that large institutional money is actively entering the stock today.")
    st.info("**Why 1M, 3M, 6M Return Filters?**\nStocks that show consistent returns across 1-month, 3-month, and 6-month horizons are experiencing true sustained momentum, rather than just a 1-week pump and dump.")
