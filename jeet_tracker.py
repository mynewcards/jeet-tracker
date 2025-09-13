import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time
from collections import defaultdict, deque

# Configuration
DEXSCREENER_BASE = "https://api.dexscreener.com/latest/dex"
COINGECKO_BASE = "https://api.coingecko.com/api/v3"
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
SOLSCAN_BASE = "https://solscan.io/tx/"
SAMPLE_WALLET = "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1"  # Replace with real wallet
POLL_INTERVAL = 60  # seconds
LOSS_THRESHOLD = 100  # USD for leaderboard
HOLD_TIME_MIN = 5  # minutes for jeet detection

# Helper Functions
@st.cache_data(ttl=300)
def get_dexscreener_trending_solana():
    """Get trending Solana tokens/pairs from DexScreener."""
    try:
        url = f"{DEXSCREENER_BASE}/tokens/solana"
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        pairs = resp.json().get('pairs', [])
        # Highly jeeted: >20 sells or >10% price drop in last hour
        highly_jeeted = [
            p for p in pairs
            if (p.get('txns', {}).get('h1', {}).get('sells', 0) > 20 or
                p.get('priceChange', {}).get('h1', 0) < -10)
        ]
        return highly_jeeted[:10]  # Top 10
    except:
        return []

@st.cache_data(ttl=300)
def get_token_price_coingecko(token_symbol, date):
    """Get historical price from CoinGecko."""
    try:
        cg_id = {'SOL': 'solana', 'USDC': 'usd-coin'}.get(token_symbol, 'solana')
        url = f"{COINGECKO_BASE}/coins/{cg_id}/history?date={date.strftime('%d-%m-%Y')}"
        resp = requests.get(url, timeout=5)
        resp.raise_for_status()
        data = resp.json()
        return data.get('market_data', {}).get('current_price', {}).get('usd', 0)
    except:
        return 0.001  # Fallback for meme tokens

def rpc_call(method, params=[]):
    """Call Solana RPC."""
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    try:
        resp = requests.post(RPC_ENDPOINT, json=payload, timeout=10)
        resp.raise_for_status()
        return resp.json().get('result')
    except:
        return None

def get_signatures(wallet, before_sig=None, limit=100):
    """Get transaction signatures for wallet."""
    params = [wallet, {"limit": limit, "commitment": "confirmed"}]
    if before_sig:
        params[1]["before"] = before_sig
    return rpc_call("getSignaturesForAddress", params)

