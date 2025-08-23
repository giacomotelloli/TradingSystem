import time
from trading_system.utils.market_data_stream import MarketDataStream  # lasciato se vuoi fallback in futuro
from trading_system.utils.bar_aggregator_stream import AggregatingBarStream

class StrategyRunner:
    def __init__(self, stock, strategy_cls, strategy_initial_capital,
                 trader, stock_state, command_queue, state,
                 bar_timeframe_minutes: int = 1):
        self.stock = stock
        self.trader = trader
        self.stock_state = stock_state
        self.command_queue = command_queue
        self.state = state
        self.strategy = strategy_cls(stock, strategy_initial_capital)
        self.running = False

        # Stream: aggrega 1m -> N minuti e chiama on_bar_agg
        self.data_stream = AggregatingBarStream(
            symbol=stock,
            timeframe_minutes=bar_timeframe_minutes,
            on_bar_agg=self._on_bar_agg,
            api_key=getattr(trader, "api_key", None) if hasattr(trader, "api_key") else None,
            api_secret=getattr(trader, "api_secret", None) if hasattr(trader, "api_secret") else None,
        )

    def run(self):
        stock_name = self.stock.upper().replace("_", "/")
        print(f"[{stock_name}] StrategyRunner starting...")
        self.running = True
        self.data_stream.start()
        self.state.update_status(self.stock, "running")

        while self.running:
            if not self.command_queue.empty():
                cmd = self.command_queue.get()
                if cmd == "close_position":
                    print(f"[{stock_name}] Closing strategy runner...")
                    self.running = False
                    break
            time.sleep(0.2)

        # flush eventuale ultima candela
        try:
            self.data_stream.flush()
        except Exception:
            pass

        self.data_stream.stop()
        self.state.update_status(self.stock, "completed")
        print(f"[{self.stock.upper()}] StrategyRunner stopped.")

    # ===== nuovo handler: candela aggregata chiusa =====
    def _on_bar_agg(self, bar):
        """
        bar = {
          "symbol": "BTC/USD", "timeframe": "5Min",
          "start": "...", "end": "...",
          "open":..., "high":..., "low":..., "close":..., "volume":...
        }
        """
        if not self.running:
            return

        # Se vuoi passare tutta la candela alla strategia, puoi:
        # signal = self.strategy.on_data(bar)

        # Ma la tua RSI usa 'price' -> creiamo un tick sintetico con la close
        data = {
            "symbol": self.stock,
            "price": float(bar["close"]),
            "timestamp": bar["end"]  # fine finestra = "consuntivo"
        }
        signal = self.strategy.on_data(data)

        if signal["action"] == "buy":
            price = data["price"]
            qty = signal["quantity"]
            real_symbol = self.stock.upper().replace("_", "/")
            self.trader.buy(real_symbol, qty)
            self.stock_state.update_on_buy(self.stock, qty, price * qty)
            print(f"[{self.stock.upper()}] Executed BUY at ${price:.2f}")

        elif signal["action"] == "sell":
            current = self.stock_state.get_state(self.stock)
            qty = current.get("quantity", 0)
            if qty > 0:
                price = data["price"]
                real_symbol = self.stock.upper().replace("_", "/")
                self.trader.sell(real_symbol, qty)
                self.stock_state.update_on_sell(self.stock, qty, price * qty)
                print(f"[{self.stock.upper()}] Executed SELL at ${price:.2f}")

    def on_data(self, data):
        """
            Receives data from the MarketDataStream 
            and passes it to the strategy and make actions 
        """
        if not self.running:
            return

        signal = self.strategy.on_data(data)

        if signal["action"] == "buy":

            price = data["price"]
            qty = signal["quantity"] 

            real_symbol = self.stock.upper().replace("_", "/")
            self.trader.buy(real_symbol, qty)
            self.stock_state.update_on_buy(self.stock, qty, price * qty)
            print(f"[{self.stock.upper()}] Executed BUY at ${price:.2f}")

        elif signal["action"] == "sell":
            current = self.stock_state.get_state(self.stock)
            qty = current.get("quantity", 0)
            if qty > 0:
                price = data["price"]
                real_symbol = self.stock.upper().replace("_", "/")
                self.trader.sell(real_symbol, qty)
                self.stock_state.update_on_sell(self.stock, qty, price * qty)
                print(f"[{self.stock.upper()}] Executed SELL at ${price:.2f}")
