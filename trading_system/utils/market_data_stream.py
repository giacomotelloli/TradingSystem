import threading
import time

class MarketDataStream:
    def __init__(self, stock, on_data_callback, trading_interface, frequency=2.0):
        self.stock = stock
        self.on_data_callback = on_data_callback
        self.trading_interface = trading_interface
        self.frequency = frequency
        self.running = False

    def start(self):
        self.running = True
        threading.Thread(target=self._stream_loop, daemon=True).start()

    def stop(self):
        self.running = False

    def _stream_loop(self):
        while self.running:
            try:
                price = self.trading_interface.get_last_price(self.stock)
                if price:
                    data = {
                        "symbol": self.stock,
                        "price": price,
                        "timestamp": time.time()
                    }
                    self.on_data_callback(data)
            except Exception as e:
                print(f"[Stream] Error fetching data for {self.stock}: {e}")
            time.sleep(self.frequency)
