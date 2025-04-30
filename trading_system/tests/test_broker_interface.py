import sys

import os

# Add parent directory (trading_system/) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from dotenv import load_dotenv
load_dotenv(override=True)  # Loads the .env file

from trading_system.utils.interface_factory import get_trading_interface

def test_trading_interface():
    trader = get_trading_interface()

    # Test fetching account
    account = trader.get_account()
    print("Account Info:")
    print(f"  Cash Available: ${account.cash}")
    print(f"  Portfolio Value: ${account.portfolio_value}")
    print()

    # Test fetching a price
    symbol = "BTC/USD"
    price = trader.get_last_price(symbol)
    print(f"Last price of {symbol}: ${price}")

    #  Optionally, test small buy/sell (careful if live money!!)
    # qty = 0.0001
    # trader.buy(symbol, qty)
    # print(f"Placed small BUY order for {qty} {symbol}")

if __name__ == "__main__":
    test_trading_interface()
