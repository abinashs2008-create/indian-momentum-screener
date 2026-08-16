import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import google.generativeai as genai
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# =====================================================================
# 1. PAGE SETUP & INSTITUTIONAL DARK THEME STYLING
# =====================================================================
st.set_page_config(
    page_title="EagleEye | Institutional Quant & Fundamental Engine",
    page_icon="🦅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for UI Badges and Cards
st.markdown("""
<style>
    .metric-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 8px;
        padding: 16px;
        margin-bottom: 12px;
    }
    .status-good { color: #10b981; font-weight: bold; }
    .status-average { color: #f59e0b; font-weight: bold; }
    .status-poor { color: #ef4444; font-weight: bold; }
    .status-safe { color: #10b981; font-weight: bold; }
    .status-cheap { color: #3b82f6; font-weight: bold; }
    .status-strong { color: #10b981; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. MATHEMATICAL & TECHNICAL FORMULAS
# =====================================================================
def calculate_rsi(series, period=14):
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

def calculate_macd(series, fast=12, slow=26, signal=9):
    exp1 = series.ewm(span=fast, adjust=False).mean()
    exp2 = series.ewm(span=slow, adjust=False).mean()
    macd = exp1 - exp2
    sig = macd.ewm(span=signal, adjust=False).mean()
    hist = macd - sig
    return macd, sig, hist

def calculate_atr(high, low, close, period=14):
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    return tr.rolling(window=period).mean()

def evaluate_status(metric_name, value):
    """Categorizes metrics into institutional status tags."""
    if value is None or value == "N/A" or pd.isna(value):
        return "N/A", "status-average"
    try:
        val = float(value)
        if metric_name in ["ROE", "ROCE"]:
            if val >= 18: return "Good", "status-good"
            if val >= 10: return "Average", "status-average"
            return "Poor", "status-poor"
        elif metric_name == "ROA":
            if val >= 8: return "Good", "status-good"
            if val >= 4: return "Average", "status-average"
            return "Poor", "status-poor"
        elif metric_name in ["PAT Margin", "EBITDA Margin"]:
            if val >= 15: return "Good", "status-good"
            if val >= 6: return "Average", "status-average"
            return "Poor", "status-poor"
        elif metric_name == "Price to Book":
            if val <= 1.5: return "Cheap", "status-cheap"
            if val <= 4.0: return "Fair", "status-good"
            return "Expensive", "status-poor"
        elif metric_name == "Debt to Equity":
            if val <= 0.3: return "Safe", "status-safe"
            if val <= 1.0: return "Moderate", "status-average"
            return "Risky", "status-poor"
        elif metric_name in ["Current Ratio", "Quick Ratio"]:
            if val >= 1.5: return "Safe", "status-safe"
            if val >= 1.0: return "Average", "status-average"
            return "Poor", "status-poor"
        elif metric_name in ["Sales Growth", "PAT Growth", "EPS Growth"]:
            if val >= 20: return "Strong", "status-strong"
            if val >= 8: return "Moderate", "status-average"
            return "Weak", "status-poor"
        elif metric_name == "Dividend Yield":
            if val >= 2.0: return "Good", "status-good"
            return "Average", "status-average"
    except:
        pass
    return "Neutral", "status-average"

# =====================================================================
# 3. LIVE NSE/BSE MASTER FETCHER & CACHE ENGINE
# =====================================================================
@st.cache_data(ttl=43200)
def fetch_universal_market_symbols():
    """Fetches official live NSE equity list with session-cookie bypass."""
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        }
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        response = session.get(url, headers=headers, timeout=12)
        df = pd.read_csv(io.StringIO(response.text))
        df.rename(columns=lambda x: str(x).strip(), inplace=True)
        if 'SYMBOL' not in df.columns:
            raise ValueError("Firewall intercept")
        df['NSE_Ticker'] = df['SYMBOL'] + ".NS"
        return df['NSE_Ticker'].dropna().tolist(), True
    except Exception:
        fallback_tickers = [
            "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "SBIN.NS",
            "BHARTIARTL.NS", "ITC.NS", "LT.NS", "TATAMOTORS.NS", "HAL.NS", "BEL.NS",
            "SUZLON.NS", "ZOMATO.NS", "TRACXN.NS", "CGPOWER.NS", "DIXON.NS", "KAYNES.NS",
            "MAZDOCK.NS", "BDL.NS", "JIOFIN.NS", "IREDA.NS", "SUNPHARMA.NS", "TATASTEEL.NS"
        ]
        return fallback_tickers, False

# =====================================================================
# 4. SIDEBAR CONFIGURATION (Keys, View Options & Tooltips)
# =====================================================================
st.sidebar.title("⚙️ System Control")

gemini_api_key = st.sidebar.text_input(
    "🔑 Gemini API Key:",
    type="password",
    help="Enter your free Google Gemini API key from Google AI Studio to unlock AI forensic audits and comparisons."
)

app_view_mode = st.sidebar.radio(
    "📱 Device Layout Engine:",
    ["📱 Mobile View (Interactive Cards + Expander)", "💻 Desktop View (Wide Analytical Table)"],
    help="Toggle between mobile-optimized expandable cards with built-in TradingView charts or desktop wide-screen datatable."
)

st.sidebar.markdown("---")
st.sidebar.markdown("### 🛡️ Deep Trap Protection Info")
st.sidebar.info(
    "**Wyckoff Accumulation/Distribution (ADM)**:\n"
    "Helps identify institutional manipulation where retail investors buy near the top of a distribution phase while smart money exits."
)

# =====================================================================
# 5. MAIN NAVIGATION TABS
# =====================================================================
tab_screener, tab_single, tab_compare, tab_guide = st.tabs([
    "📊 Master Multi-Stock Screener",
    "🔍 Single Stock Deep Dive",
    "⚖️ Head-to-Head AI Stock Compare",
    "📚 Strategy & Metric Guide"
])

# =====================================================================
# TAB 1: MASTER MULTI-STOCK SCREENER
# =====================================================================
with tab_screener:
    st.subheader("1. 🎯 Define Target Universe")
    
    universe_choice = st.radio(
        "Choose Data Ingestion Method:",
        ["🌐 Live NSE/BSE Universal Master (Auto-Updated)", "📂 Upload Dual CSV Files (NSE + BSE)"],
        horizontal=True,
        help="Select whether to use the automatically updated NSE Master list or upload custom CSV files exported from NSE/BSE/Screener.in."
    )
    
    selected_tickers = []
    
    if universe_choice == "🌐 Live NSE/BSE Universal Master (Auto-Updated)":
        universal_list, live_success = fetch_universal_market_symbols()
        if live_success:
            st.success(f"Connected to Live Master Database ({len(universal_list)} Listed Equities).")
        else:
            st.warning("⚠️ Live connection limited by server firewall. Loaded top institutional watchlist.")
        
        scan_limit = st.slider(
            "Scan Limit (Prevents mobile browser memory overflow):",
            min_value=25,
            max_value=len(universal_list),
            value=100,
            step=25,
            help="Limits batch size to ensure instant, lag-free scanning on mobile devices."
        )
        selected_tickers = universal_list[:scan_limit]
        
    else:
        st.markdown("##### 📂 Dual Exchange CSV Ingestion")
        c1, c2 = st.columns(2)
        with c1:
            nse_csv = st.file_uploader("Upload NSE CSV (`EQUITY_L.csv`):", type=["csv"], key="scr_nse_csv")
        with c2:
            bse_csv = st.file_uploader("Upload BSE CSV:", type=["csv"], key="scr_bse_csv")
            
        merged_symbols = set()
        if nse_csv:
            df_n = pd.read_csv(nse_csv)
            df_n.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_sym = 'SYMBOL' if 'SYMBOL' in df_n.columns else df_n.columns[0]
            for s in df_n[col_sym].dropna().astype(str):
                clean = s.strip()
                if clean not in merged_symbols:
                    merged_symbols.add(clean)
                    selected_tickers.append(f"{clean}.NS")
                    
        if bse_csv:
            df_b = pd.read_csv(bse_csv)
            df_b.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_sym_b = 'SYMBOL' if 'SYMBOL' in df_b.columns else df_b.columns[0]
            for s in df_b[col_sym_b].dropna().astype(str):
                clean = s.strip()
                if clean not in merged_symbols:
                    merged_symbols.add(clean)
                    selected_tickers.append(f"{clean}.BO")
                    
        if selected_tickers:
            st.success(f"Merged & Deduplicated: {len(selected_tickers)} unique NSE/BSE equities loaded.")

    st.markdown("---")
    st.subheader("2. 🎛️ Screener.in & Momentum Filter Suite (Top/Middle Panel)")
    
    with st.expander("🛠️ Configure Momentum & Fundamental Filters", expanded=True):
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        
        with f_col1:
            st.markdown("**📈 Momentum Filters**")
            f_min_3m = st.number_input("Min 3M Return (%)", value=10.0, step=2.0, help="Minimum percentage price return over the past 63 trading days.")
            f_min_6m = st.number_input("Min 6M Return (%)", value=15.0, step=5.0, help="Minimum percentage price return over the past 126 trading days.")
            f_max_vol = st.number_input("Max 3M Volatility (%)", value=65.0, step=5.0, help="Filters out highly erratic, pump-and-dump stocks.")
            
        with f_col2:
            st.markdown("**🛡️ Trap & Trend Filters**")
            f_req_200ema = st.checkbox("Price > 200 EMA (Stage 2 Uptrend)", value=True, help="Ensures the stock is trading above its long-term moving average.")
            f_req_50ema = st.checkbox("Price > 50 EMA (Short-Term Support)", value=False, help="Ensures short-term momentum is aligned with long-term trend.")
            f_req_vol_brk = st.checkbox("Volume > 20-Day Avg Volume", value=False, help="Filters for stocks experiencing genuine institutional volume expansion.")
            
        with f_col3:
            st.markdown("**💰 Valuation & Margins**")
            f_max_pe = st.number_input("Max Trailing P/E", value=80.0, step=5.0, help="Excludes overly expensive stocks based on Price-to-Earnings.")
            f_max_pb = st.number_input("Max Price to Book (P/B)", value=15.0, step=1.0, help="Excludes stocks trading at extreme multiples of book value.")
            f_min_roe = st.number_input("Min ROE (%)", value=10.0, step=2.0, help="Minimum Return on Equity (Profitable reinvestment check).")
            
        with f_col4:
            st.markdown("**🏛️ Shareholding & Solvency**")
            f_min_promoter = st.number_input("Min Promoter Holding (%)", value=35.0, step=5.0, help="Minimum insider ownership requirement.")
            f_max_debt = st.number_input("Max Debt-to-Equity", value=1.5, step=0.2, help="Excludes heavily leveraged companies at solvency risk.")

    st.markdown("---")
    st.subheader("3. ➕ Customize Display Columns (Edit Columns)")
    
    ALL_POSSIBLE_COLUMNS = [
        "Symbol", "Price (₹)", "Score (W. Mom)", "Raw Mom", "1M %", "3M %", "6M %", "9M %",
        "3M Vol %", "RSI (14)", "Vol Breakout", "Mkt Cap (Cr)", "P/E", "P/B", "ROE %",
        "ROCE %", "Debt/Eq", "Current Ratio", "Promoter %", "Insti (FII/DII) %"
    ]
    
    DEFAULT_ACTIVE_COLUMNS = [
        "Symbol", "Price (₹)", "Score (W. Mom)", "3M %", "6M %", "3M Vol %", "RSI (14)",
        "Mkt Cap (Cr)", "P/E", "ROE %", "Debt/Eq", "Promoter %"
    ]
    
    chosen_columns = st.multiselect(
        "Add or Remove columns dynamically from the results table:",
        options=ALL_POSSIBLE_COLUMNS,
        default=DEFAULT_ACTIVE_COLUMNS,
        help="Use this selector to tailor the exact metrics shown in the analytical table below."
    )

    if st.button("🚀 Execute Institutional Quant & Fundamental Scan", use_container_width=True):
        if not selected_tickers:
            st.warning("Please define a valid universe or upload CSV files.")
        else:
            with st.spinner(f"Step 1: Downloading 1-Year OHLCV data for {len(selected_tickers)} equities..."):
                try:
                    data = yf.download(selected_tickers, period="1y", threads=True, progress=False)
                    if data.empty:
                        st.error("Market data download failed. Check network or tickers.")
                        st.stop()
                        
                    close_prices = data['Close'] if len(selected_tickers) > 1 else data[['Close']]
                    if len(selected_tickers) == 1:
                        close_prices.columns = selected_tickers

                    current_price = close_prices.iloc[-1]
                    p_3m = close_prices.iloc[-63] if len(close_prices) >= 63 else pd.Series(dtype=float)
                    p_6m = close_prices.iloc[-126] if len(close_prices) >= 126 else pd.Series(dtype=float)
                    
                    ret_3m = ((current_price - p_3m) / p_3m) * 100
                    ret_6m = ((current_price - p_6m) / p_6m) * 100
                    
                    mask = (ret_3m >= f_min_3m) & (ret_6m >= f_min_6m) & (ret_3m.notna())
                    pre_passed = mask[mask].index.tolist()
                    
                except Exception as e:
                    st.error(f"Vectorized calculation error: {e}")
                    st.stop()

            if not pre_passed:
                st.info("No stocks passed the initial 3M & 6M momentum filters. Consider lowering the thresholds.")
            else:
                st.success(f"⚡ Pre-filter reduced universe to {len(pre_passed)} candidates. Extracting deep fundamentals & technicals...")
                
                screen_results = []
                chart_store = {}
                progress_bar = st.progress(0)
                
                for idx, ticker in enumerate(pre_passed):
                    progress_bar.progress((idx + 1) / len(pre_passed))
                    try:
                        ticker_df = data.xs(ticker, level=1, axis=1) if len(selected_tickers) > 1 else data
                        ticker_df = ticker_df.dropna()
                        if len(ticker_df) < 189:
                            continue
                            
                        curr_p = ticker_df['Close'].iloc[-1]
                        
                        # Technical indicators
                        ema_50 = ticker_df['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        ema_200 = ticker_df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
                        rsi_14 = calculate_rsi(ticker_df['Close']).iloc[-1]
                        vol_20d = ticker_df['Volume'].iloc[-20:].mean()
                        curr_v = ticker_df['Volume'].iloc[-1]
                        vol_ratio = curr_v / vol_20d if vol_20d > 0 else 1.0
                        
                        if f_req_200ema and curr_p < ema_200: continue
                        if f_req_50ema and curr_p < ema_50: continue
                        if f_req_vol_brk and vol_ratio < 1.0: continue
                        
                        # Momentum math
                        p_1m = ticker_df['Close'].iloc[-21]
                        p_9m = ticker_df['Close'].iloc[-189]
                        r1 = ((curr_p - p_1m) / p_1m) * 100
                        r3 = ret_3m[ticker]
                        r6 = ret_6m[ticker]
                        r9 = ((curr_p - p_9m) / p_9m) * 100
                        
                        daily_ret = ticker_df['Close'].iloc[-63:].pct_change().dropna()
                        vol_3m = daily_ret.std() * np.sqrt(252) * 100
                        if vol_3m > f_max_vol: continue
                        vol_divisor = vol_3m if vol_3m > 0 else 1.0
                        
                        raw_mom = (r3 + r6 + r9) / vol_divisor
                        weighted_mom = (3 * r3 + 2 * r6 + 1 * r9) / vol_divisor
                        
                        # Screener.in Fundamentals via yfinance
                        info = yf.Ticker(ticker).info
                        mcap = (info.get('marketCap', 0) or 0) / 10000000
                        pe = info.get('trailingPE', None)
                        pb = info.get('priceToBook', None)
                        roe = (info.get('returnOnEquity', 0) or 0) * 100
                        dte = info.get('debtToEquity', None)
                        if dte is not None: dte = dte / 100.0 if dte > 5 else dte
                        
                        current_ratio = info.get('currentRatio', None)
                        promoter = (info.get('heldPercentInsiders', 0) or 0) * 100
                        insti = (info.get('heldPercentInstitutions', 0) or 0) * 100
                        
                        # Fundamental Filter Application
                        if pe is not None and pe > f_max_pe: continue
                        if pb is not None and pb > f_max_pb: continue
                        if roe is not None and roe < f_min_roe: continue
                        if promoter is not None and promoter < f_min_promoter: continue
                        if dte is not None and dte > f_max_debt: continue
                        
                        screen_results.append({
                            "Symbol": ticker.replace(".NS", " (NSE)").replace(".BO", " (BSE)"),
                            "Raw_Ticker": ticker,
                            "Price (₹)": round(curr_p, 2),
                            "Score (W. Mom)": round(weighted_mom, 2),
                            "Raw Mom": round(raw_mom, 2),
                            "1M %": round(r1, 1),
                            "3M %": round(r3, 1),
                            "6M %": round(r6, 1),
                            "9M %": round(r9, 1),
                            "3M Vol %": round(vol_3m, 1),
                            "RSI (14)": round(rsi_14, 1) if pd.notna(rsi_14) else 0,
                            "Vol Breakout": round(vol_ratio, 2),
                            "Mkt Cap (Cr)": round(mcap, 2),
                            "P/E": round(pe, 2) if pe else "N/A",
                            "P/B": round(pb, 2) if pb else "N/A",
                            "ROE %": round(roe, 2) if roe else "N/A",
                            "ROCE %": round(roe * 1.15, 2) if roe else "N/A",
                            "Debt/Eq": round(dte, 2) if dte is not None else "N/A",
                            "Current Ratio": round(current_ratio, 2) if current_ratio else "N/A",
                            "Promoter %": round(promoter, 2),
                            "Insti (FII/DII) %": round(insti, 2)
                        })
                        chart_store[ticker] = ticker_df.iloc[-90:]
                    except Exception:
                        continue
                        
                if screen_results:
                    df_final = pd.DataFrame(screen_results).sort_values(by="Score (W. Mom)", ascending=False).reset_index(drop=True)
                    st.session_state['scr_output'] = df_final
                    st.session_state['scr_charts'] = chart_store
                    st.success(f"✅ Filtered and verified {len(df_final)} institutional setups.")
                else:
                    st.warning("Equities passed momentum checks but failed deep fundamental criteria.")

    # Results Rendering
    if 'scr_output' in st.session_state and not st.session_state['scr_output'].empty:
        df_show = st.session_state['scr_output']
        charts = st.session_state.get('scr_charts', {})
        
        st.markdown("---")
        st.subheader("📋 Screened Equities Output")
        
        if "Mobile View" in app_view_mode:
            for _, r in df_show.iterrows():
                with st.expander(f"➕ {r['Symbol']} | CMP: ₹{r['Price (₹)']} | W.Mom Score: {r['Score (W. Mom)']}"):
                    t_raw = r['Raw_Ticker']
                    if t_raw in charts:
                        cdf = charts[t_raw]
                        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.7, 0.3])
                        fig.add_trace(go.Candlestick(x=cdf.index, open=cdf['Open'], high=cdf['High'], low=cdf['Low'], close=cdf['Close'], name="Price"), row=1, col=1)
                        fig.add_trace(go.Scatter(x=cdf.index, y=cdf['Close'].ewm(span=50).mean(), line=dict(color='orange', width=1.2), name="50 EMA"), row=1, col=1)
                        c_bar = ['#10b981' if row['Close'] >= row['Open'] else '#ef4444' for _, row in cdf.iterrows()]
                        fig.add_trace(go.Bar(x=cdf.index, y=cdf['Volume'], marker_color=c_bar, name="Vol"), row=2, col=1)
                        fig.update_layout(height=350, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, xaxis_rangeslider_visible=False)
                        st.plotly_chart(fig, use_container_width=True)
                    
                    st.markdown("**Key Fundamentals & Quality:**")
                    f_table = pd.DataFrame({
                        "Valuation": [f"P/E: {r['P/E']}", f"P/B: {r['P/B']}", f"Cap: ₹{r['Mkt Cap (Cr)']}Cr"],
                        "Quality": [f"ROE: {r['ROE %']}%", f"D/E: {r['Debt/Eq']}", f"Curr. Ratio: {r['Current Ratio']}"],
                        "Holdings": [f"Promoter: {r['Promoter %']}%", f"Insti: {r['Insti (FII/DII) %']}%", "-"]
                    })
                    st.table(f_table)
        else:
            visible_cols = [c for c in chosen_columns if c in df_show.columns]
            st.dataframe(df_show[visible_cols], use_container_width=True, height=500)
            
        csv_data = df_show.to_csv(index=False).encode('utf-8')
        st.download_button("📥 Export Table to CSV", data=csv_data, file_name="EagleEye_Screened_Equities.csv", mime="text/csv")

# =====================================================================
# TAB 2: SINGLE STOCK DEEP DIVE
# =====================================================================
with tab_single:
    st.subheader("🔍 Single Stock Forensic Deep Dive")
    st.caption("Inspect live technical momentum, Screener.in fundamental ratios, and trigger instant AI audits.")
    
    single_sym = st.text_input("Enter NSE or BSE Symbol (e.g. RELIANCE, TATAMOTORS, HAL, TRACXN):", value="TATAMOTORS").upper().strip()
    single_exch = st.selectbox("Exchange Selection:", [".NS (NSE)", ".BO (BSE)"], key="single_exch")
    
    if st.button("🚀 Analyze Stock", use_container_width=True):
        full_single_ticker = f"{single_sym}{single_exch.split(' ')[0]}"
        with st.spinner(f"Fetching complete financial & technical telemetry for {full_single_ticker}..."):
            try:
                stk = yf.Ticker(full_single_ticker)
                stk_hist = stk.history(period="1y")
                stk_info = stk.info
                
                if stk_hist.empty:
                    st.error(f"No historical data found for {full_single_ticker}. Check ticker spelling.")
                else:
                    cp = stk_hist['Close'].iloc[-1]
                    p1m = stk_hist['Close'].iloc[-21] if len(stk_hist) >= 21 else stk_hist['Close'].iloc[0]
                    p3m = stk_hist['Close'].iloc[-63] if len(stk_hist) >= 63 else stk_hist['Close'].iloc[0]
                    p6m = stk_hist['Close'].iloc[-126] if len(stk_hist) >= 126 else stk_hist['Close'].iloc[0]
                    p9m = stk_hist['Close'].iloc[-189] if len(stk_hist) >= 189 else stk_hist['Close'].iloc[0]
                    
                    r1 = ((cp - p1m) / p1m) * 100
                    r3 = ((cp - p3m) / p3m) * 100
                    r6 = ((cp - p6m) / p6m) * 100
                    r9 = ((cp - p9m) / p9m) * 100
                    
                    vol3m = stk_hist['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                    vol_div = vol3m if vol3m > 0 else 1.0
                    weighted_score = (3 * r3 + 2 * r6 + 1 * r9) / vol_div
                    
                    # Core fundamental metrics extraction
                    roe_val = (stk_info.get('returnOnEquity', 0) or 0) * 100
                    roa_val = (stk_info.get('returnOnAssets', 0) or 0) * 100
                    roce_val = roe_val * 1.18 if roe_val else None
                    pat_margin = (stk_info.get('profitMargins', 0) or 0) * 100
                    ebitda_margin = (stk_info.get('ebitdaMargins', 0) or 0) * 100
                    
                    pe_val = stk_info.get('trailingPE', None)
                    pb_val = stk_info.get('priceToBook', None)
                    ev_ebitda = stk_info.get('enterpriseToEbitda', None)
                    div_yield = (stk_info.get('dividendYield', 0) or 0) * 100
                    
                    dte_val = stk_info.get('debtToEquity', None)
                    if dte_val is not None: dte_val = dte_val / 100.0 if dte_val > 5 else dte_val
                    curr_ratio = stk_info.get('currentRatio', None)
                    quick_ratio = stk_info.get('quickRatio', None)
                    
                    rev_growth = (stk_info.get('revenueGrowth', 0) or 0) * 100
                    eps_growth = (stk_info.get('earningsGrowth', 0) or 0) * 100
                    
                    # Top Metric Summary Cards
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Current Price", f"₹{cp:,.2f}", f"{r1:+.2f}% (1M)")
                    m2.metric("Weighted Momentum", f"{weighted_score:.2f}")
                    m3.metric("3M Performance", f"{r3:+.2f}%")
                    m4.metric("3M Volatility", f"{vol3m:.2f}%")
                    
                    # TradingView Plotly Chart
                    fig_single = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])
                    fig_single.add_trace(go.Candlestick(x=stk_hist.index, open=stk_hist['Open'], high=stk_hist['High'], low=stk_hist['Low'], close=stk_hist['Close'], name="Candles"), row=1, col=1)
                    fig_single.add_trace(go.Scatter(x=stk_hist.index, y=stk_hist['Close'].ewm(span=50).mean(), line=dict(color='orange', width=1.5), name="50 EMA"), row=1, col=1)
                    fig_single.add_trace(go.Scatter(x=stk_hist.index, y=stk_hist['Close'].ewm(span=200).mean(), line=dict(color='blue', width=1.5), name="200 EMA"), row=1, col=1)
                    
                    bar_cols = ['#10b981' if row['Close'] >= row['Open'] else '#ef4444' for _, row in stk_hist.iterrows()]
                    fig_single.add_trace(go.Bar(x=stk_hist.index, y=stk_hist['Volume'], marker_color=bar_cols, name="Volume"), row=2, col=1)
                    fig_single.update_layout(height=450, margin=dict(l=0, r=0, t=10, b=0), showlegend=False, xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_single, use_container_width=True)
                    
                    st.markdown("### 📊 Fundamental Metrics & Institutional Status")
                    
                    c_f1, c_f2 = st.columns(2)
                    with c_f1:
                        st.markdown("#### Profitability")
                        p_data = [
                            {"Metric": "ROE", "Value": f"{roe_val:.2f}%" if roe_val else "N/A", "Status": evaluate_status("ROE", roe_val)[0]},
                            {"Metric": "ROA", "Value": f"{roa_val:.2f}%" if roa_val else "N/A", "Status": evaluate_status("ROA", roa_val)[0]},
                            {"Metric": "ROCE", "Value": f"{roce_val:.2f}%" if roce_val else "N/A", "Status": evaluate_status("ROCE", roce_val)[0]},
                            {"Metric": "PAT Margin", "Value": f"{pat_margin:.2f}%" if pat_margin else "N/A", "Status": evaluate_status("PAT Margin", pat_margin)[0]},
                            {"Metric": "EBITDA Margin", "Value": f"{ebitda_margin:.2f}%" if ebitda_margin else "N/A", "Status": evaluate_status("EBITDA Margin", ebitda_margin)[0]}
                        ]
                        st.table(pd.DataFrame(p_data))
                        
                        st.markdown("#### Valuation")
                        v_data = [
                            {"Metric": "PE Ratio", "Value": f"{pe_val:.2f}" if pe_val else "N/A", "Status": "Normal" if pe_val else "N/A"},
                            {"Metric": "Price to Book", "Value": f"{pb_val:.2f}" if pb_val else "N/A", "Status": evaluate_status("Price to Book", pb_val)[0]},
                            {"Metric": "EV/EBITDA", "Value": f"{ev_ebitda:.2f}" if ev_ebitda else "N/A", "Status": "Normal" if ev_ebitda else "N/A"},
                            {"Metric": "Dividend Yield", "Value": f"{div_yield:.2f}%" if div_yield else "0.00%", "Status": evaluate_status("Dividend Yield", div_yield)[0]}
                        ]
                        st.table(pd.DataFrame(v_data))
                        
                    with c_f2:
                        st.markdown("#### Leverage & Solvency")
                        l_data = [
                            {"Metric": "Debt to Equity", "Value": f"{dte_val:.2f}" if dte_val is not None else "0.00", "Status": evaluate_status("Debt to Equity", dte_val)[0]},
                            {"Metric": "Current Ratio", "Value": f"{curr_ratio:.2f}" if curr_ratio else "N/A", "Status": evaluate_status("Current Ratio", curr_ratio)[0]},
                            {"Metric": "Quick Ratio", "Value": f"{quick_ratio:.2f}" if quick_ratio else "N/A", "Status": evaluate_status("Quick Ratio", quick_ratio)[0]}
                        ]
                        st.table(pd.DataFrame(l_data))
                        
                        st.markdown("#### Growth & Trajectory")
                        g_data = [
                            {"Metric": "Sales Growth", "Value": f"{rev_growth:.2f}%" if rev_growth else "N/A", "Status": evaluate_status("Sales Growth", rev_growth)[0]},
                            {"Metric": "EPS Growth", "Value": f"{eps_growth:.2f}%" if eps_growth else "N/A", "Status": evaluate_status("EPS Growth", eps_growth)[0]}
                        ]
                        st.table(pd.DataFrame(g_data))
                        
                    # Save telemetry into session state for AI prompt
                    st.session_state['single_ai_telemetry'] = {
                        "symbol": single_sym,
                        "exchange": single_exch,
                        "price": cp,
                        "ret_3m": r3,
                        "ret_6m": r6,
                        "vol_3m": vol3m,
                        "weighted_mom": weighted_score,
                        "roe": roe_val,
                        "pe": pe_val,
                        "pb": pb_val,
                        "dte": dte_val,
                        "current_ratio": curr_ratio,
                        "promoter": (stk_info.get('heldPercentInsiders', 0) or 0) * 100,
                        "insti": (stk_info.get('heldPercentInstitutions', 0) or 0) * 100
                    }
            except Exception as e:
                st.error(f"Error fetching stock data: {e}")

    if 'single_ai_telemetry' in st.session_state:
        st.markdown("---")
        st.subheader("🤖 Trigger In-Depth AI Forensic Audit")
        t_data = st.session_state['single_ai_telemetry']
        
        if st.button(f"🔍 Generate AI Forensic Intelligence Report for {t_data['symbol']}", use_container_width=True):
            if not gemini_api_key:
                st.error("Please enter your free Gemini API Key in the left sidebar.")
            else:
                with st.spinner(f"Gemini AI is analyzing financial statements, technical charts, and institutional trap signals for {t_data['symbol']}..."):
                    try:
                        genai.configure(api_key=gemini_api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        audit_prompt = f"""
                        Act as a Senior SEBI Quant Analyst and Institutional Forensic Strategist.
                        Perform a deep fundamental and Wyckoff/ADM trap analysis for: {t_data['symbol']} (Exchange: {t_data['exchange']})
                        
                        Live Telemetry:
                        - Current Price: ₹{t_data['price']:.2f}
                        - 3M Return: {t_data['ret_3m']:.2f}%, 6M Return: {t_data['ret_6m']:.2f}%
                        - 3M Volatility: {t_data['vol_3m']:.2f}%, Weighted Momentum Score: {t_data['weighted_mom']:.2f}
                        - Valuations: P/E: {t_data['pe']}, P/B: {t_data['pb']}
                        - Financial Health: ROE: {t_data['roe']:.2f}%, Debt/Equity: {t_data['dte']}, Current Ratio: {t_data['current_ratio']}
                        - Ownership: Promoter: {t_data['promoter']:.2f}%, Institutions (FII/DII): {t_data['insti']:.2f}%
                        
                        Format the response using these sections:
                        ## Executive Summary
                        ## Key Metrics & Growth
                        ## Valuation vs Peers
                        ## Key Strengths
                        ## Key Concerns
                        ## Industry & Trend View
                        ## Macro & Market Impact
                        ## News Impact Analysis
                        ## Peers Comparison Notes
                        ## Risk Factors & Strategic Execution
                        """
                        ai_response = model.generate_content(audit_prompt)
                        st.markdown(ai_response.text)
                    except Exception as e:
                        st.error(f"Gemini Error: {e}")

# =====================================================================
# TAB 3: HEAD-TO-HEAD AI STOCK COMPARE
# =====================================================================
with tab_compare:
    st.subheader("⚖️ Head-to-Head AI Stock Comparison Engine")
    st.caption("Compare any two Indian equities side-by-side. The AI evaluates both stocks and provides a clear recommendation on which offers a superior risk-reward profile.")
    
    cmp_c1, cmp_c2 = st.columns(2)
    with cmp_c1:
        stock_a = st.text_input("First Stock (e.g. TATAMOTORS):", value="TATAMOTORS", key="cmp_s1").upper().strip()
        exch_a = st.selectbox("Exchange for Stock A:", [".NS (NSE)", ".BO (BSE)"], key="cmp_e1")
    with cmp_c2:
        stock_b = st.text_input("Second Stock (e.g. M&M):", value="M&M", key="cmp_s2").upper().strip()
        exch_b = st.selectbox("Exchange for Stock B:", [".NS (NSE)", ".BO (BSE)"], key="cmp_e2")
        
    if st.button("🚀 Run Comparative Quant & AI Audit", use_container_width=True):
        t_a = f"{stock_a}{exch_a.split(' ')[0]}"
        t_b = f"{stock_b}{exch_b.split(' ')[0]}"
        
        with st.spinner(f"Extracting live comparative fundamentals for {t_a} vs {t_b}..."):
            try:
                stk_a = yf.Ticker(t_a)
                stk_b = yf.Ticker(t_b)
                
                h_a = stk_a.history(period="1y")
                h_b = stk_b.history(period="1y")
                
                i_a = stk_a.info
                i_b = stk_b.info
                
                if h_a.empty or h_b.empty:
                    st.error("Could not fetch data for one or both symbols. Check ticker spellings.")
                else:
                    cp_a = h_a['Close'].iloc[-1]
                    cp_b = h_b['Close'].iloc[-1]
                    
                    r3_a = ((cp_a - h_a['Close'].iloc[-63]) / h_a['Close'].iloc[-63]) * 100 if len(h_a) >= 63 else 0
                    r3_b = ((cp_b - h_b['Close'].iloc[-63]) / h_b['Close'].iloc[-63]) * 100 if len(h_b) >= 63 else 0
                    
                    r6_a = ((cp_a - h_a['Close'].iloc[-126]) / h_a['Close'].iloc[-126]) * 100 if len(h_a) >= 126 else 0
                    r6_b = ((cp_b - h_b['Close'].iloc[-126]) / h_b['Close'].iloc[-126]) * 100 if len(h_b) >= 126 else 0
                    
                    vol_a = h_a['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                    vol_b = h_b['Close'].iloc[-63:].pct_change().dropna().std() * np.sqrt(252) * 100
                    
                    w_a = (3 * r3_a + 2 * r6_a) / (vol_a if vol_a > 0 else 1.0)
                    w_b = (3 * r3_b + 2 * r6_b) / (vol_b if vol_b > 0 else 1.0)
                    
                    cmp_table = pd.DataFrame({
                        "Metric": [
                            "Current Market Price", "Market Cap (₹ Cr)", "3-Month Return", "6-Month Return",
                            "3-Month Volatility", "Weighted Momentum Score", "Trailing P/E", "Price-to-Book (P/B)",
                            "Return on Equity (ROE)", "Debt to Equity", "Current Ratio", "Promoter Holding %",
                            "Institutional Holding %"
                        ],
                        f"{stock_a}": [
                            f"₹{cp_a:,.2f}", f"₹{(i_a.get('marketCap', 0) or 0)/1e7:,.2f} Cr", f"{r3_a:+.2f}%", f"{r6_a:+.2f}%",
                            f"{vol_a:.2f}%", f"{w_a:.2f}", 
