from .base_interface import TradingInterface
from .alpaca_client import get_alpaca_client

class AlpacaTradingInterface(TradingInterface):
    def __init__(self):
        self.client = get_alpaca_client()

    def buy(self, symbol: str, qty: int):
        print(f"[Alpaca] Buying {qty} {symbol}")
        return self.client.submit_order(
            symbol=symbol.upper(), qty=qty, side='buy', type='market', time_in_force='gtc'
        )

    def sell(self, symbol: str, qty: int):
        print(f"[Alpaca] Selling {qty} {symbol}")
        return self.client.submit_order(
            symbol=symbol.upper(), qty=qty, side='sell', type='market', time_in_force='gtc'
        )

    def get_position(self, symbol: str):
        try:
            return self.client.get_position(symbol.upper())
        except Exception:
            return None

    def get_last_price(self, symbol: str):
        try:
            return self.client.get_latest_trade(symbol.upper()).price
        except Exception:
            return None

    def get_account(self):
        return self.client.get_account()

#---------------------------------------
# MORE BROKER'S INTERFACES COMING SOON
#---------------------------------------