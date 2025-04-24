import os
import alpaca_trade_api as tradeapi
from alpaca.data.historical import CryptoHistoricalDataClient


def get_alpaca_client():
    env = os.getenv("ENVIRONMENT", "paper").lower()

    if env == "live":
        key = os.getenv("LIVE_API_KEY_ID")
        secret = os.getenv("LIVE_API_SECRET_KEY")
        base_url = os.getenv("LIVE_API_BASE_URL")
    else:  # Default to paper
        key = os.getenv("PAPER_API_KEY_ID")
        secret = os.getenv("PAPER_API_SECRET_KEY")
        base_url = os.getenv("PAPER_API_BASE_URL")

    # Optional: validate presence of values
    if not all([key, secret, base_url]):
        raise ValueError(f"[Alpaca] Missing credentials for environment: {env}")

    return tradeapi.REST(key, secret, base_url)

def get_alpaca_crypto_client():
    return CryptoHistoricalDataClient(API_KEY, SECRET_KEY)