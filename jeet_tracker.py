import streamlit as st
import plotly.express as px
import requests
import time
from datetime import datetime
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd

# Initialize session state for caching and key counter
if "cached_data" not in st.session_state:
    st.session_state.cached_data = []
if "counter" not in st.session_state:
    st.session_state.counter = 0

# Function to fetch transaction data from DexScreener API
def fetch_jeet_data():
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[429])
    session.mount("https://", HTTPAdapter(max_retries=retries))
    try:
        # Replace with your DexScreener API endpoint or token pair URL
        url = "https://api.dexscreener.com/latest/dex/pairs/ethereum/0x123..."  # Example URL
        response = session.get(url, timeout=5)
        response.raise_for_status()
        data = response.json()
        # Process data to extract transactions (adjust based on API response structure)
        transactions = data.get("pairs", [])  # Example: list of transactions
        # Simulate jeet detection (e.g., filter trades with negative profit)
        jeets = [
            {
                "timestamp": tx.get("timestamp", datetime.now().isoformat()),
                "wallet": tx.get("maker", "Unknown"),
                "loss": tx.get("profit", 0) * -1 if tx.get("profit", 0) < 0 else 0
            }
            for tx in transactions
        ]
        return jeets
    except requests.exceptions.RequestException as e:
        st.warning(f"API error: {e}. Using cached data.")
        return st.session_state.cached_data

# App title and sidebar
st.title("Jeet Tracker")
st.sidebar.header("Controls")
refresh = st.sidebar.button("Refresh Data", key="sidebar_refresh_btn")

# Main content with dynamic updates
placeholder = st.empty()
with placeholder.container():
    # Generate unique key suffix
    timestamp = datetime.now().strftime("%H%M%S%f")
    st.session_state.counter += 1
    counter = st.session_state.counter

    # Fetch data
    data = fetch_jeet_data()
    if data:
        st.session_state.cached_data = data
    else:
        data = st.session_state.cached_data

    # Display metrics
    st.write(f"Total Jeet Transactions: {len(data)}", key=f"count_{counter}_{timestamp}")
    
    # Display data table
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, key=f"table_{counter}_{timestamp}")
        
        # Plotly chart for losses over time
        fig = px.line(
            df,
            x="timestamp",
            y="loss",
            title="Jeet Losses Over Time",
            labels={"timestamp": "Time", "loss": "Loss (USD)"}
        )
        st.plotly_chart(fig, key=f"chart_{counter}_{timestamp}")
    else:
        st.write("No data available.", key=f"nodata_{counter}_{timestamp}")

# Auto-refresh every 10 seconds (adjust to avoid 429 errors)
if not refresh:  # Only auto-refresh if manual refresh not clicked
    time.sleep(10)
    st.rerun()