import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import CryptoHistoricalDataClient, StockHistoricalDataClient

load_dotenv()

def get_trading_client():
    env = os.getenv("ENVIRONMENT", "paper").lower()

    if env == "live":
        key = os.getenv("LIVE_API_KEY_ID")
        secret = os.getenv("LIVE_API_SECRET_KEY")
    else:  # Default to paper
        key = os.getenv("PAPER_API_KEY_ID")
        secret = os.getenv("PAPER_API_SECRET_KEY")

    if not all([key, secret]):
        raise ValueError(f"[Alpaca] Missing credentials for environment: {env}")

    # TradingClient knows if you are paper trading based on a flag
    is_paper = env == "paper"
    return TradingClient(api_key=key, secret_key=secret, paper=is_paper)

def get_crypto_data_client():
    api_key = os.getenv("PAPER_API_KEY_ID")
    api_secret = os.getenv("PAPER_API_SECRET_KEY")
    if not all([api_key, api_secret]):
        raise ValueError("Missing PAPER_API_KEY_ID or PAPER_API_SECRET_KEY in .env")

    return CryptoHistoricalDataClient(api_key=api_key, secret_key=api_secret)

def get_stock_data_client():
    api_key = os.getenv("PAPER_API_KEY_ID")
    api_secret = os.getenv("PAPER_API_SECRET_KEY")
    if not all([api_key, api_secret]):
        raise ValueError("Missing PAPER_API_KEY_ID or PAPER_API_SECRET_KEY in .env")

    return StockHistoricalDataClient(api_key=api_key, secret_key=api_secret)
