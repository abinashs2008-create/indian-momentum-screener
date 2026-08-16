import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import google.generativeai as genai

# -------------------------------------------------------------
# PAGE CONFIGURATION (Responsive for Desktop & Mobile)
# -------------------------------------------------------------
st.set_page_config(page_title="Advanced Quant Screener", layout="wide", initial_sidebar_state="expanded")

st.title("📈 Advanced Quant & Fundamental Screener")
st.caption("Dual-Exchange Engine | Vectorized Filtering | AI Forensic Analysis")

# -------------------------------------------------------------
# HELPER FUNCTIONS (Advanced Technicals)
# -------------------------------------------------------------
def calculate_rsi(prices, period=14):
    """Calculates the 14-Day Relative Strength Index (RSI)."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))

# -------------------------------------------------------------
# 1. SIDEBAR CONFIGURATION & DUAL CSV UPLOAD
# -------------------------------------------------------------
st.sidebar.header("⚙️ System Config")
gemini_api_key = st.sidebar.text_input("🔑 Gemini API Key:", type="password")

st.sidebar.markdown("---")
st.sidebar.header("📱 Layout Configuration")
view_mode = st.sidebar.radio(
    "Select Interface View:", 
    ["Mobile View (+ Expandable Cards)", "Desktop View (Wide Data Table)"]
)

st.subheader("1. 📂 Upload Market Data (NSE & BSE)")
st.markdown("Upload the NSE and/or BSE Master CSV files. The engine automatically prevents duplicate scanning.")

col1, col2 = st.columns(2)
with col1:
    nse_file = st.file_uploader("Upload NSE CSV (EQUITY_L.csv):", type=["csv"], key="nse")
with col2:
    bse_file = st.file_uploader("Upload BSE CSV:", type=["csv"], key="bse")

# -------------------------------------------------------------
# 2. PRE-FILTER THRESHOLDS
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("⚡ Fast Pre-Filters")
min_3m = st.sidebar.number_input("Minimum 3-Month Return (%)", value=15.0, step=5.0)
min_6m = st.sidebar.number_input("Minimum 6-Month Return (%)", value=20.0, step=5.0)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Advanced Trap Filters")
require_trend = st.sidebar.checkbox("Price > 200 EMA (Stage 2 Uptrend)", value=True)
require_vol_breakout = st.sidebar.checkbox("Current Volume > 20-Day Avg", value=False)
max_rsi = st.sidebar.slider("Maximum RSI (Avoid Overbought)", 50, 100, 85)

# -------------------------------------------------------------
# 3. CORE PROCESSING ENGINE
# -------------------------------------------------------------
if st.button("🚀 Execute Advanced Market Scan", use_container_width=True):
    if nse_file is None and bse_file is None:
        st.warning("Please upload at least one CSV file to begin.")
    else:
        try:
            # --- DEDUPLICATION & MERGING ENGINE ---
            base_symbols = set()
            tickers_to_scan = []
            
            if nse_file is not None:
                nse_df = pd.read_csv(nse_file)
                nse_df.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
                if 'SYMBOL' in nse_df.columns:
                    for sym in nse_df['SYMBOL'].dropna().astype(str):
                        clean_sym = sym.strip()
                        if clean_sym not in base_symbols:
                            base_symbols.add(clean_sym)
                            tickers_to_scan.append(f"{clean_sym}.NS")
            
            if bse_file is not None:
                bse_df = pd.read_csv(bse_file)
                bse_df.rename(columns=lambda x: str(x).strip().upper(), inplace=True)
                # Handle common BSE column names (Security Code, Issuer Name, etc.)
                bse_col = 'SYMBOL' if 'SYMBOL' in bse_df.columns else bse_df.columns[0]
                for sym in bse_df[bse_col].dropna().astype(str):
                    clean_sym = sym.strip()
                    if clean_sym not in base_symbols:  # Deduplication check
                        base_symbols.add(clean_sym)
                        tickers_to_scan.append(f"{clean_sym}.BO")
            
            st.info(f"Engine Merged & Deduplicated: Scanning {len(tickers_to_scan)} unique companies.")
            
            # --- VECTORIZED PRE-FILTER ---
            with st.spinner("Step 1: Lightning Vectorized Pre-Filter (Fetching 1-Year History)..."):
                data = yf.download(tickers_to_scan, period="1y", threads=True, progress=False)
                
                if data.empty:
                    st.error("Network error fetching data. Please retry.")
                    st.stop()

                close_prices = data['Close'] if len(tickers_to_scan) > 1 else data[['Close']]
                if len(tickers_to_scan) == 1:
                    close_prices.columns = tickers_to_scan
                    
                current_price = close_prices.iloc[-1]
                p_3m = close_prices.iloc[-63] if len(close_prices) >= 63 else pd.Series(dtype=float)
                p_6m = close_prices.iloc[-126] if len(close_prices) >= 126 else pd.Series(dtype=float)
                
                ret_3m = ((current_price - p_3m) / p_3m) * 100
                ret_6m = ((current_price - p_6m) / p_6m) * 100
                
                mask = (ret_3m >= min_3m) & (ret_6m >= min_6m) & (ret_3m.notna()) & (ret_6m.notna())
                passed_tickers = mask[mask].index.tolist()
            
            if not passed_tickers:
                st.warning("No stocks survived the initial return filters.")
            else:
                st.success(f"⚡ Pre-filter cleared! Extracted {len(passed_tickers)} high-momentum candidates. Running deep technicals...")
                
                # --- DEEP FUNDAMENTAL & TECHNICAL EXTRACTION ---
                results = []
                progress_bar = st.progress(0)
                
                for idx, ticker in enumerate(passed_tickers):
                    progress_bar.progress((idx + 1) / len(passed_tickers))
                    try:
                        ticker_data = data[ticker].dropna() if len(tickers_to_scan) > 1 else data.dropna()
                        if len(ticker_data) < 189:
                            continue
                            
                        curr_p = ticker_data['Close'].iloc[-1]
                        
                        # Technical Indicators
                        ema_50 = ticker_data['Close'].ewm(span=50, adjust=False).mean().iloc[-1]
                        ema_200 = ticker_data['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
                        high_52w = ticker_data['Close'].max()
                        dist_52w = ((curr_p - high_52w) / high_52w) * 100
                        rsi_14 = calculate_rsi(ticker_data['Close']).iloc[-1]
                        
                        # Apply Technical Filters
                        if require_trend and curr_p < ema_200:
                            continue
                        if pd.notna(rsi_14) and rsi_14 > max_rsi:
                            continue
                            
                        vol_20d = ticker_data['Volume'].iloc[-20:].mean()
                        curr_v = ticker_data['Volume'].iloc[-1]
                        vol_ratio = curr_v / vol_20d if vol_20d > 0 else 1.0
                        
                        if require_vol_breakout and vol_ratio < 1.0:
                            continue

                        # Momentum Scoring
                        p_1m = ticker_data['Close'].iloc[-21]
                        p_9m = ticker_data['Close'].iloc[-189]
                        r1 = ((curr_p - p_1m) / p_1m) * 100
                        r3 = ret_3m[ticker]
                        r6 = ret_6m[ticker]
                        r9 = ((curr_p - p_9m) / p_9m) * 100
                        
                        daily_ret = ticker_data['Close'].iloc[-63:].pct_change().dropna()
                        vol_3m = daily_ret.std() * np.sqrt(252) * 100
                        vol_divisor = vol_3m if vol_3m > 0 else 1.0
                        
                        raw_mom = (r3 + r6 + r9) / vol_divisor
                        weighted_mom = (3 * r3 + 2 * r6 + 1 * r9) / vol_divisor
                        
                        # Fundamentals (Fetched specifically for winners)
                        stock_info = yf.Ticker(ticker).info
                        mcap_cr = stock_info.get('marketCap', 0) / 10000000 if stock_info.get('marketCap') else 0
                        pe_ratio = stock_info.get('trailingPE', 0)
                        pb_ratio = stock_info.get('priceToBook', 0)
                        promoter = stock_info.get('heldPercentInsiders', 0) * 100 if stock_info.get('heldPercentInsiders') else 0
                        fii_dii = stock_info.get('heldPercentInstitutions', 0) * 100 if stock_info.get('heldPercentInstitutions') else 0
                        
                        results.append({
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
                            "Dist 52W High %": round(dist_52w, 1),
                            "Vol Breakout (x)": round(vol_ratio, 1),
                            "Mkt Cap (Cr)": round(mcap_cr, 2),
                            "P/E": round(pe_ratio, 2) if pe_ratio else "N/A",
                            "P/B": round(pb_ratio, 2) if pb_ratio else "N/A",
                            "Promoter %": round(promoter, 2),
                            "Insti (FII/DII) %": round(fii_dii, 2)
                        })
                    except Exception:
                        continue
                        
                if results:
                    final_df = pd.DataFrame(results).sort_values(by="Score (W. Mom)", ascending=False).reset_index(drop=True)
                    st.session_state['advanced_results'] = final_df
                    st.success(f"✅ Analysis Complete! {len(final_df)} highly qualified setups identified.")
                else:
                    st.warning("Stocks passed the initial returns filter, but failed advanced trap/technical checks.")
                    
        except Exception as e:
            st.error(f"System Error: {e}")

# -------------------------------------------------------------
# 4. RESULTS DISPLAY (Mobile vs Desktop)
# -------------------------------------------------------------
if 'advanced_results' in st.session_state and not st.session_state['advanced_results'].empty:
    df_display = st.session_state['advanced_results']
    
    st.markdown("---")
    st.subheader("📊 Market Scan Results")
    
    if view_mode == "Mobile View (+ Expandable Cards)":
        # Render mobile-friendly expandable rows
        for _, row in df_display.iterrows():
            with st.expander(f"➕ {row['Symbol']} | Price: ₹{row['Price (₹)']} | Mom Score: {row['Score (W. Mom)']}"):
                st.markdown(f"**Advanced Technicals:**")
                t1, t2, t3 = st.columns(3)
                t1.metric("RSI (14)", row['RSI (14)'])
                t2.metric("Vol Breakout", f"{row['Vol Breakout (x)']}x")
                t3.metric("52W High Dist", f"{row['Dist 52W High %']}%")
                
                st.markdown(f"**Performance Breakdown:**")
                p1, p2, p3, p4 = st.columns(4)
                p1.metric("1M", f"{row['1M %']}%")
                p2.metric("3M", f"{row['3M %']}%")
                p3.metric("6M", f"{row['6M %']}%")
                p4.metric("9M", f"{row['9M %']}%")
                
                st.markdown(f"**Fundamentals (Screener.in Metrics):**")
                f_df = pd.DataFrame({
                    "Metric": ["Market Cap", "P/E Ratio", "P/B Ratio", "Promoter Hold", "FII/DII Hold"],
                    "Value": [f"₹{row['Mkt Cap (Cr)']} Cr", row['P/E'], row['P/B'], f"{row['Promoter %']}%", f"{row['Insti (FII/DII) %']}%"]
                })
                st.table(f_df)
    else:
        # Render Desktop-friendly wide interactive table
        display_cols = [col for col in df_display.columns if col != "Raw_Ticker"]
        st.dataframe(df_display[display_cols], use_container_width=True, height=500)
    
    # Global CSV Export
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Advanced Data to CSV", data=csv, file_name="Advanced_Screener_Results.csv", mime="text/csv")
    
    # -------------------------------------------------------------
    # 5. GEMINI AI FORENSIC AUDIT
    # -------------------------------------------------------------
    st.markdown("---")
    st.subheader("🤖 Gemini Institutional AI Audit")
    
    selected_stock = st.selectbox("Select a screened winner for deep AI audit:", df_display['Symbol'].tolist())
    
    if st.button(f"🔍 Run Forensic Audit on {selected_stock}", use_container_width=True):
        if not gemini_api_key:
            st.error("Please enter your free Gemini API key in the sidebar.")
        else:
            with st.spinner(f"Gemini AI is auditing {selected_stock}..."):
                try:
                    stock_data = df_display[df_display['Symbol'] == selected_stock].iloc[0]
                    raw_ticker = stock_data['Raw_Ticker']
                    
                    genai.configure(api_key=gemini_api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    Act as a Senior SEBI Quant Analyst.
                    Perform a deep fundamental and technical trap analysis for {selected_stock}.
                    
                    Context Metrics:
                    - Price: ₹{stock_data['Price (₹)']} (Mkt Cap: ₹{stock_data['Mkt Cap (Cr)']} Cr)
                    - Valuations: P/E: {stock_data['P/E']}, P/B: {stock_data['P/B']}
                    - Ownership: Promoter: {stock_data['Promoter %']}%, Insti: {stock_data['Insti (FII/DII) %']}%
                    - Returns: 3M: {stock_data['3M %']}%, 6M: {stock_data['6M %']}%
                    - Technicals: RSI: {stock_data['RSI (14)']}, Distance from 52W High: {stock_data['Dist 52W High %']}%
                    
                    Provide a structured report:
                    1. **Fundamental & Valuation Audit**: Assess the P/E, P/B, and shareholding health.
                    2. **Technical & Momentum Health**: Based on the RSI and 52-week high distance, is this overextended or breaking out?
                    3. **Institutional Trap Detection**: Are there signs of a retail distribution trap?
                    4. **Positional Verdict**: (Buy/Hold/Avoid) and a logical technical stop-loss limit.
                    """
                    
                    response = model.generate_content(prompt)
                    st.markdown("### 📋 Official AI Forensic Report")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Gemini API Error: {e}")
        
