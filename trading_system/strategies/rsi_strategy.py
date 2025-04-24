from strategies.base import StrategyBase
import numpy as np

class RSIStrategy(StrategyBase):
    def __init__(self, stock, window=14):
        super().__init__(stock)
        self.prices = []
        self.window = window

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

        if rsi < 30:
            return {"action": "buy", "confidence": 1.0}
        elif rsi > 70:
            return {"action": "sell", "confidence": 1.0}
        else:
            return {"action": "hold", "confidence": 0.0}
