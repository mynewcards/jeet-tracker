import streamlit as st
import requests
from pycoingecko import CoinGeckoAPI
from solana.rpc.api import Client
from solana.publickey import PublicKey
from datetime import datetime, timedelta
from solders.signature import Signature
import time

# Initialize APIs
cg = CoinGeckoAPI()
solana_client = Client("https://api.mainnet-beta.solana.com")  # Public RPC; use QuickNode/Helius for prod

@st.cache_data(ttl=3600)  # Cache for 1 hour to avoid API rate limits
def get_top_tokens(limit=1000):
    """Fetch top 1000 tokens by 24h volume from CoinGecko and DexScreener."""
    try:
        # CoinGecko: Top tokens by volume (proxy for 30-day activity)
        coins = cg.get_coins_markets(vs_currency='usd', per_page=limit, page=1, order='volume_desc')
        solana_tokens = [(coin['id'], coin['symbol'], coin.get('platforms', {}).get('solana', '')) 
                        for coin in coins if coin.get('platforms', {}).get('solana')]
        # DexScreener: Trending Solana pairs
        ds_url = "https://api.dexscreener.com/latest/dex/search/?q=solana"
        ds_response = requests.get(ds_url).json()
        pairs = ds_response.get('pairs', [])[:500]
        ds_tokens = [(pair['baseToken']['address'].lower(), pair['baseToken']['symbol'], 
                     pair['baseToken']['address']) for pair in pairs]
        # Combine and dedupe
        top_tokens = list(set(solana_tokens + ds_tokens))[:1000]
        return top_tokens
    except Exception as e:
        st.error(f"Error fetching top tokens: {e}")
        return []

def is_sell_transaction(tx, address):
    """Check if transaction is a sell (sends token, receives SOL/USDC)."""
    try:
        parsed_tx = solana_client.get_parsed_transaction(tx.signature, max_supported_transaction_version=0)
        if not parsed_tx.value:
            return False
        pre_balances = parsed_tx.value.meta.pre_token_balances or []
        post_balances = parsed_tx.value.meta.post_token_balances or []
        address_str = str(address)
        for pre, post in zip(pre_balances, post_balances):
            if (pre.owner == address_str and post.owner == address_str and 
                pre.ui_token_amount.amount > post.ui_token_amount.amount):
                mint = pre.mint
                if mint != "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v":  # Exclude USDC
                    instructions = parsed_tx.value.transaction.message.instructions
                    for instr in instructions:
                        if 'programId' in instr and str(instr['programId']) in [
                            '675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8',  # Raydium
                            'JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4'   # Jupiter
                        ]:
                            return True
        return False
    except Exception as e:
        st.warning(f"Error parsing transaction {tx.signature}: {e}")
        return False

def count_jeets(address_str, top_tokens):
    """Count unique tokens sold in past 7 days."""
    try:
        address = PublicKey(address_str)
        end_time = int(time.time())
        start_time = int((datetime.now() - timedelta(days=7)).timestamp())
        signatures = solana_client.get_signatures_for_address(address, limit=1000, commitment='confirmed').value
        jeeted_tokens = set()
        for sig in signatures:
            if sig.block_time < start_time or sig.block_time > end_time:
                continue
            if is_sell_transaction({'signature': sig.signature}, address):
                parsed = solana_client.get_parsed_transaction(sig.signature, max_supported_transaction_version=0)
                if parsed.value and parsed.value.meta.pre_token_balances:
                    mint = parsed.value.meta.pre_token_balances[0].mint
                    if mint in [token[2] for token in top_tokens]:
                        jeeted_tokens.add((mint, next((t[1] for t in top_tokens if t[2] == mint), 'Unknown')))
        return len(jeeted_tokens), list(jeeted_tokens)
    except Exception as e:
        st.error(f"Error processing address: {e}")
        return 0, []

# Streamlit UI
st.title("Ultimate Jeet Tracker")
st.write("Enter a Solana wallet address to scan for jeets (sells) of top 1000 tokens over the past 7 days.")

address = st.text_input("Solana Address (e.g., 9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM)", 
                       placeholder="Enter a valid Solana address")
if st.button("Scan for Jeets"):
    if address:
        with st.spinner("Fetching top tokens and scanning transactions..."):
            top_tokens = get_top_tokens()
            jeet_count, jeeted_list = count_jeets(address, top_tokens)
            st.success(f"Jeet Count: {jeet_count}")
            if jeeted_list:
                st.subheader("Jeeted Tokens")
                st.table({"Token Mint": [t[0] for t in jeeted_list], "Symbol": [t[1] for t in jeeted_list]})
    else:
        st.error("Please enter a valid Solana address.")
