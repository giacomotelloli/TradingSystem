import sys
import os
from dotenv import load_dotenv

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from trading_system.utils.market_data_stream_bars import MarketDataStreamBars

load_dotenv(override=True)

API_KEY = os.getenv("PAPER_API_KEY_ID")
SECRET_KEY = os.getenv("PAPER_API_SECRET_KEY")


def on_bar(data: dict):
    print(f"[BAR 1m] {data['symbol']} {data['timestamp']} "
          f"O:{data['open']} H:{data['high']} L:{data['low']} "
          f"C:{data['close']} V:{data['volume']}")


def test_market_data_stream_bars():
    stream = MarketDataStreamBars(
        stock="btc_usd",
        on_data_callback=on_bar,
        api_key=API_KEY,
        api_secret=SECRET_KEY
    )

    # adesso usi direttamente il grafico integrato
    stream.run_with_chart()


if __name__ == "__main__":
    test_market_data_stream_bars()
