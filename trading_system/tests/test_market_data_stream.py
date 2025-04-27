import sys
import os

# Add parent directory (trading_system/) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

import time
from trading_system.utils.market_data_stream import MarketDataStream
from trading_system.utils.interface_factory import get_trading_interface

def on_market_data(data):
    print(f"Received Market Data: {data}")

def test_market_data_stream():
    trader = get_trading_interface()

    stream = MarketDataStream(
        stock="btc_usd", 
        on_data_callback=on_market_data,
        trading_interface=trader,
        frequency=2.0  # every 2 seconds
    )

    print("Starting market data stream for BTC/USD...")
    stream.start()

    # Let it run for 10 seconds
    time.sleep(10)

    stream.stop()
    print("Stopped market data stream.")

if __name__ == "__main__":
    test_market_data_stream()
