from .base import StrategyBase
import numpy as np

class Strategy(StrategyBase):
    def __init__(self, stock, starting_capital,window=14):
        super().__init__(stock)
        self.prices = []
        self.window = window
        self.position = 0
        self.entry_price = None
        self.highest_price = None
        self.amount_to_invest = starting_capital
        self.pnl = 0

        
    def compute_rsi(self, prices):
        if len(prices) < self.window:
            return None

        prices = np.array(prices[-self.window:])
        deltas = np.diff(prices)
        gains = deltas[deltas > 0].sum() / self.window
        losses = -deltas[deltas < 0].sum() / self.window
        rs = gains / losses if losses != 0 else 0
        rsi = 100 - (100 / (1 + rs))
        return rsi

    def on_data(self, data):
        price = data["price"]
        self.prices.append(price)

        rsi = self.compute_rsi(self.prices)
        if rsi is None:
            return {"action": "hold", "confidence": 0.0}

        # If no open position and RSI is low, buy
        if self.position == 0 and rsi < 30:
            if self.capital >= self.amount_to_invest:
                self.position = self.amount_to_invest / price
                self.capital -= self.amount_to_invest
                self.entry_price = price
                self.highest_price = price
                return {"action": "buy",
                         "confidence": 1.0,
                         "quantity":self.position}

        # If position is open, manage trailing stop and sell conditions
        if self.position > 0:
            self.highest_price = max(self.highest_price, price)
            trailing_stop_price = self.highest_price * (1 - 0.02)
            target_price = self.entry_price * (1 + 0.03)

            if price <= trailing_stop_price and price >= target_price and rsi > 50:
                sell_value = self.position * price
                realized_pnl = sell_value - (self.position * self.entry_price)
                self.pnl += realized_pnl
                self.capital += sell_value
                self.position = 0
                self.entry_price = None
                self.highest_price = None
                return {"action": "sell", "confidence": 1.0}

        return {"action": "hold", "confidence": 0.0}