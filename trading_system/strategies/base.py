class StrategyBase:
    def __init__(self, stock):
        """
        :param stock: The symbol (e.g. 'aapl') the strategy operates on.
        """
        self.stock = stock

    def on_data(self, data):
        """
        This method must be implemented by any subclass.
        It processes incoming market data and returns a trading signal.

        :param data: dict containing at least:
                     - 'symbol': str
                     - 'price': float
                     - 'timestamp': float (optional)
        :return: dict containing:
                 - 'action': 'buy', 'sell', or 'hold'
                 - 'confidence': float between 0.0 and 1.0
        """
        raise NotImplementedError("Strategy must implement the on_data() method.")
