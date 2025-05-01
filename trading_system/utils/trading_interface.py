from .base_interface import TradingInterface
from alpaca.data.requests import CryptoLatestTradeRequest
from alpaca.data.requests import StockLatestTradeRequest
from .alpaca_client import get_trading_client, get_crypto_data_client, get_stock_data_client
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

class AlpacaTradingInterface:
    def __init__(self):
        self.trading_client = get_trading_client()
        self.crypto_data_client = get_crypto_data_client()
        self.stock_data_client = get_stock_data_client()

    def get_last_price(self, symbol: str):
        try:
            if "/" in symbol:  # Crypto symbol e.g. BTC/USD
                request = CryptoLatestTradeRequest(symbol_or_symbols=[symbol.upper()])
                response = self.crypto_data_client.get_crypto_latest_trade(request)
                return float(response[symbol.upper()].price)
            else:  # Stock symbol e.g. AAPL
                request = StockLatestTradeRequest(symbol_or_symbols=[symbol.upper()])
                response = self.stock_data_client.get_stock_latest_trade(request)
                return float(response[symbol.upper()].price)
        except Exception as e:
            print(f"[Alpaca] Error fetching last price for {symbol}: {e}")
            return None

    def buy(self, symbol: str, qty: float):
        
        print(f"[Alpaca] Buying {qty} {symbol}")
        formatted_symbol = symbol.upper().replace("_","/")
        order_request = MarketOrderRequest(
            symbol=formatted_symbol,
            qty=qty,
            side=OrderSide.BUY,
            type="market",
            time_in_force=TimeInForce.GTC
        )
        return self.trading_client.submit_order(
            order_data=order_request
        )

    def sell(self, symbol: str, qty: float):

        print(f"[Alpaca] Selling {qty} {symbol}")
        formatted_symbol = symbol.upper().replace("_","/")
        order_request = MarketOrderRequest(
            symbol=formatted_symbol,
            qty=qty,
            side=OrderSide.SELL,
            type="market",
            time_in_force=TimeInForce.GTC
        )
        return self.trading_client.submit_order(
            order_data=order_request
        )

    def get_position(self, symbol: str):
        try:
            return self.trading_client.get_open_position(symbol.upper())
        except Exception:
            return None

    def get_account(self):
        return self.trading_client.get_account()
    