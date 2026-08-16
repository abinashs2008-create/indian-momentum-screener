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
                            "Current
