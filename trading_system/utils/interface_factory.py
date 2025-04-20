import os
from .trading_interface import AlpacaTradingInterface

def get_trading_interface():
    provider = os.getenv("TRADING_PROVIDER", "alpaca").lower()

    if provider == "alpaca":
        return AlpacaTradingInterface()
    else:
        raise ValueError(f"Unsupported trading provider: {provider}")
