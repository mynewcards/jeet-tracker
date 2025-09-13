import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

# Page config
st.set_page_config(page_title="Jeet Tracker", page_icon="🚀", layout="wide")

st.title("🚨 Jeet Tracker: Track Premature Crypto Sellers!")
st.markdown("""
This app tracks potential 'jeets'—traders who exit early and miss gains. 
We monitor price dips in top cryptos and simulate wallet sells. 
Data from CoinGecko API. Input a Solana wallet to check for jeet behavior.
""")

@st.cache_data(ttl=300)  # Cache for 5 minutes to avoid rate limits
def fetch_crypto_data():
    """Fetch top 10 cryptos from CoinGecko and detect potential jeet signals (recent dips)."""
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,ethereum,solana&vs_currencies=usd&include_24hr_change=true"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Convert to DataFrame
        df_data = []
        for coin, info in data.items():
            change_24h = info.get('usd_24h_change', 0)
            is_jeet_risk = change_24h < -5  # Simple rule: >5% dip might indicate jeets
            df_data.append({
                'Coin': coin.title(),
                'Price (USD)': info.get('usd', 0),
                '24h Change (%)': round(change_24h, 2),
                'Jeet Risk': 'High 🚨' if is_jeet_risk else 'Low ✅'
            })
        
        df = pd.DataFrame(df_data)
        return df if not df.empty else pd.DataFrame()  # Fallback to empty DF
    except (requests.RequestException, ValueError, KeyError) as e:
        st.error(f"API fetch failed: {e}. Using mock data.")
        # Mock data fallback
        mock_df = pd.DataFrame({
            'Coin': ['Bitcoin', 'Ethereum', 'Solana'],
            'Price (USD)': [60000, 3000, 150],
            '24h Change (%)': [-3.2, -7.5, -2.1],
            'Jeet Risk': ['Low ✅', 'High 🚨', 'Low ✅']
        })
        return mock_df

def simulate_wallet_jeets(wallet_address):
    """Simulate jeet detection for a wallet (replace with real Solana RPC for production)."""
    # Mock simulation: Generate fake transactions
    transactions = []
    if wallet_address:
        # Simulate 5 recent txs
        for i in range(5):
            tx_time = datetime.now() - timedelta(hours=i*2)
            is_sell = i % 2 == 0  # Alternate buy/sell
            profit = -10 if is_sell else 5  # Negative for early sells
            is_jeet = profit < -5  # Detected jeet if sold at loss/dip
            transactions.append({
                'Time': tx_time.strftime('%Y-%m-%d %H:%M'),
                'Type': 'Sell' if is_sell else 'Buy',
                'Profit/Loss (%)': profit,
                'Jeet Detected': 'Yes 🚨' if is_jeet else 'No ✅'
            })
    return pd.DataFrame(transactions) if transactions else pd.DataFrame()

# Sidebar for inputs
st.sidebar.header("Wallet Input")
wallet_address = st.sidebar.text_input("Enter Solana Wallet Address (e.g., for simulation):")

# Fetch and display data
with st.spinner("Fetching crypto data..."):
    crypto_df = fetch_crypto_data()

if not crypto_df.empty:
    st.subheader("📊 Top Crypto Jeet Risk Dashboard")
    st.dataframe(crypto_df, use_container_width=True)
    
    # Chart
    st.subheader("📈 24h Price Changes")
    st.bar_chart(crypto_df.set_index('Coin')['24h Change (%)'])
    
    # Metrics
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Coins Tracked", len(crypto_df))
    with col2:
        high_risk = len(crypto_df[crypto_df['Jeet Risk'] == 'High 🚨'])
        st.metric("High Jeet Risk Coins", high_risk)
    with col3:
        avg_change = crypto_df['24h Change (%)'].mean()
        st.metric("Avg 24h Change", f"{avg_change:.2f}%")
else:
    st.warning("No data retrieved. Check connection or try again.")

# Wallet analysis
if wallet_address:
    st.subheader(f"💼 Wallet Analysis: {wallet_address[:8]}...")
    wallet_df = simulate_wallet_jeets(wallet_address)
    
    if not wallet_df.empty:
        st.dataframe(wallet_df, use_container_width=True)
        
        # Jeet count
        jeet_count = len(wallet_df[wallet_df['Jeet Detected'] == 'Yes 🚨'])
        st.metric("Jeets Detected in Last 10 Hours", jeet_count)
        
        if jeet_count > 2:
            st.error("⚠️ High jeet activity! Consider HODLing longer.")
        else:
            st.success("✅ Low jeet risk. Good holding strategy!")
    else:
        st.info("No transactions simulated. Enter a valid address.")
else:
    st.info("Enter a wallet address in the sidebar to analyze.")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}. Data simulated for demo; integrate real APIs for production.")