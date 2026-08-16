import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import google.generativeai as genai
from datetime import datetime

st.set_page_config(page_title="Indian Market Master Screener", layout="wide")

st.title("🇮🇳 Master Indian Market & IPO Screener")
st.caption("Lightning-fast Vectorized Pre-filtering across all 5,000+ NSE & BSE stocks.")

# -------------------------------------------------------------
# 1. LIVE MASTER DATABASE & IPO FETCHER (FIREWALL FIXED)
# -------------------------------------------------------------
@st.cache_data(ttl=43200)
def fetch_master_equity_list():
    """Fetches official live NSE/BSE Master List and bypasses firewalls."""
    try:
        session = requests.Session()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive'
        }
        
        # Hit homepage first to secure trusted cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        # Fetch the CSV
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        response = session.get(url, headers=headers, timeout=10)
        
        df = pd.read_csv(io.StringIO(response.text))
        df.rename(columns=lambda x: str(x).strip(), inplace=True)
        
        if 'DATE OF LISTING' not in df.columns:
            raise ValueError("NSE Firewall blocked the request.")
            
        df['DATE OF LISTING'] = pd.to_datetime(df['DATE OF LISTING'], format='%d-%b-%Y', errors='coerce')
        return df
        
    except Exception as e:
        st.warning(f"⚠️ Live Data temporarily blocked. Using offline fallback dataset.")
        fallback_data = {
            'SYMBOL': ['ZOMATO', 'PAYTM', 'NYKAA', 'POLICYBZR', 'JIOFIN', 'IREDA', 'TCS', 'RELIANCE', 'HDFCBANK', 'SUZLON', 'HAL', 'BEL', 'MAZDOCK'],
            'DATE OF LISTING': ['23-Jul-2021', '18-Nov-2021', '10-Nov-2021', '15-Nov-2021', '21-Aug-2023', '29-Nov-2023', '25-Aug-2004', '29-Nov-1995', '19-May-1995', '19-Oct-2005', '28-Mar-2018', '31-Aug-2000', '12-Oct-2020']
        }
        df_fallback = pd.DataFrame(fallback_data)
        df_fallback['DATE OF LISTING'] = pd.to_datetime(df_fallback['DATE OF LISTING'], format='%d-%b-%Y', errors='coerce')
        return df_fallback

master_df = fetch_master_equity_list()

# -------------------------------------------------------------
# 2. EXHAUSTIVE BROKERAGE SECTORS
# -------------------------------------------------------------
BROKERAGE_SECTORS = {
    "🚜 Agro Chemicals & Fertilizers": ["UPL", "PIIND", "COROMANDEL", "CHAMBLFERT", "FACT", "GNFC"],
    "✈️ Airlines & Aviation": ["INDIGO", "SPICEJET", "TAJGVK"],
    "⚙️ Auto & Auto Ancillaries": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "BOSCHLTD", "MOTHERSON", "MRF"],
    "🏦 Banks (Public & Private)": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "PNB", "BANKBARODA"],
    "🏗️ Capital Goods & Defense": ["LT", "HAL", "BEL", "MAZDOCK", "BDL", "SIEMENS", "ABB", "CGPOWER"],
    "🧱 Cement & Construction": ["ULTRACEMCO", "AMBUJACEM", "SHREECEM", "ACC", "DALBHARAT"],
    "🛒 FMCG & Retail": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DMART", "TRENT"],
    "💻 IT - Software & Services": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT"],
    "⛏️ Metals & Mining": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "COALINDIA"],
    "🛢️ Petrochemicals, Oil & Gas": ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "PETRONET"],
    "💊 Pharmaceuticals": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "AUROPHARMA"],
    "⚡ Power & Green Energy": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "SUZLON", "IREDA"],
    "📱 New-Age Tech (Startups)": ["ZOMATO", "PAYTM", "NYKAA", "POLICYBZR", "JIOFIN"]
}

# -------------------------------------------------------------
# 3. UI: UNIVERSE SELECTION & IPO TRACKER
# -------------------------------------------------------------
st.sidebar.header("⚙️ System Configuration")
gemini_api_key = st.sidebar.text_input("🔑 Gemini API Key:", type="password")

