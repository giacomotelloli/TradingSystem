import os
import alpaca_trade_api as tradeapi
from alpaca.data.historical import CryptoHistoricalDataClient

API_KEY = Settings.API_KEY
SECRET_KEY = Settings.API_SECRET
BASE_URL = 'https://paper-api.alpaca.markets'

def get_alpaca_client():
    return tradeapi.REST(
        API_KEY,
        SECRET_KEY,
        BASE_URL
    )

def get_alpaca_crypto_client():
    return CryptoHistoricalDataClient(API_KEY, SECRET_KEY)