def get_transaction_details(sig):
    """Get transaction details."""
    return rpc_call("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])

def analyze_wallet_trades(wallet, lookback_hours=24):
    """Analyze wallet for jeets using Solana RPC."""
    cutoff_time = datetime.now() - timedelta(hours=lookback_hours)
    signatures = get_signatures(wallet)
    if not signatures:
        return []

    buys = defaultdict(deque)  # token: deque(amount, time, price)
    jeets = []
    for sig_info in signatures:
        timestamp = datetime.fromtimestamp(sig_info['blockTime'])
        if timestamp < cutoff_time:
            continue
        tx = get_transaction_details(sig_info['signature'])
        if not tx or 'meta' not in tx:
            continue

        pre_balances = {bal['owner']: bal for bal in tx.get('meta', {}).get('preTokenBalances', [])}
        post_balances = {bal['owner']: bal for bal in tx.get('meta', {}).get('postTokenBalances', [])}

        for account in post_balances:
            if account != wallet:
                continue
            mint = post_balances[account].get('mint')
            if not mint:
                continue
            pre_amount = float(pre_balances.get(account, {}).get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
            post_amount = float(post_balances[account].get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
            amount_change = post_amount - pre_amount
            price = get_token_price_coingecko(mint[:8], timestamp)

            if amount_change > 0:
                buys[mint].append((amount_change, timestamp, price))
            elif amount_change < 0:
                total_sold = 0
                amount_sold = abs(amount_change)
                sell_usd = amount_sold * price
                while buys[mint] and total_sold < amount_sold:
                    buy_amount, buy_time, buy_price = buys[mint][0]
                    hold_min = (timestamp - buy_time).total_seconds() / 60
                    amt_used = min(buy_amount, amount_sold - total_sold)
                    buy_usd = amt_used * buy_price
                    sell_portion = amt_used * price
                    loss = buy_usd - sell_portion
                    if loss > LOSS_THRESHOLD and hold_min < HOLD_TIME_MIN:
                        jeets.append({
                            'token': mint[:8],
                            'hold_time_min': hold_min,
                            'loss_usd': loss,
                            'date': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                            'tx_sig': sig_info['signature']
                        })
                    total_sold += amt_used
                    if amt_used < buy_amount:
                        buys[mint][0] = (buy_amount - amt_used, buy_time, buy_price)
                    else:
                        buys[mint].popleft()
        time.sleep(0.1)  # Rate limit
    return jeets

# Streamlit App
st.title("🦵 Jeet Tracker: Solana Meme Coin Sell/Loss Tracker")
st.markdown("Track highly jeeted Solana tokens and wallet losses using DexScreener, CoinGecko, and Solana RPC. No API keys needed.")

# Section 1: Recent Highly Jeeted Tokens
st.header("Recent Highly Jeeted Tokens")
if st.button("Refresh Recent Jeets"):
    with st.spinner("Fetching from DexScreener..."):
        trending = get_dexscreener_trending_solana()
        recent_jeets = []
        for pair in trending:
            token = pair['baseToken']['address']
            symbol = pair['baseToken']['symbol']
            # Use pair creator as sample wallet; in prod, parse txns for sellers
            wallet = pair.get('pairCreator', SAMPLE_WALLET)
            jeets = analyze_wallet_trades(wallet, lookback_hours=1)
            if jeets:
                j = jeets[0]  # Take first jeet
                recent_jeets.append({
                    'Token': symbol,
                    'Wallet': wallet,
                    'Solscan Link': f"[View]({SOLSCAN_BASE}{j['tx_sig']})",
                    'Hold Time (min)': f"{j['hold_time_min']:.2f}",
                    'Loss (USD)': f"${j['loss_usd']:.2f}",
                    'Date': j['date']
                })
        if recent_jeets:
            st.table(pd.DataFrame(recent_jeets))
        else:
            st.info("No highly jeeted tokens detected recently.")

# Section 2: Wallet Search
st.header("Search Wallet for Jeets")
wallet_input = st.text_input("Enter Solana Wallet Address", value=SAMPLE_WALLET)
if wallet_input:
    with st.spinner("Analyzing wallet via Solana RPC..."):
        jeets = analyze_wallet_trades(wallet_input, lookback_hours=24)
        if jeets:
            df_wallet = pd.DataFrame(jeets)
            df_wallet['Solscan Link'] = df_wallet['tx_sig'].apply(lambda x: f"[View]({SOLSCAN_BASE}{x})")
            st.table(df_wallet[['token', 'hold_time_min', 'loss_usd', 'date', 'Solscan Link']])
        else:
            st.warning("No significant jeets found for this wallet in the last 24 hours.")

# Section 3: Daily Jeet Leaderboard
st.header("Daily Jeet Leaderboard (Today)")
today = datetime.utcnow().date()
if st.button("Update Leaderboard"):
    with st.spinner("Fetching daily data..."):
        all_jeets = []
        trending = get_dexscreener_trending_solana()
        for pair in trending[:5]:  # Sample top 5
            wallet = pair.get('pairCreator', SAMPLE_WALLET)
            jeets = analyze_wallet_trades(wallet, lookback_hours=24)
            for j in jeets:
                if datetime.strptime(j['date'], '%Y-%m-%d %H:%M:%S').date() == today:
                    j['wallet'] = wallet
                    all_jeets.append(j)
        if all_jeets:
            df_all = pd.DataFrame(all_jeets)
            # Fastest Jeet
            fastest = df_all.loc[df_all['hold_time_min'].idxmin()]
            st.subheader("🏆 Fastest Jeet Today")
            st.write(f"Wallet: {fastest['wallet']}")
            st.write(f"Token: {fastest['token']}, Hold: {fastest['hold_time_min']:.2f} min, "
                     f"Loss: ${fastest['loss_usd']:.2f}, Date: {fastest['date']}")
            # Biggest Loss
            biggest = df_all.loc[df_all['loss_usd'].idxmax()]
            st.subheader("💸 Biggest Loss Today")
            st.write(f"Wallet: {biggest['wallet']}")
            st.write(f"Token: {biggest['token']}, Hold: {biggest['hold_time_min']:.2f} min, "
                     f"Loss: ${biggest['loss_usd']:.2f}, Date: {biggest['date']}")
        else:
            st.info("No jeets today yet.")

st.markdown("---")
st.caption("Data from DexScreener, CoinGecko, Solana RPC. For production, use paid RPC (Helius) and DB for scalability.")