st.subheader("1. 🎯 Define Target Universe & Exchange")

col1, col2 = st.columns(2)
with col1:
    exchange_mode = st.selectbox("Select Exchange Universe:", ["NSE Only", "BSE Only", "Both NSE & BSE"])
with col2:
    scan_mode = st.selectbox(
        "Select Scanning Filter:",
        ["All Listed IPOs (Filter by Date)", "Brokerage Sectors (Exhaustive)", "Broad Market (Entire Database)"]
    )

raw_symbols = []

if scan_mode == "All Listed IPOs (Filter by Date)":
    if not master_df.empty:
        min_year = st.slider("Select IPO Listing Year Range:", min_value=1995, max_value=datetime.now().year, value=(2023, 2026))
        ipo_df = master_df[(master_df['DATE OF LISTING'].dt.year >= min_year[0]) & 
                           (master_df['DATE OF LISTING'].dt.year <= min_year[1])]
        raw_symbols = ipo_df['SYMBOL'].tolist()
        st.info(f"Loaded **{len(raw_symbols)} IPOs** listed between {min_year[0]} and {min_year[1]}.")

elif scan_mode == "Brokerage Sectors (Exhaustive)":
    selected_sector = st.selectbox("Select Industry/Sector:", list(BROKERAGE_SECTORS.keys()))
    raw_symbols = BROKERAGE_SECTORS[selected_sector]
    st.info(f"Loaded **{len(raw_symbols)} stocks** in {selected_sector}.")

elif scan_mode == "Broad Market (Entire Database)":
    if not master_df.empty:
        raw_symbols = master_df['SYMBOL'].tolist()
        st.info(f"Loaded massive database of **{len(raw_symbols)} stocks**.")

# Apply Exchange Suffixes (.NS for NSE, .BO for BSE)
tickers_to_scan = []
for sym in raw_symbols:
    if exchange_mode in ["NSE Only", "Both NSE & BSE"]:
        tickers_to_scan.append(f"{sym}.NS")
    if exchange_mode in ["BSE Only", "Both NSE & BSE"]:
        tickers_to_scan.append(f"{sym}.BO")

# -------------------------------------------------------------
# 4. PRE-FILTER THRESHOLDS
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("📈 Pre-Filter Thresholds")
min_3m = st.sidebar.number_input("Minimum 3-Month Return (%)", value=15, step=5)
min_6m = st.sidebar.number_input("Minimum 6-Month Return (%)", value=25, step=5)

