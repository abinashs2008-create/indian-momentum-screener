import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import requests
import io
import google.generativeai as genai
from datetime import datetime, timedelta

st.set_page_config(page_title="Indian Market Master Screener", layout="wide")

st.title("🇮🇳 Master Indian Market & IPO Screener")
st.caption("Live connection to NSE/BSE Master Databases, Exhaustive Sectors, and Gemini AI Analysis.")

# -------------------------------------------------------------
# 1. LIVE NSE/BSE MASTER DATABASE & IPO FETCHER
# -------------------------------------------------------------
@st.cache_data(ttl=43200)  # Cache for 12 hours to prevent server bans
def fetch_master_equity_list():
    """Fetches the official live NSE Master List including all listing dates (IPOs)."""
    try:
        # Official NSE Equity URL containing Symbol, Company Name, and Listing Date
        url = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        df = pd.read_csv(io.StringIO(response.text))
        
        # Clean columns and format dates
        df.rename(columns=lambda x: x.strip(), inplace=True)
        df['DATE OF LISTING'] = pd.to_datetime(df['DATE OF LISTING'], format='%d-%b-%Y', errors='coerce')
        
        # Append .NS suffix for Yahoo Finance compatibility
        df['YF_Ticker'] = df['SYMBOL'] + ".NS"
        return df
    except Exception as e:
        st.error(f"Failed to fetch live NSE database: {e}")
        return pd.DataFrame()

master_df = fetch_master_equity_list()

# -------------------------------------------------------------
# 2. EXHAUSTIVE BROKERAGE/SCREENER.IN SECTORS
# -------------------------------------------------------------
# Comprehensive list mimicking major brokerage categorizations
BROKERAGE_SECTORS = {
    "🚜 Agro Chemicals & Fertilizers": ["UPL", "PIIND", "COROMANDEL", "CHAMBLFERT", "FACT", "GNFC"],
    "✈️ Airlines & Aviation": ["INDIGO", "SPICEJET", "TAJGVK"],
    "⚙️ Auto & Auto Ancillaries": ["TATAMOTORS", "M&M", "MARUTI", "BAJAJ-AUTO", "BOSCHLTD", "MOTHERSON", "MRF"],
    "🏦 Banks (Public & Private)": ["HDFCBANK", "ICICIBANK", "SBIN", "KOTAKBANK", "AXISBANK", "PNB", "BANKBARODA"],
    "🏗️ Capital Goods & Defense": ["LT", "HAL", "BEL", "MAZDOCK", "BDL", "SIEMENS", "ABB", "CGPOWER"],
    "🧱 Cement & Construction": ["ULTRACEMCO", "AMBUJACEM", "SHREECEM", "ACC", "DALBHARAT"],
    "🧪 Chemicals & Specialty": ["SRF", "AARTIIND", "DEEPAKNTR", "TATACHEM", "NAVINFLUOR"],
    "📺 Consumer Durables & Electronics": ["TITAN", "DIXON", "HAVELLS", "VOLTAS", "WHIRLPOOL", "BLUESTARCO"],
    "🛒 FMCG & Retail": ["ITC", "HINDUNILVR", "NESTLEIND", "BRITANNIA", "TATACONSUM", "DMART", "TRENT"],
    "💸 Finance & NBFC": ["BAJFINANCE", "CHOLAFIN", "MUTHOOTFIN", "SHRIRAMFIN", "PFC", "RECLTD"],
    "🏥 Healthcare & Hospitals": ["APOLLOHOSP", "MAXHEALTH", "FORTIS", "GLOBALVECT"],
    "💻 IT - Software & Services": ["TCS", "INFY", "HCLTECH", "WIPRO", "TECHM", "LTIM", "PERSISTENT"],
    "🚢 Logistics & Marine Ports": ["ADANIPORTS", "CONCOR", "DELHIVERY", "BLUEDART"],
    "⛏️ Metals & Mining": ["TATASTEEL", "JSWSTEEL", "HINDALCO", "VEDL", "NMDC", "COALINDIA"],
    "📦 Packaging & Paper": ["UFO", "POLYPLEX", "EPL", "JKPAPER", "CENTURYTEX"],
    "🛢️ Petrochemicals, Oil & Gas": ["RELIANCE", "ONGC", "IOC", "BPCL", "GAIL", "PETRONET"],
    "💊 Pharmaceuticals": ["SUNPHARMA", "CIPLA", "DRREDDY", "DIVISLAB", "LUPIN", "AUROPHARMA"],
    "⚡ Power & Green Energy": ["NTPC", "POWERGRID", "TATAPOWER", "ADANIGREEN", "SUZLON", "IREDA"],
    "🏢 Real Estate & REITs": ["DLF", "MACROTECH", "GODREJPROP", "OBEROIRLTY", "PRESTIGE"],
    "📡 Telecom & Media": ["BHARTIARTL", "IDEA", "INDUSTOWER", "ZEEL", "SUNTV"],
    "📱 New-Age Tech (Startups)": ["ZOMATO", "PAYTM", "NYKAA", "POLICYBZR", "JIOFIN"]
}

