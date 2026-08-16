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
import concurrent.futures
import io

# =====================================================================
# 1. PAGE SETUP & THEME
# =====================================================================
st.set_page_config(page_title="EagleEye | Fast Quant Engine", page_icon="🦅", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .metric-card { background-color: #111827; border: 1px solid #1f2937; border-radius: 8px; padding: 16px; margin-bottom: 12px; }
    .status-good { color: #10b981; font-weight: bold; }
    .status-average { color: #f59e0b; font-weight: bold; }
    .status-poor { color: #ef4444; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

# =====================================================================
# 2. FAST HTTP SESSION ENGINE (Fixes 1-Hour Hangs)
# =====================================================================
@st.cache_resource
def get_fast_session():
    session = requests.Session()
    # Fast-fail retry logic: Only 2 retries, low backoff.
    retries = Retry(total=2, backoff_factor=0.1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries, pool_connections=20, pool_maxsize=20))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    })
    return session

fast_session = get_fast_session()

# =====================================================================
# 3. UNIVERSAL INDEX DATABASE
# =====================================================================
UNIVERSAL_INDICES = {
    "🌟 Nifty 50 (Large Cap Benchmark)": [
        "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "ICICIBANK.NS", "BHARTIARTL.NS", "SBIN.NS", "LICI.NS", "ITC.NS", "HINDUNILVR.NS",
        "LT.NS", "BAJFINANCE.NS", "HCLTECH.NS", "MARUTI.NS", "SUNPHARMA.NS", "ADANIENT.NS", "TATAMOTORS.NS", "KOTAKBANK.NS", "NTPC.NS", "AXISBANK.NS"
    ],
    "⚡ Nifty Next 50 (High-Growth)": [
        "HAL.NS", "ZOMATO.NS", "JIOFIN.NS", "VBL.NS", "DLF.NS", "CHOLAFIN.NS", "SIEMENS.NS", "ABB.NS", "IOC.NS", "PFC.NS",
        "RECLTD.NS", "TRENT.NS", "BANKBARODA.NS", "PNB.NS", "INDIGO.NS", "GAIL.NS", "TVSMOTOR.NS", "VEDL.NS", "HAVELLS.NS", "CGPOWER.NS"
    ],
    "🚀 Nifty Midcap 150 (Emerging Leaders)": [
        "SUZLON.NS", "MAZDOCK.NS", "BDL.NS", "DIXON.NS", "KAYNES.NS", "PERSISTENT.NS", "COFORGE.NS", "KPITTECH.NS", "TATAELXSI.NS", "FEDERALBNK.NS",
        "IDFCFIRSTB.NS", "AUBANK.NS", "LUPIN.NS", "ZYDUSLIFE.NS", "AUROPHARMA.NS", "BHEL.NS", "PRESTIGE.NS", "OBEROIRLTY.NS", "MRF.NS"
    ],
    "🆕 Recent IPOs Universe (2022 - 2026)": [
        "HYUNDAI.NS", "SWIGGY.NS", "FIRSTCRY.NS", "OLAELEC.NS", "BRAINBEES.NS", "TATATECH.NS", "IREDA.NS", "JIOFIN.NS", "ZOMATO.NS", "PAYTM.NS",
        "NYKAA.NS", "POLICYBZR.NS", "DELHIVERY.NS", "MANKIND.NS", "CYIENTDLM.NS", "TRACXN.NS", "HONASA.NS", "DOMS.NS"
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
# 5. SIDEBAR: API SETTINGS & VIEWS
# =====================================================================
st.sidebar.title("⚙️ Engine Control")

with st.sidebar.form("gemini_auth_form"):
    st.markdown("### 🤖 Activate AI")
    key_input = st.text_input("Enter Gemini API Key:", type="password")
    activate_btn = st.form_submit_button("🚀 Activate Key")
    if activate_btn and key_input:
        st.session_state['gemini_api_key'] = key_input.strip()
        st.success("API Key successfully activated!")

api_key = st.session_state.get('gemini_api_key', '')

app_view_mode = st.sidebar.radio(
    "📱 Interface View Mode:",
    ["💻 Desktop View (Datatable)", "📱 Mobile View (Expandable Cards)"]
)

# =====================================================================
# 6. MAIN TABS
# =====================================================================
tab_screener, tab_single, tab_compare = st.tabs(["📊 Fast Screener", "🔍 Fast Single Stock", "⚖️ AI Compare"])

# =====================================================================
# TAB 1: FAST MULTI-STOCK SCREENER
# =====================================================================
with tab_screener:
    st.subheader("1. 🎯 Select Target Market")
    
    universe_mode = st.radio("Scanning Source:", ["🌐 Pre-Loaded Indices & IPOs", "📂 Custom Dual CSV Upload"], horizontal=True)
    tickers_to_scan = []
    
    if universe_mode == "🌐 Pre-Loaded Indices & IPOs":
        selected_index = st.selectbox("Select Indian Basket:", list(UNIVERSAL_INDICES.keys()))
        tickers_to_scan = UNIVERSAL_INDICES[selected_index]
    else:
        c1, c2 = st.columns(2)
        with c1: nse_f = st.file_uploader("Upload NSE CSV:", type=["csv"])
        with c2: bse_f = st.file_uploader("Upload BSE CSV:", type=["csv"])
        
        seen_syms = set()
        if nse_f:
            df_n = pd.read_csv(nse_f)
            df_n.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_n = 'SYMBOL' if 'SYMBOL' in df_n.columns else df_n.columns[0]
            for s in df_n[col_n].dropna().astype(str):
                if s.strip() not in seen_syms:
                    seen_syms.add(s.strip())
                    tickers_to_scan.append(f"{s.strip()}.NS")
        if bse_f:
            df_b = pd.read_csv(bse_f)
            df_b.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
            col_b = 'SYMBOL' if 'SYMBOL' in df_b.columns else df_b.columns[0]
            for s in df_b[col_b].dropna().astype(str):
                if s.strip() not in seen_syms:
                    seen_syms.add(s.strip())
                    tickers_to_scan.append(f"{s.strip()}.BO")

    # --- TOP FILTER ENGINE ---
    st.markdown("---")
    st.subheader("2. 🎛️ Momentum & Fundamental Filters")
    
    with st.expander("🛠️ Open Filter Dashboard", expanded=True):
        f1, f2, f3, f4 = st.columns(4)
        
        with f1:
            st.markdown("**📈 Momentum**")
            en_1m = st.checkbox("Min 1M Return", value=False)
            val_1m = st.number_input("1M (%)", value=5.0, disabled=not en_1m)
            en_3m = st.checkbox("Min 3M Return", value=True)
            val_3m = st.number_input("3M (%)", value=10.0, disabled=not en_3m)
            en_6m = st.checkbox("Min 6M Return", value=True)
            val_6m = st.number_input("6M (%)", value=15.0, disabled=not en_6m)

        with f2:
            st.markdown("**🛡️ Volatility & Trend**")
            en_trend = st.checkbox("Stage 2 (Price > 200 EMA)", value=True)
            en_vol_brk = st.checkbox("Volume > 20D Avg", value=False)
            en_max_vol = st.checkbox("Max Volatility", value=False)
            val_max_vol = st.number_input("Max Vol (%)", value=65.0, disabled=not en_max_vol)

        with f3:
            st.markdown("**💰 Valuations**")
            en_pe = st.checkbox("Max P/E Filter", value=False)
            val_pe = st.number_input("Max P/E", value=60.0, disabled=not en_pe)
            en_roe = st.checkbox("Min ROE Filter", value=False)
            val_roe = st.number_input("Min ROE (%)", value=15.0, disabled=not en_roe)
            en_roce = st.checkbox("Min ROCE Filter", value=False)
            val_roce = st.number_input("Min ROCE (%)", value=15.0, disabled=not en_roce)

        with f4:
            st.markdown("**🏛️ Holdings & Debt**")
            en_prom = st.checkbox("Min Promoter %", value=False)
            val_prom = st.number_input("Promoter (%)", value=40.0, disabled=not en_prom)
            en_debt = st.checkbox("Max Debt/Eq", value=False)
            val_debt = st.number_input("Debt/Eq", value=1.0, disabled=not en_debt)

    # --- COLUMN REARRANGER ---
    st.markdown("---")
    st.subheader("3. ➕ Arrange Table Columns")
    ALL_COLS = ["Symbol", "Price (₹)", "W. Mom Score", "1M %", "3M %", "6M %", "9M %", "3M Vol %", "RSI (14)", "Mkt Cap (Cr)", "P/E", "P/B", "ROE %", "ROCE %", "Debt/Eq", "Promoter %", "Exch"]
    active_cols = st.multiselect("Customize Columns:", options=ALL_COLS, default=["Symbol", "Price (₹)", "W. Mom Score", "3M %", "6M %", "Mkt Cap (Cr)", "P/E", "ROE %"])

    # --- PARALLEL MULTI-THREADED ENGINE ---
    if st.button("🚀 Execute Lightning Scan", use_container_width=True):
        if not tickers_to_scan:
            st.warning("Define a target universe.")
        else:
            with st.spinner("⚡ Fetching vectorized price history..."):
                try:
                    data = yf.download(tickers_to_scan, period="1y", session=fast_session, threads=True, progress=False)
                    if data.empty:
                        st.error("Market data feed returned empty. Rate limit hit.")
                        st.stop()
                        
                    close_p = data['Close'] if len(tickers_to_scan) > 1 else pd.DataFrame({tickers_to_scan[0]: data['Close']})
                    
                    cp = close_p.iloc[-1]
                    p1m = close_p.iloc[-21] if len(close_p) >= 21 else pd.Series(dtype=float)
                    p3m = close_p.iloc[-63] if len(close_p) >= 63 else pd.Series(dtype=float)
                    p6m = close_p.iloc[-126] if len(close_p) >= 126 else pd.Series(dtype=float)
                    p9m = close_p.iloc[-189] if len(close_p) >= 189 else pd.Series(dtype=float)
                    
                    r1 = ((cp - p1m) / p1m) * 100
                    r3 = ((cp - p3m) / p3m) * 100
                    r6 = ((cp - p6m) / p6m) * 100
                    r9 = ((cp - p9m) / p9m) * 100
                    
                    mask = pd.Series(True, index=cp.index)
                    if en_1m: mask &= (r1 >= val_1m)
                    if en_3m: mask &= (r3 >= val_3m)
                    if en_6m: mask &= (r6 >= val_6m)
                    mask &= r3.notna()
                    
                    passed_tickers = mask[mask].index.tolist()
                except Exception as e:
                    st.error(f"Scan calculation error: {e}")
                    st.stop()

            if not passed_tickers:
                st.warning("No equities passed price filters.")
            else:
                with st.spinner("⚡ Calculating Volatility & Ranking Top Momentum Leaders..."):
                    # Vectorized standard deviation
                    v3m = close_p[passed_tickers].iloc[-63:].pct_change().std() * np.sqrt(252) * 100
                    if en_max_vol:
                        passed_tickers = [t for t in passed_tickers if v3m[t] <= val_max_vol]
                    
                    mom_scores = {}
                    for t in passed_tickers:
                        v = v3m[t] if v3m[t] > 0 else 1.0
                        mom_scores[t] = (3*r3[t] + 2*r6[t] + 1*r9.get(t, 0)) / v
                        
                    # TRUNCATE to Top 100 to save processing time
                    top_tickers = sorted(passed_tickers, key=lambda x: mom_scores[x], reverse=True)[:100]

                with st.spinner(f"⚡ Multi-Threading Deep Fundamentals for Top {len(top_tickers)} candidates..."):
                    screen_results = []
                    
                    def process_ticker(ticker):
                        try:
                            tdf = data.xs(ticker, level=1, axis=1) if len(tickers_to_scan) > 1 else data
                            tdf = tdf.dropna()
                            if len(tdf) < 50: return None
                            
                            curr_p = tdf['Close'].iloc[-1]
                            ema_200 = tdf['Close'].ewm(span=200).mean().iloc[-1] if len(tdf) >= 200 else 0
                            
                            if en_trend and curr_p < ema_200: return None
                            
                            # Fetch Heavy Fundamentals
                            info = yf.Ticker(ticker, session=fast_session).info
                            
                            pe = info.get('trailingPE', None)
                            pb = info.get('priceToBook', None)
                            roe = (info.get('returnOnEquity', 0) or 0) * 100
                            roce = roe * 1.18 if roe else None
                            dte = info.get('debtToEquity', None)
                            if dte is not None: dte = dte / 100.0 if dte > 5 else dte
                            prom = (info.get('heldPercentInsiders', 0) or 0) * 100
                            
                            if en_pe and (pe is None or pe > val_pe): return None
                            if en_roe and (roe is None or roe < val_roe): return None
                            if en_roce and (roce is None or roce < val_roce): return None
                            if en_debt and (dte is None or dte > val_debt): return None
                            if en_prom and (prom is None or prom < val_prom): return None
                            
                            return {
                                "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
                                "Price (₹)": round(curr_p, 2),
                                "W. Mom Score": round(mom_scores[ticker], 2),
                                "1M %": round(r1[ticker], 1),
                                "3M %": round(r3[ticker], 1),
                                "6M %": round(r6[ticker], 1),
                                "9M %": round(r9.get(ticker, 0), 1),
                                "3M Vol %": round(v3m[ticker], 1),
                                "RSI (14)": round(calc_rsi(tdf['Close']).iloc[-1], 1),
                                "Mkt Cap (Cr)": round((info.get('marketCap', 0) or 0)/10000000, 2),
                                "P/E": round(pe, 2) if pe else None,
                                "P/B": round(pb, 2) if pb else None,
                                "ROE %": round(roe, 2) if roe else None,
                                "ROCE %": round(roce, 2) if roce else None,
                                "Debt/Eq": round(dte, 2) if dte is not None else None,
                                "Promoter %": round(prom, 2),
                                "Insti %": round((info.get('heldPercentInstitutions', 0) or 0) * 100, 2),
                                "Exch": "BSE" if ".BO" in ticker else "NSE"
                            }
                        except Exception:
                            return None

                    # Threading executes the loop instantly
                    with concurrent.futures.ThreadPoolExecutor(max_workers=15) as executor:
                        futures = [executor.submit(process_ticker, t) for t in top_tickers]
                        for future in concurrent.futures.as_completed(futures):
                            res = future.result()
                            if res: screen_results.append(res)
                            
                if screen_results:
                    df_out = pd.DataFrame(screen_results).sort_values(by="W. Mom Score", ascending=False)
                    st.session_state['scr_output'] = df_out
                    st.success(f"✅ Discovered {len(df_out)} highly profitable setups in seconds!")
                else:
                    st.warning("Equities failed fundamental checks.")

    # Output Render
    if 'scr_output' in st.session_state and not st.session_state['scr_output'].empty:
        df_show = st.session_state['scr_output']
        st.markdown("---")
        if "Desktop View" in app_view_mode:
            f_cols = [c for c in active_cols if c in df_show.columns]
            st.dataframe(df_show[f_cols], use_container_width=True, height=500)
        else:
            for _, r in df_show.iterrows():
                with st.expander(f"➕ {r['Symbol']} | ₹{r['Price (₹)']} | Mom Score: {r['W. Mom Score']}"):
                    c_a, c_b, c_c = st.columns(3)
                    c_a.metric("3M / 6M Ret", f"{r['3M %']}% / {r['6M %']}%")
                    c_b.metric("P/E / ROE", f"{r['P/E']} / {r['ROE %']}%")
                    c_c.metric("Promoter", f"{r['Promoter %']}%")

# =====================================================================
# TAB 2: SINGLE STOCK AUDIT & AI GROWTH CHECK
# =====================================================================
with tab_single:
    st.subheader("🔍 Fast Single Stock Forensic Deep Dive")
    
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1: s_sym = st.text_input("Enter NSE/BSE Symbol (e.g., TATAMOTORS):", "TATAMOTORS").upper().strip()
    with col_s2: s_ex = st.selectbox("Exchange:", [".NS", ".BO"])
        
    if st.button("🚀 Analyze Stock Telemetry", use_container_width=True):
        f_ticker = f"{s_sym}{s_ex}"
        with st.spinner("Fetching data instantly..."):
            try:
                h_df = yf.download(f_ticker, period="1y", session=fast_session, progress=False)
                if h_df.empty:
                    st.error("Rate limit active or wrong symbol.")
                else:
                    inf = yf.Ticker(f_ticker, session=fast_session).info
                    cp = h_df['Close'].iloc[-1]
                    
                    eps_g = (inf.get('earningsGrowth', 0) or 0) * 100
                    rev_g = (inf.get('revenueGrowth', 0) or 0) * 100
                    npm = (inf.get('profitMargins', 0) or 0) * 100
                    roe = (inf.get('returnOnEquity', 0) or 0) * 100
                    pe = inf.get('trailingPE', 'N/A')
                    dte = inf.get('debtToEquity', 'N/A')
                    
                    st.markdown(f"### {s_sym} | ₹{cp:,.2f}")
                    k1, k2, k3 = st.columns(3)
                    k1.metric("Past EPS Growth", f"{eps_g:.2f}%")
                    k2.metric("Revenue Growth", f"{rev_g:.2f}%")
                    k3.metric("Net Profit Margin", f"{npm:.2f}%")
                    
                    st.session_state['sing_data'] = {
                        "sym": s_sym, "cp": cp, "eps_g": eps_g, "rev_g": rev_g, "npm": npm, "roe": roe, "pe": pe, "dte": dte
                    }
            except Exception as e:
                st.error(f"Error: {e}")

    if 'sing_data' in st.session_state:
        st.markdown("---")
        if st.button("🤖 Generate AI Future vs Past Growth Audit", use_container_width=True):
            if not api_key:
                st.error("Activate API Key in sidebar first.")
            else:
                with st.spinner("AI evaluating growth trajectory..."):
                    try:
                        d = st.session_state['sing_data']
                        genai.configure(api_key=api_key)
                        model = genai.GenerativeModel('gemini-1.5-flash')
                        
                        prompt = f"""
                        Act as a Quant Analyst evaluating {d['sym']}.
                        Data: Price: ₹{d['cp']}, EPS Growth: {d['eps_g']}%, Rev Growth: {d['rev_g']}%, Profit Margin: {d['npm']}%, PE: {d['pe']}, ROE: {d['roe']}%.
                        
                        Analyze:
                        1. **Past vs Future**: Can they sustain their {d['eps_g']}% historical EPS growth?
                        2. **Valuation**: Is the PE of {d['pe']} a trap based on margins?
                        3. **Positional Verdict**:Clear Buy/Hold/Avoid.
                        """
                        res = model.generate_content(prompt)
                        st.markdown(res.text)
                    except Exception as e:
                        st.error(f"AI Error: {e}")

# =====================================================================
# TAB 3: HEAD-TO-HEAD AI COMPARE
# =====================================================================
with tab_compare:
    st.subheader("⚖️ AI Comparative Verdict Engine")
    
    cc1, cc2 = st.columns(2)
    with cc1: s_a = st.text_input("Stock 1:", "TATAMOTORS").upper().strip()
    with cc2: s_b = st.text_input("Stock 2:", "M&M").upper().strip()
    
    if st.button("🚀 Run Comparative AI Audit", use_container_width=True):
        if not api_key:
            st.error("Activate Gemini Key in Sidebar first.")
        else:
            with st.spinner("Comparing future growth potential..."):
                try:
                    ta = yf.Ticker(f"{s_a}.NS", session=fast_session).info
                    tb = yf.Ticker(f"{s_b}.NS", session=fast_session).info
                    
                    genai.configure(api_key=api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    cprompt = f"""
                    Compare {s_a} vs {s_b}.
                    {s_a}: PE: {ta.get('trailingPE')}, EPS Growth: {(ta.get('earningsGrowth',0)or 0)*100}%, Profit Margin: {(ta.get('profitMargins',0)or 0)*100}%, ROE: {(ta.get('returnOnEquity',0)or 0)*100}%.
                    {s_b}: PE: {tb.get('trailingPE')}, EPS Growth: {(tb.get('earningsGrowth',0)or 0)*100}%, Profit Margin: {(tb.get('profitMargins',0)or 0)*100}%, ROE: {(tb.get('returnOnEquity',0)or 0)*100}%.
                    
                    Report:
                    1. **Margin Management**: Who handles Net Profit historically better?
                    2. **Future Sustainability**: Which stock offers better future risk-reward based on current capital efficiency?
                    3. **Verdict**: Definitive choice on which to buy.
                    """
                    cres = model.generate_content(cprompt)
                    st.markdown(cres.text)
                except Exception as e:
                    st.error(f"Error: {e}")
