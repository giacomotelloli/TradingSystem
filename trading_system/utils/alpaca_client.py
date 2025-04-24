import os
from dotenv import load_dotenv
import alpaca_trade_api as tradeapi
from alpaca.data.historical import CryptoHistoricalDataClient

load_dotenv()

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

def get_crypto_data_client():
    """
    Returns a client to query historical crypto price data (bars, trades, etc.).
    """
    api_key = os.getenv("PAPER_API_KEY_ID")
    api_secret = os.getenv("PAPER_API_SECRET_KEY")

    if not api_key or not api_secret:
        raise ValueError("Missing PAPER_API_KEY_ID or PAPER_API_SECRET_KEY in .env")

    return CryptoHistoricalDataClient(api_key=api_key, secret_key=api_secret)