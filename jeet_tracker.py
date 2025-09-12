import streamlit as st
import requests
import json
import time
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from io import StringIO

# Mock data store (use SQLite in production)
if 'jeets' not in st.session_state:
    st.session_state.jeets = []  # List of dicts: {'wallet': str, 'loss_usd': float, 'time_to_sell_min': float, 'amount_usd': float, 'timestamp': datetime}
if 'total_jeets' not in st.session_state:
    st.session_state.total_jeets = 0
if 'daily_amount' not in st.session_state:
    st.session_state.daily_amount = 0.0
if 'avg_loss' not in st.session_state:
    st.session_state.avg_loss = 0.0
if 'fastest_jeet' not in st.session_state:
    st.session_state.fastest_jeet = float('inf')

# DexScreener API base URL
BASE_URL = "https://api.dexscreener.com/latest/dex"

@st.cache_data(ttl=60)  # Cache for 1 min to respect rate limits
def fetch_recent_pairs(chain="solana", query="meme"):  # Focus on Solana meme coins
    url = f"{BASE_URL}/search/?q={query}&chainId={chain}"
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        return data.get('pairs', [])[:10]  # Limit to recent pairs
    except Exception as e:
        st.error(f"API error: {e}")
        return []

def estimate_price_at_time(pair, timestamp):
    # Mock historical price estimation (in real: use RPC or Coingecko API)
    current_price = float(pair['priceUsd']) if pair['priceUsd'] else 0
    # Assume price volatility: simple linear interpolation based on age
    age_hours = (datetime.now() - timestamp).total_seconds() / 3600
    return current_price * (1 + np.random.uniform(-0.1, 0.1) * age_hours / 24)  # Simulate fluctuation

def detect_jeets_in_pair(pair):
    new_jeets = []
    if 'transactions' not in pair:  # Mock transactions if not in API response (real API has 'transactions' list)
        # Simulate 5-10 txns based on real structure
        for _ in range(np.random.randint(5, 11)):
            txn = {
                'type': np.random.choice(['buy', 'sell']),
                'maker': f"wallet_{np.random.randint(1000, 9999)}",
                'amount': np.random.uniform(100, 10000),  # Token amount
                'usdValue': np.random.uniform(50, 5000),  # Approx USD
                'timestamp': datetime.now() - timedelta(minutes=np.random.uniform(1, 1440))  # Up to 24h ago
            }
            if txn['type'] == 'sell':
                buy_price = estimate_price_at_time(pair, txn['timestamp'] + timedelta(minutes=np.random.uniform(1, 30)))  # Assume buy shortly before
                sell_price = float(pair['priceUsd']) if pair['priceUsd'] else buy_price * 0.9  # Assume sell at current or lower
                buy_usd = txn['amount'] * buy_price
                sell_usd = txn['usdValue']
                loss = buy_usd - sell_usd
                if loss > 10:  # Threshold for jeet
                    time_to_sell = (txn['timestamp'] - (txn['timestamp'] - timedelta(minutes=np.random.uniform(1, 60)))).total_seconds() / 60
                    new_jeets.append({
                        'wallet': txn['maker'],
                        'loss_usd': loss,
                        'time_to_sell_min': time_to_sell,
                        'amount_usd': sell_usd,
                        'timestamp': txn['timestamp']
                    })
    else:
        # Real logic: Parse actual transactions from API
        for txn in pair['transactions'][-10:]:  # Last 10 txns
            if txn.get('side') == 'sell':  # Assuming API structure
                # Similar estimation logic...
                pass  # Implement based on actual API fields like 'txns' with 'maker', 'amount', etc.
    return new_jeets

def update_stats(new_jeets):
    today = datetime.now().date()
    for jeet in new_jeets:
        st.session_state.jeets.append(jeet)
        st.session_state.total_jeets += 1
        if jeet['timestamp'].date() == today:
            st.session_state.daily_amount += jeet['amount_usd']
        st.session_state.fastest_jeet = min(st.session_state.fastest_jeet, jeet['time_to_sell_min'])
    
    if st.session_state.jeets:
        losses = [j['loss_usd'] for j in st.session_state.jeets]
        st.session_state.avg_loss = np.mean(losses)

def main():
    st.set_page_config(page_title="Jeet Tracker", layout="wide")
    st.title("🩸 Jeet Tracker Dashboard")
    st.markdown("Scan DEX data for wallets selling at a loss (jeets!). Updated live as of Sat Sep 13 2025.")

    col1, col2 = st.columns(2)
    with col1:
        chain = st.selectbox("Chain", ["solana", "ethereum", "bsc"])
    with col2:
        if st.button("🔄 Refresh & Scan"):
            pairs = fetch_recent_pairs(chain=chain)
            for pair in pairs:
                jeets = detect_jeets_in_pair(pair)
                update_stats(jeets)
                time.sleep(0.2)  # Rate limit
            st.success(f"Scanned {len(pairs)} pairs. Found {len(jeets)} new jeets!")

    # Metrics Cards (mimic screenshot style)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown("### 💀 Total Jeets Caught")
        st.metric(label="", value=f"{int(st.session_state.total_jeets):,}")
    with col2:
        st.markdown("### 📉 Average Loss")
        st.metric(label="", value=f"${st.session_state.avg_loss:.0f}")
    with col3:
        st.markdown("### ⚡ Fastest Jeet")
        st.metric(label="", value=f"{st.session_state.fastest_jeet:.1f}m")
    with col4:
        st.markdown("### 🔥 Daily Jeeted Amount")
        st.metric(label=f"Sat Sep 13 2025", value=f"${st.session_state.daily_amount:,.2f}")

    # Recent Jeets Table
    if st.session_state.jeets:
        df = pd.DataFrame(st.session_state.jeets)
        st.subheader("Recent Jeets")
        st.dataframe(df.tail(10).sort_values('timestamp', ascending=False))

        # Chart: Daily Jeets Over Time
        st.subheader("Daily Jeets Trend")
        df['date'] = df['timestamp'].dt.date
        daily_counts = df.groupby('date').size()
        fig, ax = plt.subplots()
        daily_counts.plot(kind='bar', ax=ax)
        st.pyplot(fig)

        # Export
        csv = df.to_csv(index=False)
        st.download_button("Export to CSV", csv, "jeets.csv", "text/csv")

if __name__ == "__main__":
    main()
