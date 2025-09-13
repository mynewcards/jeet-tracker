import requests
import json
import time
from datetime import datetime
from collections import defaultdict, deque
import pandas as pd  # For nicer output table

# Configuration
WALLET_ADDRESS = "YourSolanaWalletAddressHere"  # e.g., "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1" (example)
RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
COINGECKO_API = "https://api.coingecko.com/api/v3"

def rpc_call(method, params=[]):
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method,
        "params": params
    }
    response = requests.post(RPC_ENDPOINT, json=payload)
    return response.json().get('result')

def get_signatures(before_sig=None, limit=1000):
    params = [WALLET_ADDRESS, {"limit": limit}]
    if before_sig:
        params[1]["before"] = before_sig
    return rpc_call("getSignaturesForAddress", params)

def get_transaction_details(sig):
    return rpc_call("getTransaction", [sig, {"encoding": "jsonParsed", "maxSupportedTransactionVersion": 0}])

def get_token_price(token_symbol, date):
    # Approximate historical price in USD. date is UNIX timestamp.
    # For Solana tokens, use a proxy like SOL if not listed; for demo, assume common tokens like USDC/SOL.
    # In real code, map token mint to CoinGecko ID.
    try:
        # Example for SOL; extend for other tokens
        if token_symbol == 'SOL':
            url = f"{COINGECKO_API}/coins/solana/history?date={date.strftime('%d-%m-%Y')}"
        elif token_symbol == 'USDC':
            url = f"{COINGECKO_API}/coins/usdc/history?date={date.strftime('%d-%m-%Y')}"
        # Add more mappings as needed, e.g., for meme tokens use current price approx.
        else:
            return 0.001  # Fallback low price for unknown meme tokens
        resp = requests.get(url)
        data = resp.json()
        return data.get('market_data', {}).get('current_price', {}).get('usd', 0)
    except:
        return 0

def analyze_wallet():
    # Fetch all transaction signatures
    signatures = []
    before = None
    while True:
        sigs = get_signatures(before)
        if not sigs:
            break
        signatures.extend(sigs)
        before = sigs[-1]['signature']
        time.sleep(0.1)  # Rate limit

    # Parse transactions for token transfers
    buys = defaultdict(deque)  # token_mint: deque of (amount, timestamp, usd_value)
    sells = defaultdict(list)  # token_mint: list of (amount, timestamp, usd_value)
    token_set = set()  # For unique tokens jeeted

    for sig_info in signatures:
        tx = get_transaction_details(sig_info['signature'])
        if not tx or 'meta' not in tx:
            continue
        timestamp = datetime.fromtimestamp(sig_info['blockTime'])
        pre_balances = {bal['owner']: bal for bal in tx.get('meta', {}).get('preTokenBalances', [])}
        post_balances = {bal['owner']: bal for bal in tx.get('meta', {}).get('postTokenBalances', [])}

        # Simplified: Check for net token outflow (sell) or inflow (buy) for the wallet
        # In reality, use program IDs to detect swaps (e.g., Jupiter: JUP6LkbZbjS1jKKwapdHNy74zcZ3tLUZoi5QNyVTaV4)
        for account in post_balances:
            if account != WALLET_ADDRESS:
                continue
            mint = post_balances[account].get('mint')
            if not mint:
                continue
            pre_amount = float(pre_balances.get(account, {}).get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
            post_amount = float(post_balances[account].get('uiTokenAmount', {}).get('uiAmount', 0) or 0)
            amount_change = post_amount - pre_amount
            if amount_change > 0:
                # Buy
                usd_value = amount_change * get_token_price(mint[:8], timestamp)  # Approx symbol from mint
                buys[mint].append((amount_change, timestamp, usd_value))
            elif amount_change < 0:
                # Sell
                usd_value = abs(amount_change) * get_token_price(mint[:8], timestamp)
                sells[mint].append((abs(amount_change), timestamp, usd_value))
                token_set.add(mint)

        time.sleep(0.1)  # Rate limit

    # Calculate P&L for losses (FIFO matching)
    total_usd_lost = 0
    for mint, sell_list in sells.items():
        buy_queue = buys[mint]
        for sell_amount, sell_time, sell_usd in sell_list:
            total_sold = 0
            while buy_queue and total_sold < sell_amount:
                buy_amount, buy_time, buy_usd_per_unit = buy_queue[0]
                if buy_amount <= sell_amount - total_sold:
                    # Full buy lot sold
                    pnl = (sell_usd / sell_amount) * buy_amount - (buy_usd_per_unit * buy_amount)
                    total_sold += buy_amount
                    buy_queue.popleft()
                else:
                    # Partial
                    fraction = (sell_amount - total_sold) / buy_amount
                    pnl = (sell_usd / sell_amount) * (buy_amount * fraction) - (buy_usd_per_unit * buy_amount * fraction)
                    buy_queue[0] = (buy_amount * (1 - fraction), buy_time, buy_usd_per_unit)
                    total_sold = sell_amount
                if pnl < 0:
                    total_usd_lost += abs(pnl)

    # Results
    tokens_jeeted = len(token_set)
    print(f"Tokens Jeeted (Sold): {tokens_jeeted}")
    print(f"USD Lost (from losing sells): ${total_usd_lost:.2f}")

    # For table output: Summary of sells
    sell_data = []
    for mint, sell_list in sells.items():
        total_sell_usd = sum(s[2] for s in sell_list)
        sell_data.append({'Token Mint': mint[:8], 'Sells Count': len(sell_list), 'Total Sell USD': total_sell_usd})
    df = pd.DataFrame(sell_data)
    print("\nSell Summary Table:")
    print(df)

# Run the analysis
if __name__ == "__main__":
    analyze_wallet()