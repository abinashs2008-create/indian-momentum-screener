import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

st.set_page_config(page_title="NSE Positional Screener", layout="centered")

st.title("📊 Positional Momentum Screener")
st.caption("Live mathematical ranking based on 3M/6M/9M returns & 3M volatility.")

# Searchable list of popular Indian companies (Name -> Yahoo Ticker)
STOCK_DIRECTORY = {
    "Reliance Industries": "RELIANCE.NS",
    "Tata Consultancy Services (TCS)": "TCS.NS",
    "HDFC Bank": "HDFCBANK.NS",
    "Infosys": "INFY.NS",
    "ICICI Bank": "ICICIBANK.NS",
    "State Bank of India (SBI)": "SBIN.NS",
    "Bharti Airtel": "BHARTIARTL.NS",
    "ITC Limited": "ITC.NS",
    "Larsen & Toubro": "LT.NS",
    "Tata Motors": "TATAMOTORS.NS",
    "Zomato": "ZOMATO.NS",
    "Suzlon Energy": "SUZLON.NS",
    "Jio Financial Services": "JIOFIN.NS",
    "Adani Enterprises": "ADANIENT.NS",
    "Adani Ports": "ADANIPORTS.NS",
    "Bajaj Finance": "BAJFINANCE.NS",
    "Hindustan Unilever": "HINDUNILVR.NS",
    "Sun Pharma": "SUNPHARMA.NS",
    "Coal India": "COALINDIA.NS",
    "Bharat Electronics (BEL)": "BEL.NS",
    "Hindustan Aeronautics (HAL)": "HAL.NS",
    "Power Grid Corp": "POWERGRID.NS",
    "NTPC": "NTPC.NS",
    "ONGC": "ONGC.NS",
    "Titan Company": "TITAN.NS",
    "Tracxn Technologies": "TRACXN.NS"
}

# Watchlist buckets
WATCHLIST_OPTIONS = {
    "Top 25 Active Stocks (Pre-loaded)": list(STOCK_DIRECTORY.values()),
    "Custom Search by Name": []
}

st.subheader("1. Filter & Universe Selection")
selected_option = st.selectbox("Choose Scanning Mode:", list(WATCHLIST_OPTIONS.keys()))

if selected_option == "Custom Search by Name":
    selected_names = st.multiselect(
        "Search & select companies (type any letter):",
        options=list(STOCK_DIRECTORY.keys()),
        default=["Reliance Industries", "Tata Motors", "Suzlon Energy"]
    )
    tickers_to_scan = [STOCK_DIRECTORY[name] for name in selected_names]
else:
    tickers_to_scan = WATCHLIST_OPTIONS[selected_option]

col1, col2 = st.columns(2)
with col1:
    min_3m = st.number_input("Min 3M Return (%)", value=15)
with col2:
    min_6m = st.number_input("Min 6M Return (%)", value=25)

if st.button("🚀 Run Live Momentum Scan", use_container_width=True):
    if not tickers_to_scan:
        st.warning("Please select at least one stock to scan.")
    else:
        with st.spinner("Downloading market data and running quantitative calculations..."):
            try:
                # Batch download historical price data
                data = yf.download(tickers_to_scan, period="1y", group_by='ticker', progress=False)
                
                results = []
                for ticker in tickers_to_scan:
                    try:
                        df = data[ticker].dropna() if len(tickers_to_scan) > 1 else data.dropna()
                        
                        if len(df) < 189:
                            continue  # Need at least ~9 months of trading days
                            
                        current_price = df['Close'].iloc[-1]
                        p_1m = df['Close'].iloc[-21]
                        p_3m = df['Close'].iloc[-63]
                        p_6m = df['Close'].iloc[-126]
                        p_9m = df['Close'].iloc[-189]
                        
                        ret_1m = ((current_price - p_1m) / p_1m) * 100
                        ret_3m = ((current_price - p_3m) / p_3m) * 100
                        ret_6m = ((current_price - p_6m) / p_6m) * 100
                        ret_9m = ((current_price - p_9m) / p_9m) * 100
                        
                        # 3-Month Volatility calculation
                        daily_returns = df['Close'].iloc[-63:].pct_change().dropna()
                        vol_3m = daily_returns.std() * np.sqrt(252) * 100
                        vol_divisor = vol_3m if vol_3m > 0 else 1.0
                        
                        # Momentum formulas
                        raw_momentum = (ret_3m + ret_6m + ret_9m) / vol_divisor
                        weighted_momentum = (3 * ret_3m + 2 * ret_6m + 1 * ret_9m) / vol_divisor
                        
                        if ret_3m >= min_3m and ret_6m >= min_6m:
                            results.append({
                                "Stock": ticker.replace(".NS", ""),
                                "Price (₹)": round(current_price, 2),
                                "1M %": round(ret_1m, 1),
                                "3M %": round(ret_3m, 1),
                                "6M %": round(ret_6m, 1),
                                "9M %": round(ret_9m, 1),
                                "3M Vol %": round(vol_3m, 1),
                                "Raw Mom": round(raw_momentum, 2),
                                "Weighted Score": round(weighted_momentum, 2)
                            })
                    except Exception:
                        continue
                
                if results:
                    final_df = pd.DataFrame(results).sort_values(by="Weighted Score", ascending=False)
                    st.success(f"Found {len(final_df)} stocks matching your momentum criteria!")
                    st.dataframe(final_df, use_container_width=True)
                else:
                    st.info("No stocks in the selected list met your minimum return thresholds.")
            except Exception as e:
                st.error(f"Error executing scan: {e}")
          