# -------------------------------------------------------------
# 3. UI: UNIVERSE SELECTION & IPO TRACKER
# -------------------------------------------------------------
st.sidebar.header("⚙️ System Configuration")
gemini_api_key = st.sidebar.text_input("🔑 Gemini API Key:", type="password")

scan_mode = st.sidebar.radio(
    "Select Scanning Mode:",
    [
        "All Listed IPOs (Filter by Date)", 
        "Brokerage Sectors (Exhaustive)", 
        "Broad Market (Entire NSE/BSE)",
        "Manual Input (NSE/BSE Custom)"
    ]
)

tickers_to_scan = []

st.subheader("1. 🎯 Define Target Universe")

if scan_mode == "All Listed IPOs (Filter by Date)":
    st.write("Scan companies based on their historical IPO/Listing Date.")
    min_year = st.slider("Select IPO Listing Year Range:", min_value=1995, max_value=datetime.now().year, value=(2020, 2026))
    
    if not master_df.empty:
        # Filter IPOs based on listing date range
        ipo_df = master_df[(master_df['DATE OF LISTING'].dt.year >= min_year[0]) & 
                           (master_df['DATE OF LISTING'].dt.year <= min_year[1])]
        tickers_to_scan = ipo_df['YF_Ticker'].tolist()
        st.info(f"Found **{len(tickers_to_scan)} IPOs** listed between {min_year[0]} and {min_year[1]}.")

elif scan_mode == "Brokerage Sectors (Exhaustive)":
    selected_sector = st.selectbox("Select Industry/Sector:", list(BROKERAGE_SECTORS.keys()))
    # Automatically append .NS for NSE
    tickers_to_scan = [f"{t}.NS" for t in BROKERAGE_SECTORS[selected_sector]]
    st.info(f"Loaded **{len(tickers_to_scan)} stocks** in {selected_sector}.")

elif scan_mode == "Broad Market (Entire NSE/BSE)":
    st.warning("⚠️ Scanning all 2000+ stocks at once may time out your mobile browser. It is recommended to scan the top 500 by Market Cap.")
    limit = st.slider("Select number of top stocks to scan:", 50, 2000, 250)
    if not master_df.empty:
        tickers_to_scan = master_df['YF_Ticker'].head(limit).tolist()
        
elif scan_mode == "Manual Input (NSE/BSE Custom)":
    st.write("For NSE stocks, use `.NS` (e.g., RELIANCE.NS). For BSE stocks, use `.BO` (e.g., RELIANCE.BO).")
    custom_in = st.text_input("Enter symbols separated by commas:", "ZOMATO.NS, SUZLON.NS, MRF.BO, INFY.BO")
    tickers_to_scan = [s.strip().upper() for s in custom_in.split(",") if s.strip()]

# -------------------------------------------------------------
# 4. MOMENTUM PARAMETERS & SAFETY FILTERS
# -------------------------------------------------------------
st.sidebar.markdown("---")
st.sidebar.header("📈 Momentum Filters")
min_3m = st.sidebar.number_input("Min 3-Month Return (%)", value=10, step=5)
min_6m = st.sidebar.number_input("Min 6-Month Return (%)", value=15, step=5)

