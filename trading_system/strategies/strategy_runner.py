import time
from trading_system.utils.market_data_stream import MarketDataStream  # lasciato se vuoi fallback in futuro
from trading_system.utils.bar_aggregator_stream import AggregatingBarStream

class StrategyRunner:
    def __init__(self, stock, strategy_cls, strategy_initial_capital,
                 trader, stock_state, command_queue, state, frequency=2.0,
                 portfolio_manager=None):           # <-- NUOVO
        self.stock = stock
        self.trader = trader
        self.stock_state = stock_state
        self.command_queue = command_queue
        self.state = state
        self.strategy = strategy_cls(stock, strategy_initial_capital)
        self.running = False
        self.portfolio = portfolio_manager            # <-- NUOVO

        self.data_stream = MarketDataStream(
            stock=stock,
            on_data_callback=self.on_data,
            trading_interface=trader,
            frequency=frequency
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
            time.sleep(0.5)

        self.data_stream.stop()
        self.state.update_status(self.stock, "completed")
        print(f"[{self.stock.upper()}] StrategyRunner stopped.")

    def on_data(self, data):
        if not self.running:
            return

        signal = self.strategy.on_data(data)

        if signal["action"] == "buy":
            price = data["price"]
            qty = signal["quantity"]

            if self.portfolio:
                self.portfolio.book_buy(self.stock, qty, price)
            else:
                # fallback vecchio
                real_symbol = self.stock.upper().replace("_", "/")
                self.trader.buy(real_symbol, qty)
                self.stock_state.update_on_buy(self.stock, qty, price * qty)

            print(f"[{self.stock.upper()}] Executed BUY at ${price:.2f}")

        elif signal["action"] == "sell":
            current = self.stock_state.get_state(self.stock)
            qty = current.get("quantity", 0)
            if qty > 0:
                price = data["price"]

                if self.portfolio:
                    self.portfolio.book_sell(self.stock, qty, price)
                else:
                    real_symbol = self.stock.upper().replace("_", "/")
                    self.trader.sell(real_symbol, qty)
                    self.stock_state.update_on_sell(self.stock, qty, price * qty)

                print(f"[{self.stock.upper()}] Executed SELL at ${price:.2f}")
    
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

    