# -------------------------------------------------------------
# 5. VECTORIZED PRE-FILTERING ENGINE (LIGHTNING FAST)
# -------------------------------------------------------------
if st.button("🚀 Execute Lightning Pre-Filter Scan", use_container_width=True):
    if not tickers_to_scan:
        st.warning("No tickers to scan.")
    else:
        with st.spinner(f"Step 1: Downloading raw price data for {len(tickers_to_scan)} stocks..."):
            try:
                # 1. Bulk download only closing prices to save memory
                data = yf.download(tickers_to_scan, period="1y", threads=True, progress=False)
                
                # Format dataframe handling based on single or multiple tickers
                if len(tickers_to_scan) == 1:
                    close_prices = data[['Close']]
                    close_prices.columns = tickers_to_scan
                else:
                    close_prices = data['Close']
                
                # 2. Vectorized calculation for all stocks simultaneously
                current_price = close_prices.iloc[-1]
                p_3m = close_prices.iloc[-63] if len(close_prices) >= 63 else pd.Series(dtype=float)
                p_6m = close_prices.iloc[-126] if len(close_prices) >= 126 else pd.Series(dtype=float)
                p_9m = close_prices.iloc[-189] if len(close_prices) >= 189 else pd.Series(dtype=float)
                
                ret_3m = ((current_price - p_3m) / p_3m) * 100
                ret_6m = ((current_price - p_6m) / p_6m) * 100
                ret_9m = ((current_price - p_9m) / p_9m) * 100
                
                # 3. Create a boolean mask to instantly drop stocks that fail the filter
                mask = (ret_3m >= min_3m) & (ret_6m >= min_6m) & (ret_3m.notna()) & (ret_6m.notna())
                
                # 4. Extract the winning tickers
                passed_tickers = mask[mask].index.tolist()
                
                if not passed_tickers:
                    st.info("No stocks passed your pre-filter. Try lowering the thresholds.")
                else:
                    st.success(f"⚡ Filter reduced {len(tickers_to_scan)} stocks down to {len(passed_tickers)} winners. Processing deep metrics...")
                    
                    results = []
                    # 5. Run deep metrics (Volatility & Momentum) ONLY on the remaining winners
                    for ticker in passed_tickers:
                        try:
                            # 3-Month Volatility calculation
                            ticker_closes = close_prices[ticker].iloc[-63:].dropna()
                            daily_returns = ticker_closes.pct_change().dropna()
                            vol_3m = daily_returns.std() * np.sqrt(252) * 100
                            vol_divisor = vol_3m if vol_3m > 0 else 1.0
                            
                            # Momentum Formulas
                            r3 = ret_3m[ticker]
                            r6 = ret_6m[ticker]
                            r9 = ret_9m[ticker] if pd.notna(ret_9m[ticker]) else 0
                            
                            weighted_mom = (3 * r3 + 2 * r6 + 1 * r9) / vol_divisor
                            
                            exchange = "BSE" if ".BO" in ticker else "NSE"

                            results.append({
                                "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
                                "Exch": exchange,
                                "Price": round(current_price[ticker], 2),
                                "3M %": round(r3, 1),
                                "6M %": round(r6, 1),
                                "3M Vol %": round(vol_3m, 1),
                                "Momentum Score": round(weighted_mom, 2)
                            })
                        except Exception:
                            continue
                    
                    final_df = pd.DataFrame(results).sort_values(by="Momentum Score", ascending=False).reset_index(drop=True)
                    st.session_state['screened_results'] = final_df
                    
            except Exception as e:
                st.error(f"Engine Error: {e}")

# -------------------------------------------------------------
# 6. RESULTS & GEMINI API INTEGRATION
# -------------------------------------------------------------
if 'screened_results' in st.session_state and not st.session_state['screened_results'].empty:
    df_display = st.session_state['screened_results']
    st.dataframe(df_display, use_container_width=True)
    
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Winners to CSV", data=csv, file_name="Filtered_Market_Scan.csv", mime="text/csv")
    
    st.markdown("---")
    st.subheader("2. 🤖 Gemini Deep Forensic Analysis")
    selected_stock = st.selectbox("Select a filtered winner to audit:", df_display['Symbol'].tolist())
    
    if st.button(f"🔍 Audit {selected_stock}", use_container_width=True):
        if not gemini_api_key:
            st.error("Please enter your free Gemini API key in the left sidebar.")
        else:
            with st.spinner(f"Gemini AI is analyzing {selected_stock}..."):
                try:
                    stock_data = df_display[df_display['Symbol'] == selected_stock].iloc[0]
                    
                    genai.configure(api_key=gemini_api_key)
                    model = genai.GenerativeModel('gemini-1.5-flash')
                    
                    prompt = f"""
                    Act as a Senior SEBI Quant Analyst. 
                    Analyze the Indian stock: {selected_stock} (Exchange: {stock_data['Exch']})
                    Current Price: ₹{stock_data['Price']}
                    3-Month Return: {stock_data['3M %']}%
                    6-Month Return: {stock_data['6M %']}%
                    Volatility: {stock_data['3M Vol %']}%
                    
                    Provide a forensic breakdown:
                    1. Promoter holding risks and recent FII/DII activity for {selected_stock}.
                    2. Wyckoff Distribution Risk: Is this a genuine institutional markup or a retail trap?
                    3. Fundamental Health Check (Valuations/Earnings).
                    4. Positional Recommendation (Action, Stop Loss ₹, and Exit Strategy).
                    """
                    
                    response = model.generate_content(prompt)
                    st.markdown("### 📋 AI Forensic Report")
                    st.markdown(response.text)
                except Exception as e:
                    st.error(f"Gemini API Error: {e}")
        