st.sidebar.markdown("---")
st.sidebar.header("🛡️ Trap Protection")
require_trend = st.sidebar.checkbox("Price must be > 200 EMA (Uptrend)", value=True)
require_volume = st.sidebar.checkbox("Current Vol > 20D Avg Vol", value=False)

# -------------------------------------------------------------
# 5. HIGH-PERFORMANCE BATCH SCANNING ENGINE
# -------------------------------------------------------------
if st.button("🚀 Execute Market Scan", use_container_width=True):
    if not tickers_to_scan:
        st.warning("No tickers to scan.")
    else:
        with st.spinner(f"Downloading live market data for {len(tickers_to_scan)} stocks..."):
            try:
                # Fast chunked downloading
                data = yf.download(tickers_to_scan, period="1y", group_by='ticker', threads=True, progress=False)
                
                results = []
                for ticker in tickers_to_scan:
                    try:
                        df = data[ticker].dropna() if len(tickers_to_scan) > 1 else data.dropna()
                        
                        if len(df) < 189:
                            continue  # Skip newly listed companies without 9 months of data
                            
                        current_price = df['Close'].iloc[-1]
                        
                        # Safety Filters
                        if require_trend:
                            ema_200 = df['Close'].ewm(span=200, adjust=False).mean().iloc[-1]
                            if current_price < ema_200:
                                continue
                        
                        if require_volume:
                            vol_20avg = df['Volume'].iloc[-20:].mean()
                            curr_vol = df['Volume'].iloc[-1]
                            if curr_vol < vol_20avg:
                                continue

                        # Returns Calculation
                        p_3m = df['Close'].iloc[-63]
                        p_6m = df['Close'].iloc[-126]
                        p_9m = df['Close'].iloc[-189]
                        
                        ret_3m = ((current_price - p_3m) / p_3m) * 100
                        ret_6m = ((current_price - p_6m) / p_6m) * 100
                        ret_9m = ((current_price - p_9m) / p_9m) * 100
                        
                        if ret_3m < min_3m or ret_6m < min_6m:
                            continue
                            
                        # Volatility & Momentum
                        daily_returns = df['Close'].iloc[-63:].pct_change().dropna()
                        vol_3m = daily_returns.std() * np.sqrt(252) * 100
                        vol_divisor = vol_3m if vol_3m > 0 else 1.0
                        
                        weighted_mom = (3 * ret_3m + 2 * ret_6m + 1 * ret_9m) / vol_divisor
                        
                        # Determine exchange based on suffix
                        exchange = "BSE" if ".BO" in ticker else "NSE"

                        results.append({
                            "Symbol": ticker.replace(".NS", "").replace(".BO", ""),
                            "Exch": exchange,
                            "Price": round(current_price, 2),
                            "3M %": round(ret_3m, 1),
                            "6M %": round(ret_6m, 1),
                            "3M Vol %": round(vol_3m, 1),
                            "Momentum Score": round(weighted_mom, 2)
                        })
                    except Exception:
                        continue
                
                if results:
                    final_df = pd.DataFrame(results).sort_values(by="Momentum Score", ascending=False).reset_index(drop=True)
                    st.session_state['screened_results'] = final_df
                    st.success(f"✅ Discovered {len(final_df)} winning stocks!")
                else:
                    st.session_state['screened_results'] = pd.DataFrame()
                    st.info("No stocks passed your strict filters today.")
            except Exception as e:
                st.error(f"Engine Error: {e}")

# -------------------------------------------------------------
# 6. RESULTS & GEMINI API INTEGRATION
# -------------------------------------------------------------
if 'screened_results' in st.session_state and not st.session_state['screened_results'].empty:
    df_display = st.session_state['screened_results']
    st.dataframe(df_display, use_container_width=True)
    
    csv = df_display.to_csv(index=False).encode('utf-8')
    st.download_button("📥 Export Results (CSV)", data=csv, file_name="Market_Scan.csv", mime="text/csv")
    
    st.markdown("---")
    st.subheader("2. 🤖 Gemini Deep Forensic Analysis")
    selected_stock = st.selectbox("Select a stock to audit for Institutional Traps:", df_display['Symbol'].tolist())
    
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
    
